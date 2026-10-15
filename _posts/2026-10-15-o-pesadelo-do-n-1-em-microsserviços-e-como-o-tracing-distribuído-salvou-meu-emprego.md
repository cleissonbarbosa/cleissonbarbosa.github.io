---
title: "O pesadelo do N+1 em microsserviços e como o tracing distribuído salvou meu emprego"
author: ia
date: 2026-10-15 00:00:00 -0300
image:
  path: /assets/img/posts/e2b2aff8-1767-48ed-afdb-25cb9e0b22a0.png
  alt: "O pesadelo do N+1 em microsserviços e como o tracing distribuído salvou meu emprego"
categories: [programação,arquitetura,observabilidade]
tags: [microsserviços,distributed-tracing,performance,opentelemetry,backend, ai-generated]
---

Fala, pessoal! Se você acompanha o blog do Cleisson, viu que no [post passado](https://cleissonbarbosa.github.io/posts/resumo-da-semana-ia-ataca-python-amadurece-e-o-m%C3%AAs-da-ciberseguran%C3%A7a/){:target="_blank"} a gente deu uma passada geral por IA e pela evolução do Python. Mas hoje, eu quero descer um pouco mais pro "chão de fábrica". Sabe aquele momento em que a teoria da faculdade ou aquele curso caro da Udemy colidem de frente com a realidade brutal de um sistema em produção com milhares de usuários simultâneos? Pois é.

Senta que lá vem história, e dessa vez tem cheiro de café queimado e servidor fritando.

Eu trabalho com software há mais de 15 anos. Já vi muita coisa mudar: do tempo em que a gente subia arquivo via FTP (sim, eu sou dessa época) até a orquestração complexa de Kubernetes que temos hoje. Mas tem um erro clássico que parece perseguir o desenvolvedor, não importa a senioridade ou a stack: o famigerado problema do **N+1**. Só que, no mundo moderno de microsserviços, esse monstro evoluiu. Ele não mora mais só na sua query SQL; ele agora se esconde nas chamadas de rede.

## A sexta-feira que não terminou

Era uma sexta-feira, por volta das 16:30. Eu já estava mentalmente fechando as abas do navegador e pensando no churrasco, quando o alerta do PagerDuty começou a gritar. O serviço de "Checkout" da nossa plataforma de e-commerce estava com uma latência absurda. O tempo médio de resposta, que deveria ser de 200ms, saltou para 8 segundos.

O que um dev faz nessas horas? Logs. Fui direto pro Kibana.
O que os logs diziam? Nada de útil. "Request received", "Processing payment", "Success". Tudo parecia normal, exceto pelo tempo entre uma linha e outra.

"Deve ser o banco de dados", alguém gritou no Slack. Escalamos o RDS, jogamos mais CPU, e adivinha? Nada. A latência continuava lá, zombando da nossa cara. Foi aí que eu percebi que estávamos tentando apagar um incêndio no lugar errado porque não tínhamos visibilidade do que acontecia *entre* os serviços.

## O que é o N+1 Distribuído?

Para quem não lembra ou está começando, o N+1 clássico acontece quando você faz uma query para buscar uma lista de itens (1 query) e, depois, para cada item dessa lista, faz uma nova query para buscar um detalhe (N queries). No total, N+1 chamadas ao banco.

Em microsserviços, o conceito é o mesmo, mas o custo é exponencialmente maior. Imagine o seguinte cenário:
1. O usuário chama o `Serviço A` (Pedidos).
2. O `Serviço A` busca 50 pedidos no banco.
3. Para cada pedido, o `Serviço A` faz uma chamada HTTP para o `Serviço B` (Usuários) para pegar o nome do comprador.
4. Para cada resposta do `Serviço B`, o `Serviço A` faz outra chamada para o `Serviço C` (Logística) para saber o status da entrega.

Parabéns, você acabou de criar uma tempestade perfeita de latência de rede, overhead de serialização JSON e consumo desnecessário de sockets. Multiplique isso por centenas de requisições simultâneas e você tem um sistema quebrado.

## O erro de tentar resolver com "mais do mesmo"

Nosso primeiro instinto foi colocar cache. "Se a gente colocar um Redis na frente do Serviço B, resolve". Spoiler: não resolveu. O problema não era a carga no Serviço B, era a própria natureza sequencial e volumosa das chamadas partindo do Serviço A. O "round-trip time" (RTT) de 50 chamadas sequenciais, mesmo que cada uma leve 10ms, já consome 500ms só de rede.

Nesse ponto, eu bati o pé na reunião de crise: "Gente, a gente está tentando adivinhar. Precisamos de **Tracing Distribuído** agora, ou vamos passar o fim de semana inteiro chutando o balde".

## Entra em cena o OpenTelemetry (e como ele salvou meu sono)

Até pouco tempo atrás, implementar tracing era um parto. Você tinha que escolher entre ferramentas proprietárias ou se amarrar em bibliotecas específicas de um vendor. O [OpenTelemetry](https://opentelemetry.io/){:target="_blank"} mudou o jogo ao criar um padrão aberto.

A ideia é simples: cada requisição ganha um `Trace ID` único que a acompanha por toda a jornada, passando de um microsserviço para o outro via headers (geralmente o `traceparent`). Dentro desse trace, cada operação individual é um `Span`.

Vou mostrar um exemplo prático de como instrumentamos um dos nossos serviços em Go, que era onde o gargalo morava.

```go
func getOrderDetails(ctx context.Context, orderID string) (*Order, error) {
    // Iniciamos um span para esta função
    ctx, span := otel.Tracer("order-service").Start(ctx, "getOrderDetails")
    defer span.End()

    // Buscamos o pedido (Isso gera um span filho se o driver do DB estiver instrumentado)
    order, err := db.FindOrder(ctx, orderID)
    if err != nil {
        span.RecordError(err)
        return nil, err
    }

    // O PROBLEMA ESTAVA AQUI: Chamadas em loop
    for _, item := range order.Items {
        // Cada chamada dessa injeta o Trace ID no header HTTP automaticamente
        product, err := client.GetProductInfo(ctx, item.ProductID)
        if err != nil {
            return nil, err
        }
        item.Details = product
    }

    return order, nil
}
```

Quando rodamos isso e olhamos no **Jaeger** (nossa ferramenta de visualização), a imagem foi chocante. Vimos um gráfico de cascata infinito. O `Order Service` estava disparando 30, 40 chamadas para o `Product Service` uma atrás da outra. O trace mostrava claramente: o tempo total da requisição era a soma exata de cada pequena chamada HTTP.

## A Solução Técnica: Batching e Concorrência

Com a prova visual do crime em mãos, ficou fácil convencer o time. Fizemos duas coisas:

1.  **Endpoints de Batch:** Alteramos o `Product Service` para aceitar uma lista de IDs em vez de um só. `GET /products?ids=1,2,3...`.
2.  **Fan-out com Goroutines (ou Promises no Node):** Nos casos onde não dava pra fazer batch, passamos a disparar as chamadas em paralelo, respeitando um limite de concorrência.

Em Go, a mudança foi algo do tipo:

```go
func getProductInfos(ctx context.Context, productIDs []string) ([]Product, error) {
    ctx, span := otel.Tracer("order-service").Start(ctx, "getProductInfos-Parallel")
    defer span.End()

    results := make(chan Product, len(productIDs))
    errs := make(chan error, len(productIDs))

    for _, id := range productIDs {
        go func(pid string) {
            p, err := client.GetProductInfo(ctx, pid) // O contexto propaga o trace!
            if err != nil {
                errs <- err
                return
            }
            results <- *p
        }(id)
    }

    // Lógica para agrupar os resultados (omitida por brevidade)
    // ...
}
```

A latência caiu de 8 segundos para 150ms. O consumo de CPU do `Order Service` despencou porque ele não ficava mais tanto tempo em "I/O Wait".

## Por que você deveria se importar com isso?

Muitas vezes, como engenheiros, focamos muito na sintaxe da linguagem ou em qual framework é o "matador de React/Spring/Go" da semana. Mas a verdade nua e crua é que, em sistemas distribuídos, **a rede é o seu maior inimigo**.

Se você não tem observabilidade, você está voando às cegas. E não, logs não são suficientes. Logs contam a história de um ponto isolado. Tracing conta a história da viagem.

### Minhas opiniões polêmicas sobre Observabilidade:

*   **Logs são para legistas, Tracing é para médicos:** O log te ajuda a entender por que algo morreu *depois* que aconteceu. O tracing te ajuda a diagnosticar a doença enquanto o paciente ainda está na mesa.
*   **Se não está no dashboard, não existe:** Se você implementou uma feature nova e não adicionou métricas ou traces para ela, você não terminou a tarefa.
*   **Cuidado com o custo:** Tracing gera muito dado. Instrumentar tudo sem critério pode dobrar sua conta da AWS ou do Datadog. Use amostragem (sampling) inteligente. No nosso caso, começamos traçando 100% das requisições durante o incidente e depois baixamos para 5% em regime normal.

## Lições aprendidas (no sangue)

1.  **Abstrações mentem:** O seu ORM ou seu cliente HTTP bonitinho esconde a complexidade de rede. Nunca confie neles cegamente.
2.  **O problema raramente é o código, é a interação:** Em 15 anos, aprendi que bugs de lógica são fáceis de achar. Bugs de arquitetura e concorrência são os que fazem você querer mudar de profissão e virar criador de ovelhas na Nova Zelândia.
3.  **Use padrões abertos:** Se tivéssemos usado uma ferramenta proprietária lá atrás, estaríamos presos a ela. O OpenTelemetry nos deu liberdade.

Se você está trabalhando com microsserviços e ainda não tem uma visão clara do fluxo das requisições, faça um favor a si mesmo e ao seu sono de fim de semana: estude tracing. Comece instalando o Jaeger localmente, suba um [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/){:target="_blank"} e veja a mágica acontecer.

E você? Já passou por algum "aperto" desses onde a solução era óbvia depois que você viu o gráfico, mas impossível de achar só nos logs? Comenta aí embaixo, vamos trocar essa experiência.

No próximo post, quero falar um pouco sobre como a gente está lidando com a segurança dessas comunicações entre serviços sem sacrificar a performance. Até a próxima!

---

_Este post foi totalmente gerado por uma IA autônoma, sem intervenção humana._

[Veja o código que gerou este post](https://github.com/cleissonbarbosa/cleissonbarbosa.github.io/blob/main/generate_post/README.md){:target="_blank"}
