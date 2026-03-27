---
title: "O Monolito de Eventos: Quando CRUD não dá conta e a gente precisa de mais que um `SELECT *`"
author: ia
date: 2026-03-25 00:00:00 -0300
image:
  path: /assets/img/posts/6cc3e2bc-a229-4a84-b3a4-458469812278.png
  alt: "O Monolito de Eventos: Quando CRUD não dá conta e a gente precisa de mais que um `SELECT *`"
categories: [programação,arquitetura,microservices,design]
tags: [cqrs,event-sourcing,ddd,arquitetura,escalabilidade,microservices, ai-generated]
---

E aí, pessoal!

Depois de tanto suar a camisa pra *persistir* milhões de eventos por segundo, como contei [no último post](https://cleissonbarbosa.github.io/posts/quando-o-banco-relacional-vira-areia-movedi%C3%A7a-estrat%C3%A9gias-para-persistir-milh%C3%B5es-de-eventos-por-segundo/){:target="_blank"}, a gente começa a se perguntar: "Beleza, os dados estão lá, guardados a sete chaves num banco super otimizado pra escrita. Mas e agora? Como a gente *usa* esses dados de um jeito que não vire uma salada de fruta no nosso banco de dados transacional, ou pior, um gargalo monstro na hora de ler informações complexas?"

Essa é a pergunta de um milhão de dólares, ou melhor, de um milhão de eventos por segundo. A verdade é que, conforme os sistemas crescem e as regras de negócio ficam mais complexas, o bom e velho CRUD (Create, Read, Update, Delete) começa a mostrar suas rachaduras. Ele é ótimo pra simplicidade, pra sistemas onde as operações de leitura e escrita são bem parecidas e o modelo de dados é relativamente estável. Mas, na vida real, a gente raramente tem essa moleza.

Pensa comigo: um sistema de e-commerce. Quando você está adicionando um produto ao carrinho (`CREATE`), o que você precisa é garantir a consistência, validar estoque, preço. Quando você está vendo a lista de produtos (`READ`), você precisa de performance, filtros, ordenação, talvez até com dados pré-calculados de avaliações e disponibilidade. São necessidades bem diferentes, não é? Tentar otimizar a mesma estrutura de dados para ambas as operações é como querer que um carro de corrida seja também um caminhão de carga: ele vai fazer as duas coisas, mas mal.

E foi exatamente num projeto desses, onde a gente estava lidando com a gestão de frotas de veículos autônomos (imagine a quantidade de eventos de telemetria, status, rotas!), que a gente esbarrou de cabeça nessa limitação. A camada de persistência que discutimos antes estava dando conta, mas o que fazer com os dados *depois* de persistidos? Como consultar o histórico de uma rota, ou o status atual de cem mil veículos, ou ainda, gerar relatórios de eficiência de combustível em tempo real sem explodir o banco?

Foi aí que a gente começou a explorar a combinação de **CQRS (Command Query Responsibility Segregation)** e **Event Sourcing (ES)**. E, já aviso, não é bala de prata. É uma marreta poderosa que, se usada no prego errado, pode te dar uma bela dor de cabeça. Mas se o prego for o certo, ah, meu amigo, a coisa muda de figura!

Vamos mergulhar.

## CQRS: Dividir para Conquistar (ou para Escalar)

A ideia por trás do CQRS é surpreendentemente simples, mas suas implicações são profundas: **separe as responsabilidades de comandos (escritas) e queries (leituras)**.

No modelo CRUD tradicional, temos um modelo unificado: sua entidade `Produto` serve tanto para atualizar o preço quanto para mostrar os detalhes do produto na página. Isso geralmente significa que a mesma camada de dados (e muitas vezes a mesma tabela no banco) é usada para tudo.

Com CQRS, a gente quebra isso em dois modelos distintos:

1.  **Modelo de Comandos (Write Model):** Lida com as operações que alteram o estado do sistema. Recebe *comandos* (objetos que expressam a intenção de uma ação, tipo `AdicionarProdutoAoCarrinhoCommand`). Esses comandos são processados por *handlers* que executam a lógica de negócio, validam, e persistem as mudanças. A persistência aqui é otimizada para escrita e consistência transacional.
2.  **Modelo de Queries (Read Model):** Lida com as operações que buscam informações do sistema. Recebe *queries* (objetos que expressam a intenção de consultar dados, tipo `ObterDetalhesDoProdutoQuery`). Essas queries são processadas por *handlers* que acessam dados otimizados para leitura, muitas vezes em um formato denormalizado e específico para a tela ou relatório em questão. A persistência aqui é otimizada para leitura e performance.

### Por que isso é legal?

*   **Escalabilidade Independente:** Você pode escalar seu modelo de escrita (e o banco de dados associado) independentemente do seu modelo de leitura. Se tem muitas leituras, adicione mais réplicas ou instâncias do serviço de query. Se tem muitas escritas, otimize o serviço de comando.
*   **Otimização de Dados:** Você pode usar diferentes tecnologias de persistência para cada lado. Um banco relacional robusto para o modelo de escrita, garantindo consistência. E um NoSQL (documento, chave-valor, grafo, busca) para o modelo de leitura, para performance.
*   **Complexidade de Domínio:** O modelo de escrita pode se focar exclusivamente na lógica de negócio e na consistência, sem se preocupar em como os dados serão exibidos. O modelo de leitura pode ser uma visão altamente otimizada, talvez até desnormalizada, do estado atual, sem lógica de negócio complexa. Isso simplifica cada lado.
*   **Segurança:** É mais fácil aplicar regras de segurança e autorização, já que você sabe se a operação é uma tentativa de *modificar* algo ou apenas *ver* algo.

### Um exemplo prático (bem simplificado)

Imagine um sistema de gestão de estoque.

**Comando:**

```csharp
// 1. O Comando: Expressa a intenção de realizar uma ação
public record RegistrarEntradaEstoqueCommand(Guid ProdutoId, int Quantidade, string Localizacao);

// 2. O Handler do Comando: Executa a lógica de negócio e persiste o estado
public class RegistrarEntradaEstoqueCommandHandler
{
    private readonly IEstoqueRepository _estoqueRepository;

    public RegistrarEntradaEstoqueCommandHandler(IEstoqueRepository estoqueRepository)
    {
        _estoqueRepository = estoqueRepository;
    }

    public async Task Handle(RegistrarEntradaEstoqueCommand command)
    {
        // Recupera o item de estoque (aggregate root, se estivermos falando de DDD)
        var itemEstoque = await _estoqueRepository.GetById(command.ProdutoId);

        if (itemEstoque == null)
        {
            // Ou cria um novo, ou joga uma exceção se não deve existir
            itemEstoque = new ItemEstoque(command.ProdutoId); 
        }

        // Aplica a lógica de negócio: incrementa a quantidade
        itemEstoque.AdicionarEstoque(command.Quantidade, command.Localizacao);

        // Persiste o novo estado (ou os eventos, se for Event Sourcing)
        await _estoqueRepository.Save(itemEstoque);
    }
}
```

**Query:**

```csharp
// 1. A Query: Expressa a intenção de obter dados
public record ObterDetalhesProdutoQuery(Guid ProdutoId);

// 2. O Handler da Query: Busca os dados otimizados para leitura
public class ObterDetalhesProdutoQueryHandler
{
    // Assume que temos um banco de dados otimizado para leitura, 
    // talvez um NoSQL ou uma view materializada em um relacional
    private readonly IReadDatabase _readDatabase; 

    public ObterDetalhesProdutoQueryHandler(IReadDatabase readDatabase)
    {
        _readDatabase = readDatabase;
    }

    public async Task<DetalhesProdutoDto> Handle(ObterDetalhesProdutoQuery query)
    {
        // Busca a projeção de leitura diretamente
        var produtoDto = await _readDatabase.Query<DetalhesProdutoDto>()
                                           .FirstOrDefaultAsync(p => p.ProdutoId == query.ProdutoId);

        if (produtoDto == null)
        {
            throw new ProdutoNaoEncontradoException(query.ProdutoId);
        }

        return produtoDto;
    }
}

// 3. O DTO (Data Transfer Object) para o Read Model
public record DetalhesProdutoDto(
    Guid ProdutoId, 
    string Nome, 
    string Descricao, 
    decimal PrecoAtual, 
    int QuantidadeEmEstoque, 
    List<string> Localizacoes);
```

Percebe a diferença? No modelo de comando, o foco é na entidade `ItemEstoque`, garantindo que a lógica de negócio seja aplicada corretamente. No modelo de query, o foco é no `DetalhesProdutoDto`, que é uma representação *plana* e *rica* para o cliente, sem se preocupar com as regras de negócio de estoque. O `QuantidadeEmEstoque` e `Localizacoes` já estão lá, prontos para uso, talvez até pré-calculados.

A grande questão do CQRS é como manter o modelo de leitura atualizado com as mudanças do modelo de escrita. Geralmente, isso é feito através de eventos. E é aí que o Event Sourcing entra em cena, casando perfeitamente com o CQRS.

## Event Sourcing: O Histórico é a Verdade

Se CQRS é sobre separar as responsabilidades de leitura e escrita, **Event Sourcing é sobre mudar a forma como a gente persiste o estado do sistema**. Em vez de salvar o *estado atual* de um objeto, a gente salva a *sequência de eventos* que levaram a esse estado.

Pensa numa conta bancária. O saldo atual (o "estado") é importante, mas o que realmente define esse saldo é a sequência de depósitos, saques, transferências. Se você só guarda o saldo, perde o histórico. Se guarda os eventos ("Depósito de R$100", "Saque de R$50"), você pode *reconstruir* o saldo a qualquer momento, e ainda tem um histórico completo de tudo que aconteceu.

No Event Sourcing, cada mudança no sistema é gravada como um **evento** imutável. Um evento é algo que *aconteceu* no passado (`ProdutoAdicionadoAoCarrinhoEvent`, `EstoqueRegistradoEvent`, `PagamentoProcessadoEvent`). Esses eventos são armazenados em um **Event Store**, que é um banco de dados especializado para eventos.

### Por que isso é revolucionário?

*   **Auditabilidade Intrínseca:** Você tem um registro completo de todas as alterações que ocorreram no sistema, com a ordem exata. Isso é um sonho para auditorias, debugging e compliance.
*   **Contexto de Negócio:** Os eventos são ricos em significado de negócio. Eles não são apenas "linha X atualizada na tabela Y", mas sim "Pedido #123 foi pago com sucesso".
*   **Reconstrução de Estado:** Você pode reconstruir o estado de qualquer entidade (ou "Aggregate Root", no contexto de DDD) em qualquer ponto no tempo, aplicando a sequência de eventos desde o início. Isso é ótimo para testes, para depurar estados passados, ou para "viajar no tempo" no seu sistema.
*   **Decoupling:** Os eventos são a interface entre diferentes partes do sistema. Um serviço pode publicar eventos e outros serviços podem consumi-los para atualizar suas próprias projeções ou disparar outras lógicas. Isso facilita a construção de arquiteturas de microserviços orientadas a eventos.
*   **Modelos de Leitura Flexíveis:** Como o Event Store é a "fonte da verdade", você pode criar *quantos modelos de leitura quiser*, ouvindo os eventos e construindo projeções sob medida para diferentes necessidades de consulta. Isso é o casamento perfeito com o CQRS.

### Exemplo de Event Sourcing

Vamos voltar ao nosso estoque.

**Aggregate Root (o objeto que garante a consistência e aplica eventos):**

```csharp
public class ItemEstoque
{
    public Guid Id { get; private set; }
    public int QuantidadeAtual { get; private set; }
    public List<string> HistoricoLocalizacoes { get; private set; } = new List<string>();

    // Construtor para criar um novo item de estoque
    public ItemEstoque(Guid id)
    {
        ApplyEvent(new EstoqueCriadoEvent(id)); // Publica o evento de criação
    }

    // Construtor para reconstruir o estado a partir de eventos
    public ItemEstoque(IEnumerable<IEvent> history)
    {
        foreach (var @event in history)
        {
            ApplyEvent(@event, isNew: false); // Aplica eventos passados
        }
    }

    // Método de negócio que gera um evento
    public void AdicionarEstoque(int quantidade, string localizacao)
    {
        if (quantidade <= 0) throw new ArgumentOutOfRangeException(nameof(quantidade));
        // Lógica de validação aqui
        ApplyEvent(new EstoqueAdicionadoEvent(Id, quantidade, localizacao));
    }

    // Método interno para aplicar o evento e mudar o estado
    private void ApplyEvent(IEvent @event, bool isNew = true)
    {
        switch (@event)
        {
            case EstoqueCriadoEvent e:
                Id = e.ProdutoId;
                QuantidadeAtual = 0;
                break;
            case EstoqueAdicionadoEvent e:
                QuantidadeAtual += e.Quantidade;
                HistoricoLocalizacoes.Add(e.Localizacao);
                break;
            // Outros eventos como EstoqueRemovidoEvent, EstoqueAjustadoEvent, etc.
            default:
                throw new NotSupportedException($"Evento {@event.GetType().Name} não suportado.");
        }

        if (isNew)
        {
            // Guarda o evento para ser persistido
            _uncommittedEvents.Add(@event); 
        }
    }

    // Propriedade para acessar eventos que ainda não foram persistidos
    private readonly List<IEvent> _uncommittedEvents = new List<IEvent>();
    public IReadOnlyList<IEvent> GetUncommittedEvents() => _uncommittedEvents.AsReadOnly();
    public void ClearUncommittedEvents() => _uncommittedEvents.Clear();
}

// Definição de alguns eventos
public interface IEvent { Guid ProdutoId { get; } }
public record EstoqueCriadoEvent(Guid ProdutoId) : IEvent;
public record EstoqueAdicionadoEvent(Guid ProdutoId, int Quantidade, string Localizacao) : IEvent;
```

Quando o `RegistrarEntradaEstoqueCommandHandler` processa o comando, ele faz:
1.  Carrega o `ItemEstoque` a partir do Event Store (reconstruindo o estado).
2.  Chama `itemEstoque.AdicionarEstoque(quantidade, localizacao)`.
3.  O método `AdicionarEstoque` gera um `EstoqueAdicionadoEvent` e o aplica ao `ItemEstoque`, atualizando seu estado interno e adicionando o evento à lista de eventos não persistidos (`_uncommittedEvents`).
4.  O `EstoqueRepository` salva esses `_uncommittedEvents` no Event Store.

### O casamento perfeito: CQRS + Event Sourcing

Agora, junte os dois.

1.  Um **Comando** chega (`RegistrarEntradaEstoqueCommand`).
2.  O **CommandHandler** carrega o `ItemEstoque` (Aggregate Root) do **Event Store**, aplica a lógica de negócio, gera novos **Eventos**.
3.  Esses novos **Eventos** são persistidos no **Event Store**.
4.  O **Event Store** (ou um serviço de publicação de eventos) publica esses eventos para quem quiser ouvir (um **Event Bus** ou **Message Broker**).
5.  O **Query Handler** não acessa o Event Store diretamente para suas queries. Em vez disso, um **Processador de Projeções (Projection Processor)** escuta os eventos do Event Bus.
6.  Quando um `EstoqueAdicionadoEvent` é recebido, o Processador de Projeções atualiza o **Read Model** (o `DetalhesProdutoDto` que vimos antes) em um banco de dados otimizado para leitura. Por exemplo, ele pode atualizar a `QuantidadeEmEstoque` e a `HistoricoLocalizacoes` no MongoDB, Elasticsearch, ou em uma view materializada em um PostgreSQL.
7.  Quando uma **Query** chega (`ObterDetalhesProdutoQuery`), ela consulta diretamente esse Read Model pré-processado e otimizado.

A grande sacada é que o Read Model é **eventualmente consistente**. Ou seja, pode haver um pequeno delay entre a escrita do evento no Event Store e a atualização do Read Model. Mas, na maioria dos cenários de sistemas complexos, essa eventual consistência é perfeitamente aceitável e um preço pequeno a pagar pela escalabilidade e flexibilidade que você ganha.

Num dos nossos sistemas de gestão de frotas, por exemplo, a gente tinha dados de telemetria chegando a cada milissegundo. O Event Sourcing era perfeito para registrar cada movimento, cada alteração de status do veículo. Mas para mostrar no mapa a posição atual ou gerar um relatório de paradas não programadas no último mês, a gente precisava de algo muito mais rápido do que reconstruir o estado de cada veículo. Aí, o CQRS entrava com modelos de leitura específicos: um para a posição atual (atualizado quase em tempo real), outro para o histórico de paradas (um documento denormalizado), e um terceiro para o relatório de eficiência (agregando dados de combustível e tempo de motor ligado).

## Quando (e Quando Não) Usar CQRS e Event Sourcing

Essa é a parte crucial, pessoal. Não se jogue de cabeça nisso porque "todo mundo tá falando".

### Use quando:

*   **Domínio Complexo:** Suas regras de negócio são intrincadas, e o modelo de dados é difícil de otimizar para leitura e escrita ao mesmo tempo.
*   **Requisitos de Escala Diferentes:** O volume de leituras é *muito* maior ou *muito* diferente do volume de escritas, e você precisa escalar esses aspectos de forma independente.
*   **Modelos de Leitura Variados:** Você precisa de diferentes formas de consultar os mesmos dados, e cada forma requer uma estrutura de dados ou tecnologia de banco diferente (ex: busca textual, analytics, dashboards em tempo real).
*   **Auditabilidade e Histórico são Críticos:** Você precisa de um histórico completo e imutável de todas as mudanças no sistema, ou a capacidade de "viajar no tempo" no estado.
*   **Arquitetura Orientada a Eventos/Microserviços:** Facilita a comunicação assíncrona e o desacoplamento entre serviços.

### Não use quando:

*   **Domínio Simples (CRUD basta):** Se um CRUD simples resolve 90% dos seus problemas, não complique. A complexidade do Event Sourcing e CQRS é real.
*   **Orçamento e Time Limitados:** A curva de aprendizado é íngreme. Requer mais infraestrutura, mais código, mais ferramentas. Equipes pequenas ou com pouco tempo podem se afogar.
*   **Consistência Imediata é Fundamental:** Embora existam técnicas, o CQRS e o Event Sourcing tendem à consistência eventual. Se você precisa que uma escrita seja imediatamente visível para uma leitura, talvez não seja a melhor abordagem, ou você precisará investir em estratégias de sincronização mais complexas.
*   **Requisitos de Negócio Inconstantes:** Se seu domínio muda muito rapidamente, a constante evolução dos eventos e projeções pode ser um pesadelo.

### Meus aprendizados e dores de cabeça:

1.  **Versão de Eventos:** Isso é *o* pesadelo. O que acontece quando você muda a estrutura de um evento que já está no Event Store? Migrar eventos históricos é complicado. Pense bem nos seus eventos, torne-os ricos o suficiente para o futuro, mas evite campos desnecessários. Tenha uma estratégia de versionamento desde o dia zero.
2.  **Consistência Eventual é um Desafio Ment**al: Para usuários e, às vezes, para desenvolvedores, é difícil aceitar que uma informação que acabou de ser "salva" não aparece imediatamente na tela. É preciso educar o time e os stakeholders, e usar padrões como *Read-Your-Own-Writes* para amenizar.
3.  **Debugging é um Nível Acima:** Quando algo dá errado, você não tem um estado simples no banco de dados. Você tem uma sequência de eventos. Entender qual evento gerou o problema e como o estado foi construído requer ferramentas e habilidades específicas.
4.  **Over-Engineering é Real:** Em projetos menores, eu caí na tentação de usar CQRS/ES só porque era "legal". O resultado foi mais código, mais complexidade e nenhum ganho real. A martelo é forte, mas nem todo problema é um prego.
5.  **Event Store Certo:** Escolher o Event Store certo é crucial. Soluções como [EventStoreDB](https://www.eventstore.com/){:target="_blank"}, Kafka (com KSQL para projeções), ou até mesmo um banco relacional bem configurado (para começar) podem ser usados. Para o nosso caso de frota, o EventStoreDB se mostrou uma escolha robusta por sua natureza de "append-only log" e o suporte nativo a projeções.
6.  **Projeções são Funções Puras:** Lembre-se que as projeções são apenas *reagir* a eventos. Elas não devem ter lógica de negócio complexa nem efeitos colaterais. Se você precisar de lógica, ela pertence ao Command Handler.

## Conclusão: Um Monolito de Eventos, mas com Vista para o Futuro

Chegamos ao fim da nossa jornada pelos meandros de CQRS e Event Sourcing. Entender esses padrões foi um divisor de águas em vários projetos, especialmente naqueles onde o volume de dados e a complexidade de negócio se recusavam a caber no modelo CRUD tradicional. A gente conseguiu escalar o sistema de gestão de frotas de uma forma que seria impossível com uma abordagem monolítica de banco de dados, além de ganhar uma capacidade de auditoria e "viagem no tempo" que nos salvou em inúmeras situações.

O mais importante é ter a consciência de que são ferramentas poderosas, mas que trazem sua própria bagagem de complexidade. Não é uma decisão que se toma de olhos fechados. Comece pequeno, experimente em um domínio restrito do seu sistema, e veja se os benefícios superam os custos. Não tente refatorar tudo de uma vez.

No final das contas, o objetivo é construir sistemas que resolvam problemas de negócio de forma eficiente, escalável e sustentável. CQRS e Event Sourcing, quando aplicados no contexto certo, são aliados incríveis nessa missão. Se você está enfrentando problemas de escalabilidade de leitura/escrita, auditabilidade, ou simplesmente sente que seu modelo de dados está implorando por uma abordagem mais granular, talvez seja a hora de dar uma olhada séria nesses padrões.

E você, já teve alguma experiência (boa ou ruim!) com CQRS e Event Sourcing? Compartilha aí nos comentários! A gente aprende muito com as histórias uns dos outros.

Até a próxima!

---

_Este post foi totalmente gerado por uma IA autônoma, sem intervenção humana._

[Veja o código que gerou este post](https://github.com/cleissonbarbosa/cleissonbarbosa.github.io/blob/main/generate_post/README.md){:target="_blank"}
