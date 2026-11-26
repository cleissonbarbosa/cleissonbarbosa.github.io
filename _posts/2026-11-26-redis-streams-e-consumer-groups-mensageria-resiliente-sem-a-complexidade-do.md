---
title: "Redis Streams e Consumer Groups: Mensageria Resiliente sem a Complexidade do Kafka"
author: ia
date: 2026-11-26 01:00:53 -0300
description: "Aprenda a construir sistemas de mensageria confiáveis com Redis Streams, Consumer Groups, PEL e XAUTOCLAIM, evitando o overengineering do Kafka em produção."
image:
  path: /assets/img/posts/c7b457dc-eb10-4675-a2f6-16012485b92c.png
  alt: "Redis Streams e Consumer Groups: Mensageria Resiliente sem a Complexidade do Kafka"
categories: ["backend", "arquitetura", "bancos de dados"]
tags: ["redis", "redis-streams", "mensageria", "sistemas-distribuidos", "go", "arquitetura-de-software", "ai-generated"]
---

Se você já participou de discussões de arquitetura para novos microsserviços, provavelmente já presenciou a seguinte cena: a equipe precisa desacoplar um fluxo assíncrono simples — como disparar e-mails de boas-vindas, processar imagens em segundo plano ou sincronizar cadastros entre dois serviços — e imediatamente alguém saca a carta mágica: *"Vamos subir um cluster de Kafka!"*.

Duas semanas depois, o time está gerenciando tópicos, partições, balanceamento de *consumer groups*, brokers do Kafka, storage persistent volume claims complexos no Kubernetes, e descobrindo que o consumo de memória da JVM já engoliu metade da cota da infraestrutura para trafegar míseras 50 mensagens por segundo. Como mencionei no nosso [último resumo da semana](https://cleissonbarbosa.github.io/posts/resumo-da-semana-postgresql-19-java4shell-vazamentos-em-agentes-de-ia-e-receita/){:target="_blank"}, a complexidade operacional é um dos maiores vetores de falhas e incidentes em produção. Escolher a marreta errada para um prego pequeno não é apenas ineficiente; é arriscado.

Por outro lado, o clássico **Redis Pub/Sub** é descartado logo de cara por um motivo justo: ele é *fire-and-forget*. Se o consumidor estiver reiniciando no momento em que a mensagem chega, o dado simplesmente evapora.

É aqui que entra o **Redis Streams**. Introduzido no Redis 5.0 e consolidado há anos, ele oferece a semântica de um log de eventos distribuído e append-only — muito parecida com a do Kafka —, com suporte a confirmações de leitura (ACKs), grupos de consumidores concorrentes, retenção em memória e recuperação de falhas, aproveitando a mesma instância de Redis que você provavelmente já tem na sua infraestrutura para cache.

Neste artigo, vamos dissecar o Redis Streams por dentro, entender como o *Pending Entries List* (PEL) funciona, como tratar falhas com `XAUTOCLAIM` e construir um consumidor resiliente em Go que aguenta o tranco do mundo real.

---

## Por Que Não Apenas Redis Pub/Sub ou Listas (LPUSH/RPOP)?

Antes do Streams, engenheiros usavam duas abordagens principais para filas no Redis:

1. **Pub/Sub tradicional (`PUBLISH` / `SUBSCRIBE`)**: Excelente para broadcast em tempo real (como notificações efêmeras via WebSockets), mas completamente inadequado para processamento de tarefas críticas. Não há persistência, não há histórico e não há garantia de entrega (*at-most-once* puro).
2. **Listas (`LPUSH` / `BRPOP` ou `RPOPLPUSH`)**: Funcionam bem para filas de tarefas simples ponto a ponto. No entanto, escalar para múltiplos consumidores independentes que precisam ler *a mesma* mensagem (modelo fan-out com grupos de leitura) exige criar listas separadas para cada sistema consumidor. Além disso, a inspeção de mensagens presas ou reprocessamento em caso de crash do worker exige malabarismos complexos.

O **Redis Streams** resolve essas duas deficiências unindo a durabilidade do append-only log ao modelo de *Consumer Groups*.

```
                                  +--> [Consumer Group: emails] --> Worker A / Worker B
[Producer] ---> [Stream: orders] -|
                                  +--> [Consumer Group: estoque] -> Worker C / Worker D
```

Cada mensagem no Stream recebe um ID único baseado em timestamp (`<millisecondsTime>-<sequenceNumber>`), persiste de acordo com a estratégia de retenção configurada e pode ser lida independentemente por diferentes grupos de consumidores.

---

## Anatomia de uma Mensagem e o Custo de Memória

Internamente, o Redis armazena streams utilizando uma estrutura de dados chamada **radix tree** combinada com **listpacks** (estruturas compactas de bytes contíguos na memória). Isso significa que, ao contrário de criar milhares de nós em listas encadeadas, o Redis Streams compacta múltiplos eventos por bloco, tornando-o extremamente eficiente em termos de RAM.

Para publicar um evento, usamos o comando `XADD`:

```text
XADD pedidos * tipo "novo_pagamento" valor "159.90" cliente_id "usr_8812"
```

O asterisco `*` instrui o Redis a gerar o ID automaticamente usando o relógio do servidor, por exemplo: `1716382901234-0`. Esse ID é estritamente incremental.

### O Perigo do Tamanho Infinito e o `MAXLEN ~`

Como o Redis é um banco in-memory, deixar uma stream crescer indefinidamente vai esgotar sua RAM até disparar o OOM Killer do Linux ou a política de eviction do Redis. Por isso, nunca chame `XADD` em produção sem definir um teto de retenção.

O Redis oferece o argumento `MAXLEN`, mas há um truque fundamental de performance: use o modificador `~` (aproximado):

```text
XADD pedidos MAXLEN ~ 100000 * tipo "novo_pagamento" valor "159.90"
```

Por que usar o `~`? Sem ele (`MAXLEN 100000` exato), a cada inserção o Redis precisaria cortar cirurgicamente os nós das listpacks para manter exatamente cem mil itens, forçando realocações de memória frequentes. Com o `~`, o Redis só remove blocos inteiros de listpack quando um limite razoável é excedido. O ganho de throughput é gigantesco com custo insignificante de variação de tamanho.

---

## Dominando Consumer Groups e o Ciclo de Vida da Mensagem

Para processar mensagens em paralelo com múltiplos workers cooperando entre si, criamos um **Consumer Group**.

```text
# Criando o grupo 'processadores-pedidos' ouvindo desde o início (0) ou novas mensagens ($)
XGROUP CREATE pedidos processadores-pedidos 0 MKSTREAM
```

O parâmetro `MKSTREAM` é crucial: ele cria a Stream automaticamente caso ela ainda não exista, evitando erros de inicialização durante deploys simultâneos.

### O ID Especial `>` e a Leitura Concorrente

Quando um worker quer consumir uma nova mensagem que nenhum outro worker do grupo viu, ele usa o comando `XREADGROUP` com o ID especial `>`:

```text
XREADGROUP GROUP processadores-pedidos worker-1 COUNT 2 BLOCK 2000 STREAMS pedidos >
```

O que acontece aqui:
1. O Redis entrega até 2 mensagens que ainda não foram distribuídas a ninguém do grupo.
2. O worker fica bloqueado por até 2000 milissegundos aguardando dados se a fila estiver vazia.
3. **Internamente, o Redis move essas mensagens para a PEL (Pending Entries List) associada ao `worker-1`.**

### O que é a PEL (Pending Entries List)?

A PEL é o coração da confiabilidade do Redis Streams. Quando uma mensagem é entregue a um consumidor, ela não é removida da stream. O Redis anota em uma tabela interna: *"A mensagem X foi entregue ao worker-1 às 14:00:00 e ainda não foi confirmada"*.

Se o seu worker processar o pedido com sucesso, ele deve enviar explicitamente um comando de reconhecimento (`XACK`):

```text
XACK pedidos processadores-pedidos 1716382901234-0
```

Assim que o `XACK` é recebido, a entrada é removida da PEL. A mensagem continua na stream principal (até ser descartada pelo `MAXLEN`), mas o grupo de consumidores sabe que o trabalho foi concluído.

---

## O Cenário de Desastre: Lidando com Falhas e Workers Zumbis

Em sistemas distribuídos, a regra é simples: coisas vão falhar. O container do seu worker pode sofrer SIGKILL por estourar limites de memória, o pod pode ser desalocado pelo Kubernetes durante um auto-scale down, ou uma chamada externa de rede pode travar a goroutine.

O que acontece com as mensagens que estavam no meio do caminho? **Elas continuam presas na PEL para sempre se você não fizer nada.**

Historicamente, resolver isso no Redis exigia uma rotina manual e complexa usando `XPENDING` seguido de `XCLAIM`. A partir do **Redis 6.2**, a equipe do Redis introduziu o excelente comando `XAUTOCLAIM`, que simplificou drasticamente a recuperação de mensagens órfãs.

```text
# Tenta reivindicar mensagens que estão paradas na PEL há mais de 60.000 ms (1 minuto)
XAUTOCLAIM pedidos processadores-pedidos worker-recuperador 60000 0-0 COUNT 10
```

O comando faz três coisas em uma única operação atômica:
1. Varre a PEL do grupo procurando mensagens com tempo ocioso (*idle time*) superior a 60 segundos.
2. Transfere a propriedade dessas mensagens para o `worker-recuperador`.
3. Retorna a lista de mensagens transferidas para que o novo worker possa processá-las imediatamente.

### Detectando Mensagens Venenosas (Poison Pills)

Algumas mensagens simplesmente quebram o código (ex: um JSON malformado que causa pânico na desserialização, ou um payload que aciona um bug de divisão por zero). Se o seu worker capotar toda vez que tentar processá-la, ela vai entrar num loop infinito de *crash -> timeout na PEL -> claim -> crash*.

Para evitar isso, podemos checar o contador de entregas retornado pelo `XPENDING` ou `XAUTOCLAIM`. Se uma mensagem já foi tentada mais de 5 vezes, nós publicamos em uma Dead Letter Queue (outra Stream dedicada) e emitimos o `XACK` na stream original para tirá-la do caminho.

---

## Implementação Completa em Go: Produtor e Consumidor Resiliente

Vamos montar uma implementação prática e pronta para produção usando o cliente oficial [go-redis](https://github.com/redis/go-redis){:target="_blank"}. Nosso worker cuidará do consumo contínuo, tratamento de graceful shutdown e uma rotina de background para roubar mensagens órfãs com `XAUTOCLAIM`.

### 1. O Produtor Confiável

```go
package main

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/redis/go-redis/v9"
)

type OrderEvent struct {
	ID       string
	Amount   float64
	ClientID string
}

func PublishOrder(ctx context.Context, rdb *redis.Client, order OrderEvent) (string, error) {
	args := &redis.XAddArgs{
		Stream: "stream:orders",
		MaxLen: 50000,
		Approx: true, // Crucial: performance com MAXLEN ~
		Values: map[string]interface{}{
			"order_id":  order.ID,
			"amount":    order.Amount,
			"client_id": order.ClientID,
			"timestamp": time.Now().UnixNano(),
		},
	}

	id, err := rdb.XAdd(ctx, args).Result()
	if err != nil {
		return "", fmt.Errorf("falha ao publicar evento no stream: %w", err)
	}

	return id, nil
}
```

### 2. O Consumidor Resiliente com Autoclaim e Graceful Shutdown

Aqui construímos uma estrutura com dois loops concorrentes: um loop consome mensagens novas via `XREADGROUP`, enquanto o outro periodicamente verifica a PEL em busca de mensagens presas.

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/redis/go-redis/v9"
)

const (
	streamName    = "stream:orders"
	groupName     = "order-processors"
	consumerName  = "worker-instance-01"
	claimInterval = 10 * time.Second
	maxIdleTime   = 30 * time.Second
	maxRetries    = 3
)

func ensureGroupExists(ctx context.Context, rdb *redis.Client) error {
	err := rdb.XGroupCreateMkStream(ctx, streamName, groupName, "$").Err()
	if err != nil && err.Error() != "BUSYGROUP Consumer Group name already exists" {
		return err
	}
	return nil
}

func processMessage(ctx context.Context, rdb *redis.Client, msg redis.XMessage) error {
	log.Printf("Processando mensagem %s: %+v", msg.ID, msg.Values)

	// Simulação de regra de negócio
	time.Sleep(100 * time.Millisecond)

	// Confirmação (ACK) imediata após o sucesso
	return rdb.XAck(ctx, streamName, groupName, msg.ID).Err()
}

func startClaimLoop(ctx context.Context, wg *sync.WaitGroup, rdb *redis.Client) {
	defer wg.Done()
	ticker := time.NewTicker(claimInterval)
	defer ticker.Stop()

	startID := "0-0"

	for {
		select {
		case <-ctx.Done():
			log.Println("Encerrando loop de claim de mensagens órfãs...")
			return
		case <-ticker.C:
			// Busca mensagens travadas na PEL há mais de 30 segundos
			res, nextID, err := rdb.XAutoClaim(ctx, &redis.XAutoClaimArgs{
				Stream:   streamName,
				Group:    groupName,
				Consumer: consumerName,
				MinIdle:  maxIdleTime,
				Start:    startID,
				Count:    10,
			}).Result()

			if err != nil && !errors.Is(err, redis.Nil) {
				log.Printf("Erro no XAutoClaim: %v", err)
				continue
			}

			startID = nextID

			for _, msg := range res {
				log.Printf("[REIVINDICADA] Mensagem órfã recuperada: %s", msg.ID)
				if err := processMessage(ctx, rdb, msg); err != nil {
					log.Printf("Erro ao reprocessar mensagem %s: %v", msg.ID, err)
				}
			}
		}
	 Cambridge:
	}
}

func startConsumerLoop(ctx context.Context, wg *sync.WaitGroup, rdb *redis.Client) {
	defer wg.Done()

	for {
		select {
		case <-ctx.Done():
			log.Println("Encerrando loop principal de consumo...")
			return
		default:
			// Ler novas mensagens com o marcador '>'
			streams, err := rdb.XReadGroup(ctx, &redis.XReadGroupArgs{
				Group:    groupName,
				Consumer: consumerName,
				Streams:  []string{streamName, ">"},
				Count:    10,
				Block:    2 * time.Second,
			}).Result()

			if err != nil {
				if errors.Is(err, redis.Nil) {
					// Timeout sem mensagens, continua o loop
					continue
				}
				log.Printf("Erro no XReadGroup: %v", err)
				time.Sleep(1 * time.Second)
				continue
			}

			for _, stream := range streams {
				for _, msg := range stream.Messages {
					if err := processMessage(ctx, rdb, msg); err != nil {
						log.Printf("Falha ao processar mensagem %s: %v", msg.ID, err)
					}
				}
			}
		}
	}
}

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	rdb := redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
	})
	defer rdb.Close()

	if err := ensureGroupExists(ctx, rdb); err != nil {
		log.Fatalf("Erro ao preparar stream e grupo: %v", err)
	}

	var wg sync.WaitGroup
	wg.Add(2)

	go startConsumerLoop(ctx, &wg, rdb)
	go startClaimLoop(ctx, &wg, rdb)

	log.Println("Worker iniciado com sucesso. Pressione Ctrl+C para encerrar.")
	<-ctx.Done()
	log.Println("Interrupção recebida. Aguardando finalização das rotinas ativas...")

	wg.Wait()
	log.Println("Serviço encerrado de forma graciosa.")
}
```

Observe o cuidado com o **Graceful Shutdown**: quando o container recebe `SIGTERM`, o contexto `ctx` é cancelado, os loops de consumo e claim finalizam a mensagem que estão processando e só então o processo encerra. Isso reduz drasticamente a necessidade de acionar o `XAUTOCLAIM` durante deploys rotineiros.

---

## Comparativo Arquitetural: Redis Streams vs. Kafka vs. RabbitMQ

Nenhuma tecnologia existe no vácuo. Para tomar decisões maduras de arquitetura, compare as forças e fraquezas de cada ferramenta:

| Característica | Redis Streams | Apache Kafka | RabbitMQ |
| :--- | :--- | :--- | :--- |
| **Modelo Primário** | Append-only Log em RAM | Append-only Log em Disco | Fila AMQP com Roteamento Avançado |
| **Armazenamento Padrão** | Memória RAM | Disco (NVMe/SSD) | Memória + Spool para Disco |
| **Complexidade Operacional** | Muito baixa (se já usa Redis) | Alta (Zookeeper/KRaft, JVM, Partições) | Média (Erlang, clustering) |
| **Throughput Típico** | 100k a 500k ops/sec por nó | 1M+ ops/sec em cluster particionado | 20k a 80k msgs/sec |
| **Retenção Longa (Semanas)**| Inviável (custo da RAM) | Nativa e econômica | Não recomendado (fila não é storage) |
| **Roteamento Complexo** | Simples (por stream) | Por Tópico / Header | Altíssimo (Direct, Topic, Fanout, Headers) |
| **Garantia de Entrega** | At-least-once (com PEL + ACK) | At-least-once / Exactly-once | At-least-once (com manual ACK) |

---

## Onde o Redis Streams Falha: Limitações Reais em Produção

Nem tudo são flores. É dever de um engenheiro sênior conhecer os limites do seu ferramental antes de colocá-lo na linha de frente.

### 1. O Custo Proibitivo da Retenção Longa

Se o seu caso de uso exige que mensagens fiquem disponíveis para replay durante 30 dias (por exemplo, auditoria bancária ou event sourcing de domínios inteiros), **não use Redis Streams**. A memória RAM é cara demais para servir como repositório frio de eventos. Nesses cenários, Kafka, Redpanda ou Apache Pulsar são superiores porque salvam os segmentos diretamente em disco e tiering storage (como AWS S3).

### 2. Replicação Assíncrona e Risco de Perda em Failover

Por padrão, a replicação do Redis entre nós Master e Replica é **assíncrona**. Se o Master aceitar um `XADD` e cair antes que o dado seja replicado para a réplica, durante o failover do Sentinel/Cluster essa mensagem pode ser perdida.

Se você precisa de garantias rígidas de durabilidade, pode usar o comando `WAIT` após o `XADD` para forçar confirmação síncrona de $N$ réplicas, mas isso introduz latência de rede no caminho crítico da escrita:

```text
XADD pedidos * tipo "compra"
WAIT 1 1000 # Bloqueia até que 1 réplica confirme ou estoure 1000ms
```

### 3. Escala Horizontal de Streams Individuais

No Kafka, você cria um tópico com 32 partições e escala o paralelismo horizontalmente de forma nativa entre 32 instâncias de workers. No Redis Cluster, uma Stream específica vive **em um único hash slot**, ou seja, em um único nó da máquina.

Embora você possa ter múltiplos consumidores dentro do mesmo Consumer Group dividindo as mensagens daquela stream, o throughput de escrita da stream fica limitado pela capacidade de CPU de uma única thread do Redis. Se você precisar de mais vazão do que uma máquina aguenta (centenas de milhares de escritas por segundo na mesma entidade), terá que fazer o particionamento manualmente na aplicação (ex: criando streams como `stream:orders:0`, `stream:orders:1` via hashing consistente).

---

## Conclusão e Checklist para Produção

O Redis Streams preenche com elegância o imenso abismo que existia entre a fragilidade do Redis Pub/Sub e a pesadíssima infraestrutura de um cluster Kafka. Para mais de 90% dos casos de uso em microsserviços modernos — processamento em lote, integrações assíncronas entre APIs, pipelines de notificações e desacoplamento de escrita —, ele entrega tudo o que precisamos com zero dependências adicionais de infraestrutura.

Antes de colocar sua implementação em produção, revise este checklist:

- [ ] **Defina o `MAXLEN ~` no `XADD`**: Nunca deixe a stream sem política de poda.
- [ ] **Trate o graceful shutdown**: Deixe seu consumidor concluir as mensagens correntes antes de fechar a conexão.
- [ ] **Implemente o `XAUTOCLAIM`**: Sem uma rotina de claim, mensagens de pods mortos ficarão presas na PEL para sempre.
- [ ] **Monitore a PEL com `XPENDING`**: Configure alertas se o número de mensagens pendentes ou o tempo ocioso crescer de forma anormal.
- [ ] **Estabeleça uma DLQ**: Descarte ou isole mensagens que falham consecutivamente após 3 a 5 tentativas.

A melhor arquitetura não é a que usa as ferramentas mais complexas do mercado, mas aquela que resolve o problema do negócio com a menor sobrecarga cognitiva e operacional possível para o time. Dê uma chance ao Redis Streams antes de assinar o cheque do Kafka.

---

_Este post foi totalmente gerado por uma IA autônoma, sem intervenção humana._

[Veja o código que gerou este post](https://github.com/cleissonbarbosa/cleissonbarbosa.github.io/blob/main/generate_post/README.md){:target="_blank"}
