---
title: "Concorrência e Locks no PostgreSQL: Por que seu SELECT FOR UPDATE está matando o throughput"
author: ia
date: 2026-10-24 21:05:42 -0300
description: "Entenda como o MVCC, lock queues e níveis de isolamento funcionam no PostgreSQL para resolver gargalos de concorrência sem travar sua aplicação."
image:
  path: /assets/img/posts/ff5ad051-bcd8-41c4-931d-e550d6b79693.png
  alt: "Concorrência e Locks no PostgreSQL: Por que seu SELECT FOR UPDATE está matando o throughput"
categories: ["programação", "banco de dados"]
tags: ["postgresql", "sql", "performance", "backend", "concorrencia", "ai-generated"]
---

Você já deve ter passado por isso: a aplicação passa nos testes de carga sintéticos com louvor, a infraestrutura tem CPU e memória de sobra, mas basta entrar um pico de usuários simultâneos tentando atualizar o mesmo recurso para a latência escalar de 15 milissegundos para 4 segundos. Os pods do Kubernetes começam a acumular requisições, o pool de conexões esgota e o monitor de métricas aponta CPU em míseros 18%. 

A primeira reação da maioria dos times é aumentar o pool de conexões ou subir a máquina do banco. Alerta de spoiler: isso só piora a situação. 

No post anterior sobre [WebAssembly no server](https://cleissonbarbosa.github.io/posts/webassembly-no-server-onde-a-performance-encontra-a-leveza-e-por-que-voce/){:target="_blank"}, comentei sobre a nossa eterna busca por eficiência e menor overhead de execução. Só que de nada adianta ter um runtime ultraleve e uma API em Rust ou Go respondendo em microssegundos se a sua camada de persistência estiver enfileirada em esperas passivas por locks de linha. 

Vamos dissecar o que realmente acontece debaixo do capô do PostgreSQL quando múltiplos clientes tentam manipular os mesmos registros simultaneamente, por que o clássico `SELECT ... FOR UPDATE` é frequentemente mal utilizado e quais são as ferramentas nativas para desenhar fluxos concorrentes de alta performance.

---

## MVCC não é passe livre para concorrência cega

Quase todo desenvolvedor backend sabe que o PostgreSQL usa **MVCC** (*Multi-Version Concurrency Control*). O mantra repetido em tutoriais é simples: *"leitores não bloqueiam escritores, e escritores não bloqueiam leitores"*. Isso é verdade para operações puras de `SELECT` e `UPDATE`/`INSERT`. O banco atinge essa proeza mantendo múltiplas versões físicas da mesma linha na tabela (as chamadas *tuples*).

Toda tupla no PostgreSQL carrega metadados internos vitais nos seus cabeçalhos:
- `xmin`: O ID da transação (`txid`) que criou aquela versão da linha.
- `xmax`: O ID da transação que deletou ou substituiu aquela linha por uma versão mais nova. Se a tupla estiver ativa e sem modificações pendentes, o `xmax` fica zerado (ou contém flags de lock, como veremos adiante).

Quando uma transação com isolamento `READ COMMITTED` (o padrão do PostgreSQL) executa uma query, ela enxerga apenas as tuplas cujo `xmin` já foi commitado antes do início da instrução atual, e cujo `xmax` seja inválido ou pertença a uma transação ainda não commitada.

Até aí, tudo lindo. O problema surge quando duas transações tentam alterar a **mesma** linha ou quando usamos mecanismos explícitos de bloqueio. O MVCC resolve conflitos de leitura versus escrita criando snapshots. Porém, quando duas transações querem **escrever** no mesmo registro físico, a física dos discos e a integridade relacional entram em cena: uma delas obrigatoriamente terá que esperar.

---

## A anatomia de uma fila de espera: Como o lock de linha funciona

Imagine um cenário clássico de e-commerce ou sistema financeiro: débito de saldo em conta ou reserva de estoque.

```sql
-- Transação A
BEGIN;
SELECT saldo FROM contas WHERE id = 42 FOR UPDATE;
-- Aplicação faz contas em memória...
UPDATE contas SET saldo = saldo - 50 WHERE id = 42;
COMMIT;
```

O que o `FOR UPDATE` faz? Ele escreve o ID da transação corrente no campo `xmax` do cabeçalho da tupla e seta flags específicas no campo `t_infomask` indicando um lock exclusivo de linha. 

Agora, imagine que outras 100 requisições simultâneas cheguem no mesmo milissegundo querendo manipular a conta `42`. O que acontece com a Transação B, C, D e as demais?

Elas não tomam erro imediato. Em vez disso, entram em estado de espera no lock manager do PostgreSQL (`LockView`). A transação B tenta adquirir o lock, percebe que o `xmax` da tupla aponta para a Transação A (que ainda está aberta) e registra uma dependência no subsistema de locks em memória compartilhada via `XidLock`.

### O efeito dominó do Lock Queue

O problema não é apenas que B espera A terminar. O problema é a formação de uma fila encadeada e o consumo invisível de recursos:

1. **Retenção de conexões:** Cada requisição travada no banco segura uma conexão ativa do pool da aplicação (HikariCP, pgxpool, SQLAlchemy, etc.).
2. **Atraso cumulativo:** Se a Transação A demorar 100ms (talvez porque a aplicação chamou uma API externa antes do `COMMIT` — um pecado capital), e 10 clientes disputam o registro, o décimo cliente esperará pelo menos 1000ms apenas na fila do banco, sem consumir CPU, mas monopolizando workers do Postgres.
3. **Bloat e Thrashing:** Enquanto o lock é mantido, o `VACUUM` não consegue limpar versões antigas daquela linha se houver transações mais antigas ativas na instância, gerando inchaço desnecessário de páginas em disco.

Para verificar se sua aplicação está sofrendo disso neste exato momento em homologação ou produção, consulte a visão do sistema:

```sql
SELECT 
    blocked_locks.pid     AS blocked_pid,
    blocked_activity.usename  AS blocked_user,
    blocking_locks.pid    AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query    AS blocked_statement,
    blocking_activity.query   AS current_statement_in_blocking_process
FROM  pg_catalog.pg_locks         blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks         blocking_locks 
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

Se essa query retornar várias linhas apontando para a mesma tupla ou tabela, você tem contenção grave de locks.

---

## Os quatro sabores de Lock de Linha (e por que você provavelmente escolheu o errado)

O PostgreSQL não oferece apenas `FOR UPDATE`. Ele possui quatro modos de bloqueio a nível de linha, documentados na [especificação de explicit locking](https://www.postgresql.org/docs/current/explicit-locking.html){:target="_blank"}. Escolher a intensidade correta do lock reduz grande parte dos bloqueios desnecessários.

| Modo | Conflita com | Caso de uso típico |
| :--- | :--- | :--- |
| **FOR UPDATE** | `UPDATE`, `DELETE`, `FOR UPDATE`, `FOR NO KEY UPDATE`, `FOR SHARE`, `FOR KEY SHARE` | Modificação de chaves primárias/únicas ou exclusão da linha. |
| **FOR NO KEY UPDATE** | `UPDATE` (em chaves), `DELETE`, `FOR UPDATE`, `FOR NO KEY UPDATE`, `FOR SHARE` | Atualização de colunas comuns (ex: mudar status, saldo, nome). **Não bloqueia quem lê com FOR KEY SHARE.** |
| **FOR SHARE** | `UPDATE`, `DELETE`, `FOR UPDATE`, `FOR NO KEY UPDATE` | Leitura com garantia de que a linha não será modificada por ninguém até o fim da transação. |
| **FOR KEY SHARE** | `DELETE`, `UPDATE` (apenas em colunas que compõem chaves exclusivas) | Integridade referencial (usado automaticamente por Foreign Keys). |

### O caso do `FOR NO KEY UPDATE`

Se você vai apenas atualizar uma coluna não-chave (por exemplo, `saldo` ou `status`), o `FOR UPDATE` é truculento demais. Ele bloqueia transações filhas que dependem de checagem de chave estrangeira (`FOR KEY SHARE`).

```sql
-- Mais eficiente para updates simples de dados não indexados por constraints exclusivas
SELECT id, saldo 
FROM contas 
WHERE id = 42 
FOR NO KEY UPDATE;
```

Ao usar `FOR NO KEY UPDATE`, se outra transação estiver apenas inserindo um registro na tabela `pedidos` que referencia `contas(id = 42)`, as duas transações rodam em paralelo sem conflito. Se você usasse `FOR UPDATE`, o insert na tabela de pedidos ficaria retido aguardando o commit da conta.

---

## Quebrando o gargalo: SKIP LOCKED e NOWAIT

Um dos maiores vilões de performance em arquiteturas backend ocorre quando o banco de dados relacional é utilizado como fila de processamento (*Job Queue* ou *Outbox Pattern*).

Considere a tabela típica de outbox:

```sql
CREATE TABLE outbox_messages (
    id BIGSERIAL PRIMARY KEY,
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_outbox_pending ON outbox_messages(id) WHERE status = 'PENDING';
```

Se você tiver 10 workers consumindo essa tabela, o instinto inicial de muitos engenheiros é:

```sql
-- ANTI-PATTERN EM WORKERS CONCORRENTES
SELECT id, payload 
FROM outbox_messages 
WHERE status = 'PENDING' 
ORDER BY id ASC 
LIMIT 10 
FOR UPDATE;
```

**O desastre anunciado:** O Worker 1 pega os 10 primeiros IDs (1 a 10). O Worker 2 executa a mesma query. O que o Postgres faz? 
Ele avalia o `ORDER BY id ASC LIMIT 10`, percebe que os registros 1 a 10 atendem ao filtro, mas vê que estão bloqueados pelo Worker 1. O Worker 2 **não** pula para o registro 11! Ele simplesmente fica parado esperando o Worker 1 terminar. Quando o Worker 1 commita alterando o status para `'PROCESSED'`, o Worker 2 finalmente acorda, reavalia a cláusula `WHERE status = 'PENDING'`, vê que os registros 1 a 10 não servem mais, e só então busca os registros 11 a 20. Toda a concorrência dos seus 10 workers vira execução serializada.

### A solução: SKIP LOCKED

O PostgreSQL introduziu no 9.5 o modificador `SKIP LOCKED`. Ele instrui o motor a ignorar silenciosamente qualquer linha que já esteja travada por outra transação e pegar as próximas elegíveis no índice:

```sql
-- PADRÃO DE ALTA PERFORMANCE PARA WORKERS
WITH selected_jobs AS (
    SELECT id 
    FROM outbox_messages 
    WHERE status = 'PENDING' 
    ORDER BY id ASC 
    LIMIT 10 
    FOR UPDATE SKIP LOCKED
)
UPDATE outbox_messages o
SET status = 'PROCESSING'
FROM selected_jobs s
WHERE o.id = s.id
RETURNING o.id, o.payload;
```

Com `SKIP LOCKED`, se o Worker 1 está processando as linhas 1 a 10, o Worker 2 instantaneamente seleciona de 11 a 20 sem esperar um único nanossegundo. O throughput da sua fila passa a escalar de forma linear com o número de workers.

### Quando usar NOWAIT?

Se a sua regra de negócio não tolera filas e prefere falhar rápido para responder ao usuário com um erro semântico (como `409 Conflict`), use `NOWAIT`:

```sql
SELECT * FROM assentos_aviao 
WHERE voo_id = 99 AND numero = '12A' 
FOR UPDATE NOWAIT;
```

Se outra pessoa estiver reservando o assento exatamente no mesmo instante, em vez de sua thread de aplicação ficar suspensa até timeout de socket, o PostgreSQL retorna imediatamente o erro `55P03 (lock_not_available)`. Você captura isso na aplicação e devolve ao frontend uma mensagem amigável de que o recurso está sendo operado por outro usuário.

---

## Concorrência Otimista vs Pessimista: Quem ganha em escala?

O `SELECT ... FOR UPDATE` é a personificação da **concorrência pessimista**: você assume que o pior vai acontecer (conflito iminente), bloqueia o recurso no início da operação e só libera no final.

Para cenários de baixíssima contenção e tráfego massivo, a **concorrência otimista** via versionamento de registro é imbatível, pois elimina completamente locks de leitura duradouros.

### Implementação prática de Concorrência Otimista

Adicione uma coluna de controle (pode ser um inteiro sequencial ou um timestamp/UUID):

```sql
ALTER TABLE produtos ADD COLUMN version INT DEFAULT 1;
```

O fluxo na aplicação passa a ser puramente sem locks na leitura:

```sql
-- 1. Leitura sem nenhum lock (rápida, puramente MVCC)
SELECT id, preco, estoque, version 
FROM produtos 
WHERE id = 500;

-- 2. A aplicação faz suas validações e regras de negócio localmente.

-- 3. Atualização condicional atômica
UPDATE produtos 
SET estoque = estoque - 1, 
    version = version + 1
WHERE id = 500 AND version = 1;
```

Na aplicação, você checa quantas linhas foram afetadas pelo `UPDATE`:
- Se `rows_affected == 1`, a alteração foi aplicada com sucesso.
- Se `rows_affected == 0`, significa que outro cliente alterou o registro enquanto sua aplicação pensava. Você simplesmente descarta a transação e decide: ou tenta novamente (*retry loop* com backoff exponencial) ou rejeita a operação.

Essa abordagem descarrega completamente o gerenciador de locks do banco. O custo pago é o de possíveis repetições na aplicação caso a contenção no mesmo ID seja muito alta.

---

## O segredo dos Advisory Locks: Bloqueios sem tocar nas tabelas

E quando você precisa sincronizar uma operação complexa entre múltiplos nós do seu backend, mas não quer criar registros de mentira no banco nem subir um Redis com Redlock?

O PostgreSQL possui um recurso brilhante chamado **PostgreSQL Advisory Locks** (bloqueios consultivos). São locks gerenciados na memória compartilhada do Postgres, identificados por um identificador numérico de 64 bits arbitrário definido pela sua aplicação, sem dependência de tabelas físicas.

Eles vêm em dois sabores:
1. **Session-level:** O lock dura até a conexão física fechar ou até você chamar explicitamente a função de liberação.
2. **Transaction-level:** O lock é liberado automaticamente quando a transação atual faz `COMMIT` ou `ROLLBACK`.

### Exemplo prático: Evitando jobs duplicados com Advisory Locks

Imagine que você tem um cron job rodando a cada 5 minutos em 4 instâncias da sua aplicação para processar faturamentos. Você quer garantir que **apenas uma** instância execute a rotina ao mesmo tempo:

```sql
-- Na transação do worker:
BEGIN;

-- Tenta adquirir o lock transacional exclusivo sem bloquear (chave de 64 bits arbitrária)
SELECT pg_try_advisory_xact_lock(849204829104812) AS lock_adquirido;
```

Se `lock_adquirido` retornar `true`, a instância atual assume a liderança e roda as queries pesadas. As outras instâncias recebem `false` imediatamente, encerram a transação e vão dormir sem enfileirar o banco.

```sql
-- Quando o worker vencedor termina:
COMMIT;
-- O pg_try_advisory_xact_lock é liberado automaticamente aqui!
```

Você também pode usar advisory locks baseados em IDs relacionais. Digamos que você queira sincronizar a criação de um diretório complexo de arquivos para um usuário específico cujo `user_id` é `12345`:

```sql
-- O primeiro argumento é um namespace da aplicação (ex: 1 = processamento_arquivos)
-- O segundo argumento é o ID da entidade (user_id)
SELECT pg_advisory_xact_lock(1, 12345);
-- Qualquer outra transação tentando travar o par (1, 12345) vai esperar aqui.
```

Isso evita criar registros temporários em tabelas só para controle de mutex.

---

## Níveis de Isolamento: O perigo do Phantom Read e Serialization Failure

Por padrão, o PostgreSQL opera em `READ COMMITTED`. Cada comando SQL dentro da mesma transação enxerga um snapshot diferente: o estado do banco no instante em que a instrução individual começou.

Isso gera o clássico bug de concorrência por *Non-repeatable Read*:

```sql
-- Transação A (READ COMMITTED)
BEGIN;
SELECT saldo FROM contas WHERE id = 1; -- Retorna 100

-- (Nesse meio tempo, Transação B faz UPDATE contas SET saldo = 50 WHERE id = 1 e COMMIT)

SELECT saldo FROM contas WHERE id = 1; -- Retorna 50 dentro da mesma transação!
COMMIT;
```

Se você mudar para `REPEATABLE READ`, o PostgreSQL congela o snapshot no início da **primeira instrução** da transação inteira:

```sql
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SELECT saldo FROM contas WHERE id = 1; -- Retorna 100
-- Mesmo que Transação B commite novo saldo...
SELECT saldo FROM contas WHERE id = 1; -- Continua retornando 100!
```

Mas cuidado: se a Transação A tentar alterar uma linha que foi modificada e commitada pela Transação B após o início do snapshot da Transação A, o PostgreSQL abortará a operação imediatamente com o erro:

`ERROR: could not serialize access due to concurrent update (SQLSTATE 40001)`

### O que isso significa para o código da sua aplicação?

Se você decide subir o nível de isolamento para `REPEATABLE READ` ou `SERIALIZABLE` para evitar anomalias de leitura, o seu código backend **precisa obrigatoriamente** implementar uma camada de tratamento de retry para o SQLSTATE `40001`.

Veja um exemplo conceitual em pseudocódigo idiomático de como tratar isso adequadamente na aplicação:

```python
import time
import psycopg2

def execute_with_retry(db_pool, business_fn, max_retries=3):
    retries = 0
    backoff = 0.05  # 50ms
    
    while True:
        conn = db_pool.getconn()
        try:
            with conn:
                with conn.cursor() as cur:
                    # Inicia com isolamento estrito
                    cur.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;")
                    result = business_fn(cur)
                    return result
        except psycopg2.errors.SerializationFailure:
            retries += 1
            if retries > max_retries:
                raise RuntimeError("Concorrência excessiva: limite de tentativas excedido.")
            # Backoff com jitter para não gerar thundering herd
            time.sleep(backoff * (2 ** retries))
        finally:
            db_pool.putconn(conn)
```

Sem esse tratamento no nível da aplicação, mudar o nível de isolamento no banco apenas transfere o problema de inconsistência lógica para um mar de exceções não tratadas no monitor do Sentry.

---

## Boas práticas para manter o banco respirando

Para manter a concorrência alta e evitar quedas provocadas por filas de bloqueio, transforme estas regras em convenções do seu time:

1. **Transações devem ser minúsculas no tempo:** Jamais faça chamadas HTTP, parseamento de JSON gigantesco ou cálculos matemáticos demorados com uma transação do banco aberta. Abra a transação, faça apenas as queries estritamente necessárias e commite imediatamente.
2. **Ordem determinística de locks:** Se duas transações precisam travar os mesmos registros (por exemplo, transferir dinheiro entre a conta A e a conta B), garanta que ambas sempre travem os recursos **na mesma ordem** (exemplo: sempre trave o menor `id` primeiro). Isso elimina 100% dos cenários clássicos de Deadlock (`deadlock detected`).
3. **Configure statement_timeout e lock_timeout:** Nunca deixe uma query esperar eternamente por um lock. Defina parâmetros sensatos na sessão ou globalmente:
   ```sql
   SET lock_timeout = '2s';
   SET statement_timeout = '10s';
   ```
   Se o lock demorar mais de 2 segundos para ser adquirido, a transação cai antes de sufocar o pool de conexões.
4. **Prefira `SKIP LOCKED` a queries de polling manuais:** Se você implementa mensageria no banco, esse parâmetro é obrigatório.
5. **Use os modos de lock menos restritivos:** Pergunte-se se você realmente precisa de `FOR UPDATE` ou se um `FOR NO KEY UPDATE` já protege a sua invariante de domínio.

Entender como as tuplas, transações e a memória do PostgreSQL cooperam é o que diferencia uma aplicação que trava aos 200 RPS de um sistema que sustenta dezenas de milhares de operações por segundo sem suar a CPU do banco.

---

_Este post foi totalmente gerado por uma IA autônoma, sem intervenção humana._

[Veja o código que gerou este post](https://github.com/cleissonbarbosa/cleissonbarbosa.github.io/blob/main/generate_post/README.md){:target="_blank"}
