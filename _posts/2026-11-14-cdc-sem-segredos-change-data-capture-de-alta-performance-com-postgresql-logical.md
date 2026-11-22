---
title: "CDC Sem Segredos: Change Data Capture de Alta Performance com PostgreSQL Logical Replication em Go"
author: ia
date: 2026-11-14 22:38:07 -0300
description: "Aprenda a implementar Change Data Capture (CDC) de alta performance usando Logical Replication do PostgreSQL diretamente em Go, eliminando dual-writes e polling."
image:
  path: /assets/img/posts/30213388-89b2-4c78-b6b8-673891360082.png
  alt: "CDC Sem Segredos: Change Data Capture de Alta Performance com PostgreSQL Logical Replication em Go"
categories: ["programação", "backend", "go", "banco de dados"]
tags: ["go", "postgresql", "cdc", "arquitetura", "concorrência", "ai-generated"]
audio: /assets/audio/posts/cdc-sem-segredos-change-data-capture-de-alta-performance-com-postgresql-logical.mp3
---

No último artigo, discutimos sobre [GOMEMLIMIT e GC Tuning em Go](https://cleissonbarbosa.github.io/posts/gomemlimit-e-gc-tuning-em-go-como-parar-de-pagar-caro-por-ram-no-kubernetes/){:target="_blank"} para evitar estouros de memória e manter pods leves no Kubernetes. Mas otimizar o runtime de Go é apenas metade da batalha quando sua arquitetura de microsserviços passa 40% do tempo executando queries de polling no banco de dados para descobrir se novos dados chegaram.

Se você trabalha com arquiteturas orientadas a eventos ou sistemas distribuídos, provavelmente já enfrentou a clássica necessidade: **quando uma linha for inserida ou alterada na tabela X, preciso disparar uma mensagem para o broker Y (Kafka, RabbitMQ, NATS)**.

A maioria dos times começa resolvendo isso com a pior solução possível: a **gravação dupla (dual write)**. O código do serviço faz o `INSERT` na tabela do banco de dados e, na linha seguinte, chama a API do broker de mensagens. Parece simples até que o banco responde com sucesso, o broker falha ou cai por 200ms, e sua aplicação fica em um estado inconsistente irrecuperável.

A evolução natural costuma ser o *Transactional Outbox Pattern*: grava-se o evento em uma tabela `outbox` na mesma transação do banco e um worker fica rodando `SELECT ... FOR UPDATE` periodicamente para publicar esses registros. Funciona? Funciona. Mas gera um desgaste massivo de IOPS, tabela com *bloat* e concorrência no banco de dados que destroem a escalabilidade.

Existe uma alternativa extremamente eficiente e limpa: **Change Data Capture (CDC) nativo via PostgreSQL Logical Replication usando Go**.

Neste post, vamos entender como o streaming de WAL (*Write-Ahead Log*) do PostgreSQL funciona e como você pode escrever um consumidor de eventos streaming de altíssima performance em Go sem depender de infraestruturas pesadas como Java ou Debezium quando tudo o que você precisa é de simplicidade e baixo consumo de memória.

---

## Como Funciona a Replicação Lógica no PostgreSQL

Sempre que o PostgreSQL executa uma transação (`INSERT`, `UPDATE`, `DELETE`), ele grava a alteração sequencialmente no **WAL (Write-Ahead Log)** no disco antes de efetivar o dado na tabela. Isso garante a durabilidade (o 'D' do ACID).

A replicação física tradicional transfere esses blocos de disco binários linha por linha para um banco standby. Já a [Replicação Lógica](https://www.postgresql.org/docs/current/logicaldecoding.html){:target="_blank"} usa o mecanismo de *Logical Decoding* para ler o WAL e traduzir as alterações brutas do banco em eventos estruturados com o estado das tuplas (dados antes e depois da alteração).

Para que isso funcione, o PostgreSQL utiliza três conceitos principais:

1. **Publication**: Uma declaração dentro do banco que especifica quais tabelas e quais eventos (`INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`) devem ser exportados.
2. **Replication Slot**: Um cursor no banco de dados que rastreia qual foi a última posição do WAL lida pelo cliente consumidor. Isso impede que o PostgreSQL delete os arquivos de WAL no disco até que o cliente dê o *acknowledge* (ACK).
3. **Logical Decoder Plugin**: O plugin do PostgreSQL responsável por traduzir o log binário no protocolo de saída. O padrão a partir do PostgreSQL 10 é o `pgoutput`.

```
+---------------+      +--------------+      +-------------------+      +----------------+
|   Aplicação   | ---> |  PostgreSQL  | ---> | WAL (Write-Ahead) | ---> | Logical Slot   |
| (Writes CRUD) |      | (DB Engine)  |      |   (Log de Disco)  |      |   (pgoutput)   |
+---------------+      +--------------+      +-------------------+      +----------------+
                                                                                |
                                                                                v
                                                                      +------------------+
                                                                      | Worker Go (CDC)  |
                                                                      | (pgx stream rx)  |
                                                                      +------------------+
```

A grande vantagem desse modelo é o **desacoplamento total**. O microserviço que realiza os inserts não sabe que os eventos existem, o impacto no throughput de escrita do banco é residual e o seu consumidor em Go recebe os eventos em tempo real com latência na casa dos milissegundos.

---

## Configurando o PostgreSQL para CDC

Antes de escrever uma linha de código em Go, precisamos garantir que o PostgreSQL está configurado adequadamente para suportar replicação lógica.

 No arquivo `postgresql.conf` do seu banco (ou nas configurações da AWS RDS/GCP Cloud SQL), defina o nível do WAL para `logical`:

```ini
wal_level = logical
max_replication_slots = 10
max_wal_senders = 10
```

Após reiniciar o serviço do banco de dados, execute os scripts SQL abaixo para criar uma tabela de exemplo e registrar a *Publication*:

```sql
-- Tabela de exemplo no nosso sistema de e-commerce
CREATE TABLE orders (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Garante que UPDATES e DELETES incluam a linha completa (FULL) nos logs de replicação
ALTER TABLE orders REPLICA IDENTITY FULL;

-- Cria a publicação para rastrear mudanças na tabela orders
CREATE PUBLICATION orders_pub FOR TABLE orders;
```

A propriedade `REPLICA IDENTITY FULL` garante que, durante atualizações (`UPDATE`), o evento do WAL traga tanto os dados antigos quanto os dados novos da linha, algo fundamental se você precisa calcular diferenças (*diffs*).

---

## Construindo o Consumidor CDC em Go

Para interagir diretamente com a API do protocolo de streaming de replicação do PostgreSQL, usaremos a biblioteca [jackc/pgx/v5](https://github.com/jackc/pgx){:target="_blank"}, mais especificamente o subpacote `pgconn` e `pglogrepl` que implementam o protocolo nativo de baixo nível.

### 1. Inicializando as conexões e o Replication Slot

Primeiro, precisamos abrir uma conexão usando o driver no modo de replicação (`replication=database` na connection string).

```go
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pglogrepl"
	"github.com/jackc/pgx/v5/pgproto3"
)

const (
	ConnString = "postgres://postgres:postgres@localhost:5432/app_db?replication=database"
	SlotName   = "orders_cdc_slot"
	PubName    = "orders_pub"
)

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	conn, err := pgconn.Connect(ctx, ConnString)
	if err != nil {
		log.Fatalf("Erro ao conectar ao PostgreSQL: %v", err)
	}
	defer conn.Close(context.Background())

	// Identificar a posição atual da timeline no banco
	sysIdent, err := pglogrepl.IdentifySystem(ctx, conn)
	if err != nil {
		log.Fatalf("IdentifySystem falhou: %v", err)
	}
	fmt.Printf("SystemID: %s, Timeline: %d, XLogPos: %s
", sysIdent.SystemID, sysIdent.Timeline, sysIdent.XLogPos)

	// Criar o slot de replicação se ele não existir
	_, err = pglogrepl.CreateReplicationSlot(ctx, conn, SlotName, "pgoutput", pglogrepl.CreateReplicationSlotOptions{
		Mode: pglogrepl.LogicalReplication,
	})
	if err != nil {
		// Caso o erro indique que o slot já existe, podemos ignorar
		log.Printf("Aviso ao criar slot (pode ser que já exista): %v", err)
	}

	// Iniciar o streaming a partir da posição atual (LSN)
	err = pglogrepl.StartReplication(ctx, conn, SlotName, sysIdent.XLogPos, pglogrepl.StartReplicationOptions{
		PluginArgs: []string{
			"proto_version '1'",
			fmt.Sprintf("publication_names '%s'", PubName),
		},
	})
	if err != nil {
		log.Fatalf("Erro ao iniciar replicação: %v", err)
	}

	log.Println("Escutando eventos de CDC com sucesso...")
	streamLoop(ctx, conn, sysIdent.XLogPos)
}
```

### 2. O Event Loop de Recebimento de Mensagens e Heartbeats

O PostgreSQL exige que a aplicação consumidora leia as mensagens de alteração e confirme periodicamente o **LSN (Log Sequence Number)** consumido. Além disso, o servidor envia pings de *Heartbeat* que exigem resposta do cliente para evitar que a conexão caia por tempo limite (*timeout*).

```go
func streamLoop(ctx context.Context, conn *pgconn.PgConn, startLSN pglogrepl.LSN) {
	var clientXLogPos = startLSN
	standbyMessageTimeout := 10 * time.Second
	nextStandbyMessageDeadline := time.Now().Add(standbyMessageTimeout)
	relations := make(map[uint32]*pglogrepl.RelationMessage)

	for {
		if time.Now().After(nextStandbyMessageDeadline) {
			err := sendClientStatusUpdate(ctx, conn, clientXLogPos)
			if err != nil {
				log.Printf("Erro ao enviar status update: %v", err)
			}
			nextStandbyMessageDeadline = time.Now().Add(standbyMessageTimeout)
		}

		ctxTimeout, cancel := context.WithTimeout(ctx, time.Second*2)
		rawMsg, err := conn.ReceiveMessage(ctxTimeout)
		cancel()

		if err != nil {
			if pgconn.Timeout(err) {
				continue
			}
			log.Printf("Erro ao receber mensagem: %v", err)
			return
		}

		switch msg := rawMsg.(type) {
		case *pgproto3.CopyData:
			switch msg.Data[0] {
			case pglogrepl.PrimaryKeepaliveMessageByte:
				pkm, err := pglogrepl.ParsePrimaryKeepaliveMessage(msg.Data[1:])
				if err != nil {
					log.Printf("ParseKeepalive falhou: %v", err)
					continue
				}
				if pkm.ReplyRequested {
					nextStandbyMessageDeadline = time.Time{}
				}

			case pglogrepl.XLogDataByte:
				xld, err := pglogrepl.ParseXLogData(msg.Data[1:])
				if err != nil {
					log.Printf("ParseXLogData falhou: %v", err)
					continue
				}

				// Processar as alterações de dados reais
				processWALMessage(xld.WALData, relations)

				// Atualizar a posição do LSN lido
				clientXLogPos = xld.WALStart + pglogrepl.LSN(len(xld.WALData))
			}
		}
	}
}

func sendClientStatusUpdate(ctx context.Context, conn *pgconn.PgConn, lsn pglogrepl.LSN) error {
	return pglogrepl.SendStandbyStatusUpdate(ctx, conn, pglogrepl.StandbyStatusUpdate{
		WALWritePosition: lsn,
		WALFlushPosition: lsn,
		WALApplyPosition: lsn,
	})
}
```

### 3. Decodificando Operações de DML (`INSERT`, `UPDATE`, `DELETE`)

O protocolo `pgoutput` serializa os dados enviando primeiro metadados da tabela (`RelationMessage`) e, logo em seguida, as mudanças nas linhas (`InsertMessage`, `UpdateMessage`, etc.). É preciso guardar o mapa de relações na memória para associar os tipos de dados dos campos.

```go
func processWALMessage(walData []byte, relations map[uint32]*pglogrepl.RelationMessage) {
	logicalMsg, err := pglogrepl.Parse(walData)
	if err != nil {
		log.Printf("Falha ao interpretar mensagem WAL: %v", err)
		return
	}

	switch v := logicalMsg.(type) {
	case *pglogrepl.RelationMessage:
		// Mapear o ID da relação para saber os nomes das colunas depois
		relations[v.RelationID] = v

	case *pglogrepl.InsertMessage:
		rel, ok := relations[v.RelationID]
		if !ok {
			log.Printf("Relação ID %d não encontrada na memória", v.RelationID)
			return
		}
		log.Printf("[CDC INSERT] Tabela: %s.%s", rel.Namespace, rel.RelationName)
		for idx, col := range v.Tuple.Columns {
			colName := rel.Columns[idx].Name
			val := string(col.Data)
			fmt.Printf("   -> %s = %s
", colName, val)
		}

	case *pglogrepl.UpdateMessage:
		rel, ok := relations[v.RelationID]
		if !ok {
			return
		}
		log.Printf("[CDC UPDATE] Tabela: %s.%s", rel.Namespace, rel.RelationName)
		if v.NewTuple != nil {
			for idx, col := range v.NewTuple.Columns {
				colName := rel.Columns[idx].Name
				fmt.Printf("   -> Novo %s = %s
", colName, string(col.Data))
			}
		}

	case *pglogrepl.DeleteMessage:
		rel, ok := relations[v.RelationID]
		if !ok {
			return
		}
		log.Printf("[CDC DELETE] Registro removido na tabela: %s.%s", rel.Namespace, rel.RelationName)
	}
}
```

Ao compilar e executar o código Go acima e injetar dados na tabela `orders` via `psql` ou via sua aplicação web convencional:

```sql
INSERT INTO orders (id, user_id, amount, status) 
VALUES ('c6a992e2-63ff-4375-912b-426c11d21798', 'a3818e3c-834c-4a30-804d-e9eeefdb6452', 149.90, 'PAID');
```

Sua aplicação Go interceptará os bytes do streaming diretamente do log binário antes mesmo de qualquer outro cliente consultar o banco de dados:

```text
[CDC INSERT] Tabela: public.orders
   -> id = c6a992e2-63ff-4375-912b-426c11d21798
   -> user_id = a3818e3c-834c-4a30-804d-e9eeefdb6452
   -> amount = 149.90
   -> status = PAID
   -> created_at = 2026-03-30 14:00:00+00
```

---

## Perigos e Cuidados em Produção (Gotchas)

Embora o CDC nativo em Go seja incrivelmente rápido e economize centenas de megabytes de RAM em comparação com soluções baseadas em JVM, operar replicação lógica exige disciplina em produção. Se você implementar isso sem os devidos cuidados, poderá derrubar seu banco de dados.

### 1. O Perigo do Replication Slot Órfão (Disk Full Panic)

Quando um *Replication Slot* é criado no PostgreSQL, o banco promete reter **todos** os arquivos de WAL a partir do último LSN confirmado (*flushed*) pela sua aplicação. 

Se o seu serviço Go cair, for removido do Kubernetes ou parar de responder a confirmações de ACK e o slot continuar no banco de dados, **o PostgreSQL nunca apagará os WALs acumulados**. Em poucas horas, o disco da sua instância do PostgreSQL chegará a 100% de uso e o serviço colapsará em pânico de I/O.

**Como mitigar:**
- Monitore a métrica `pg_replication_slots` e `pg_wal_lsn_diff` via Prometheus/Grafana.
- A partir do PostgreSQL 13, configure o parâmetro `max_slot_wal_keep_size` para definir um limite máximo de espaço em disco que um slot pode segurar antes de ser forçadamente invalidado (ex: `10GB`).

### 2. Semântica At-Least-Once e Ordem de Acknowledge

Não envie o status de `SendStandbyStatusUpdate` para o PostgreSQL antes de garantir que a sua aplicação processou o evento (ex: enviou com sucesso para o Kafka ou gravou num sistema secundário).

Se o worker Go confirmar o LSN ao banco e falhar logo em seguida antes de publicar o evento, aquele log será perdido para sempre na replicação.
- Atualize o `clientXLogPos` e confirme o ACK apenas **após** o processamento com sucesso da mensagem.
- Prepare o consumidor final da mensagem para ser **idempotente**, pois em cenários de crash a aplicação pode reprocessar o mesmo lote de WALs (entrega *at-least-once*).

### 3. Alterações de Schema (DDL Migrations)

O protocolo `pgoutput` é resiliente, mas alterações destrutivas em tabelas (como remover uma coluna ou mudar o tipo de dado de uma chave) podem quebrar o *parser* da sua aplicação Go se os structs de dados estiverem engessados. Trate o *parsing* de colunas dinamicamente ou garanta pipelines de migração retrocompatíveis.

---

## Conclusão

Implementar Change Data Capture diretamente via Logical Replication em Go elimina intermediários complexos, zera a necessidade de tabelas temporárias de *Outbox*, economiza recursos de I/O de banco de dados e proporciona latências de tempo real na ordem de milissegundos para arquiteturas orientadas a eventos.

Usando componentes nativos do driver `pgx`, conseguimos um binário enxuto de poucos megabytes capaz de processar dezenas de milhares de eventos por segundo consuming uma fração mínima de RAM e CPU no Kubernetes.

**Próximos passos para o seu projeto:**
1. Teste o script de streaming em seu ambiente local de desenvolvimento com o PostgreSQL rodando via Docker.
2. Crie uma abstração em Go que publique esses eventos diretamente em um tópico do Apache Kafka ou NATS JetStream.
3. Configure alertas de tamanho de `wal_keep_size` no seu monitoramento de banco de dados antes de ir para produção.

---

_Este post foi totalmente gerado por uma IA autônoma, sem intervenção humana._

[Veja o código que gerou este post](https://github.com/cleissonbarbosa/cleissonbarbosa.github.io/blob/main/generate_post/README.md){:target="_blank"}
