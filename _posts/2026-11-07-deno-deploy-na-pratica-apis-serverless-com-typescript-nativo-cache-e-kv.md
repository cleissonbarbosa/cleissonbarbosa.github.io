---
title: "Deno Deploy na prática: APIs serverless com TypeScript nativo, cache e KV"
author: ia
date: 2026-11-07 22:18:37 -0300
description: "Aprenda a criar, otimizar e publicar APIs serverless usando Deno Deploy, com rotas dinâmicas, Edge Cache e Deno KV."
image:
  path: /assets/img/posts/09f023fc-b4e6-4f6b-af0e-eff5fbd0f283.png
  alt: "Deno Deploy na prática: APIs serverless com TypeScript nativo, cache e KV"
categories: ["programação", "deno", "serverless"]
tags: ["deno", "typescript", "serverless", "edge", "kv", "api", "observabilidade", "ai-generated"]
---

## Introdução: por que Deno Deploy merece sua atenção agora

Se você já está cansado de lidar com Dockerfiles gigantes, dependências que precisam ser compiladas e o clássico "cold start" das funções Lambda em Python ou Node.js, vai achar o Deno Deploy um alívio refrescante. O Deno, criado por Ryan Dahl (o mesmo que inventou o Node), traz um runtime JavaScript/TypeScript que roda **sem necessidade de um gerenciador de pacotes externo** e já inclui um conjunto de recursos de segurança, bundling e testes. O Deno Deploy, por sua vez, é a camada serverless que coloca seu código **na borda** da rede, próximo ao usuário final, reduzindo latência e eliminando a sobrecarga de provisionamento de containers.

Neste post vamos montar, passo a passo, uma API RESTful completa usando apenas TypeScript puro, sem frameworks pesados. Vamos explorar rotas dinâmicas, cache de resposta na Edge, persistência com o novo Deno KV e ainda automatizar o deploy com GitHub Actions. Tudo isso em menos de uma hora de trabalho – se você seguir o roteiro.

> *Dica*: se você ainda não conhece o Deno, dê uma olhada na documentação oficial antes de prosseguir: [Deno Manual](https://deno.land/manual){:target="_blank"}.

## 1. Deno vs Node: o que mudou?

A principal diferença está na **filosofia de segurança**. Enquanto o Node permite acesso livre ao sistema de arquivos e à rede, o Deno começa **sandboxed**; você precisa conceder permissões explicitamente (`--allow-net`, `--allow-read`, etc.). Além disso, o Deno tem suporte nativo a **ESM**, **TypeScript** e **Web APIs** (como `fetch`, `Request`, `Response`). Isso elimina a necessidade de Babel, Webpack ou ts-node.

Do ponto de vista de performance, o Deno usa o motor V8 diretamente (mesmo que o Node) e tem um **garbage collector** mais recente. Na prática, a diferença de tempo de execução costuma ser mínima, mas o ganho de produtividade ao não precisar de configuração de build pode ser decisivo.

## 2. Configurando o ambiente local

Instalar o Deno é bem simples. No macOS ou Linux, basta:

```bash
curl -fsSL https://deno.land/x/install/install.sh | sh
```

No Windows, use o **PowerShell**:

```powershell
iwr https://deno.land/x/install/install.ps1 -useb | iex
```

Depois de instalado, verifique a versão:

```bash
denoversion
```

### Projeto inicial

Crie uma pasta para o projeto e inicialize um *git*:

```bash
mkdir deno-api && cd deno-api
git init
```

Vamos criar um arquivo `main.ts` que será o ponto de entrada da nossa API:

```ts
// main.ts
import { serve } from "https://deno.land/std@0.224.0/http/server.ts";

const handler = (request: Request): Response => {
  const url = new URL(request.url);
  if (url.pathname === "/") {
    return new Response("Hello from Deno Deploy!", { status: 200 });
  }
  return new Response("Not Found", { status: 404 });
};

serve(handler);
```

Execute localmente com:

```bash
denon run --allow-net main.ts
```

Abra `http://localhost:8000` no navegador e você verá a mensagem de saudação.

> **Nota**: o módulo `serve` vem da biblioteca padrão (`std`). Sempre verifique a versão mais recente antes de usar.

## 3. Primeiro deploy: uma API mínima

Crie uma conta em [Deno Deploy](https://dash.deno.com){:target="_blank"}. O plano gratuito já oferece 100 MiB de KV, 2 GB de transferência mensal e 30 dias de histórico de logs – suficiente para testes.

No dashboard, clique em **New Project**, escolha **GitHub** como origem e selecione o repositório que você acabou de criar. O Deploy detecta automaticamente o arquivo `main.ts` como ponto de entrada.

### Configurando permissões

Como o Deno começa sandboxed, o Deploy precisa saber quais permissões seu código requer. No painel de *Settings* → *Permissions*, habilite **net** (necessário para responder a requisições HTTP) e **read/write** para KV se for usar o banco de chave‑valor.

A primeira implantação deve estar online em poucos segundos. Teste a URL pública (algo como `https://<project>.deno.dev/`) e confirme que a mensagem aparece.

## 4. Rotas dinâmicas e parâmetros de caminho

Para transformar a API em algo útil, vamos criar um recurso de **todos**. Cada todo tem `id`, `title` e `completed`. Usaremos rotas do tipo `/todos` (GET, POST) e `/todos/:id` (GET, PATCH, DELETE).

Primeiro, vamos organizar o código em módulos. Crie a pasta `routes` e o arquivo `todos.ts`:

```ts
// routes/todos.ts
import { kv } from "https://deno.land/x/kv@0.2.0/mod.ts";

export const handler = async (request: Request): Promise<Response> => {
  const url = new URL(request.url);
  const parts = url.pathname.split("/").filter(Boolean); // ['todos', ':id?']

  // /todos
  if (parts.length === 1) {
    switch (request.method) {
      case "GET":
        return listTodos();
      case "POST":
        return createTodo(request);
    }
  }

  // /todos/:id
  if (parts.length === 2) {
    const id = parts[1];
    switch (request.method) {
      case "GET":
        return getTodo(id);
      case "PATCH":
        return updateTodo(id, request);
      case "DELETE":
        return deleteTodo(id);
    }
  }

  return new Response("Not Found", { status: 404 });
};

// Funções auxiliares -------------------------------------------------------

const listTodos = async (): Promise<Response> => {
  const entries = await kv.list({ prefix: ["todo"] });
  const todos = [];
  for await (const entry of entries) {
    todos.push(entry.value);
  }
  return new Response(JSON.stringify(todos), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
};

const createTodo = async (req: Request): Promise<Response> => {
  const body = await req.json();
  const id = crypto.randomUUID();
  const todo = { id, title: body.title ?? "", completed: false };
  await kv.set(["todo", id], todo);
  return new Response(JSON.stringify(todo), { status: 201, headers: { "Content-Type": "application/json" } });
};

const getTodo = async (id: string): Promise<Response> => {
  const result = await kv.get(["todo", id]);
  if (!result.value) return new Response("Not Found", { status: 404 });
  return new Response(JSON.stringify(result.value), { status: 200, headers: { "Content-Type": "application/json" } });
};

const updateTodo = async (id: string, req: Request): Promise<Response> => {
  const existing = await kv.get(["todo", id]);
  if (!existing.value) return new Response("Not Found", { status: 404 });
  const updates = await req.json();
  const updated = { ...existing.value, ...updates };
  await kv.set(["todo", id], updated);
  return new Response(JSON.stringify(updated), { status: 200, headers: { "Content-Type": "application/json" } });
};

const deleteTodo = async (id: string): Promise<Response> => {
  await kv.delete(["todo", id]);
  return new Response(null, { status: 204 });
};
```

Agora ajuste o `main.ts` para delegar as requisições ao módulo de rotas:

```ts
// main.ts
import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { handler as todosHandler } from "./routes/todos.ts";

const handler = (request: Request): Response | Promise<Response> => {
  const url = new URL(request.url);
  if (url.pathname.startsWith("/todos")) {
    return todosHandler(request);
  }
  if (url.pathname === "/") {
    return new Response("API Deno Deploy pronta!", { status: 200 });
  }
  return new Response("Not Found", { status: 404 });
};

serve(handler);
```

Teste localmente com `deno run --allow-net --allow-read --allow-write main.ts`. Use o **httpie** ou **curl** para validar:

```bash
curl -X POST https://localhost:8000/todos -H "Content-Type: application/json" -d '{"title":"Comprar café"}'
```

A resposta deve conter o objeto criado com um `id` UUID.

## 5. Edge Cache: reduzindo latência e custo

Uma das vantagens do Deploy é o **Edge Cache** embutido. Ele permite que respostas idempotentes sejam armazenadas nos pontos de presença (PoPs) da rede, evitando chamadas ao KV a cada requisição.

Vamos cachear a listagem de todos os *todos* por 30 segundos. Modifique a função `listTodos`:

```ts
const listTodos = async (): Promise<Response> => {
  const cache = await caches.open("todos-cache");
  const cached = await cache.match("/todos");
  if (cached) return cached;

  const entries = await kv.list({ prefix: ["todo"] });
  const todos = [];
  for await (const entry of entries) {
    todos.push(entry.value);
  }
  const resp = new Response(JSON.stringify(todos), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "public, max-age=30",
    },
  });
  await cache.put("/todos", resp.clone());
  return resp;
};
```

A API agora serve a resposta a partir da cache por 30 s, reduzindo leituras no KV e, consequentemente, custos de I/O.

> **Curiosidade**: o módulo `caches` segue a mesma API do Service Workers, facilitando a migração de lógica de front‑end para a Edge.

## 6. Persistência com Deno KV vs SQLite

Se você acompanha o post anterior sobre **SQLite em produção** [{SQLite em Produção}](https://cleissonbarbosa.github.io/posts/sqlite-em-producao-o-guia-definitivo-de-performance-wal-mode-e-concorrencia-real/){:target="_blank"}, já sabe que um banco embutido pode ser suficiente em certos cenários. No entanto, no contexto serverless da Edge, **acesso a disco** é limitado ou inexistente. O Deno KV oferece um armazenamento de chave‑valor distribuído, com latência sub‑milissegundo e replicação automática.

### Quando usar KV?
- Dados **não relacionais** (por exemplo, sessões, rate‑limit counters, configurações de feature flag).
- Necessidade de **consistência eventual** com alta disponibilidade.
- Operações simples de **get/set/delete**.

### Quando ainda preferir SQLite?
- Quando a aplicação exige **consultas SQL complexas** (joins, agregações).
- Quando a consistência **forte** é mandatória.
- Quando o volume de dados excede o limite gratuito de KV (100 MiB).

No nosso exemplo de *todos*, KV é suficiente porque cada item é um documento JSON independente.

## 7. Observabilidade: logs e métricas na Edge

Deno Deploy expõe logs via dashboard e também permite **exportar métricas** para serviços externos (Datadog, Prometheus). Vamos habilitar logs estruturados em JSON para facilitar a ingestão.

```ts
const logger = (msg: string, data?: unknown) => {
  const payload = { timestamp: new Date().toISOString(), msg, ...data };
  console.log(JSON.stringify(payload));
};
```

Use o `logger` nas rotas:

```ts
const createTodo = async (req: Request): Promise<Response> => {
  const body = await req.json();
  const id = crypto.randomUUID();
  const todo = { id, title: body.title ?? "", completed: false };
  await kv.set(["todo", id], todo);
  logger("todo_created", { id, title: todo.title });
  return new Response(JSON.stringify(todo), { status: 201, headers: { "Content-Type": "application/json" } });
};
```

No dashboard, vá em **Logs** → **Live** e veja as entradas em tempo real. Para métricas, adicione cabeçalhos `Server-Timing` nas respostas:

```ts
return new Response(JSON.stringify(todos), {
  status: 200,
  headers: {
    "Content-Type": "application/json",
    "Cache-Control": "public, max-age=30",
    "Server-Timing": "db;dur=12, cache;dur=3",
  },
});
```

Esses valores podem ser consumidos por ferramentas como **Chrome DevTools** ou **Grafana** via endpoint `/metrics` que você pode criar usando o mesmo padrão.

## 8. CI/CD com GitHub Actions

Automatizar o deploy evita o clássico *"esqueci de atualizar o ambiente"*. Crie o arquivo `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Deno
on:
  push:
    branches: [ main ]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Deno
        uses: denoland/setup-deno@v2
        with:
          deno-version: v1.x
      - name: Deploy
        env:
          DENO_DEPLOY_TOKEN: ${{ secrets.DENO_DEPLOY_TOKEN }}
        run: |
          deno task deploy
```

Adicione um script `deploy` no `deno.json`:

```json
{
  "tasks": {
    "deploy": "deno deploy --project=<YOUR_PROJECT_ID> main.ts"
  }
}
```

Crie o segredo `DENO_DEPLOY_TOKEN` no repositório (você encontra o token no dashboard → *Account* → *API Tokens*). A partir do próximo push no `main`, o GitHub Actions enviará o código para a Edge automaticamente.

## 9. Boas práticas e armadilhas comuns

| Boa prática | Por quê? |
|---|---|
| **Limitar permissões** | Reduz risco de vazamento de dados caso o código seja comprometido. |
| **Cachear somente GETs idempotentes** | Evita servir conteúdo stale para operações de escrita. |
| **Não armazenar arquivos grandes no KV** | KV tem limites de tamanho por valor (aprox. 64 KB). Use um bucket S3/Spaces para blobs. |
| **Versionar APIs** | Mantenha a compatibilidade ao introduzir mudanças; use `/v1/`, `/v2/` nos caminhos. |
| **Testar com Deno test** | O Deno já inclui um runner de testes; escreva unit‑tests para cada handler. |

### Armadilhas que já vi
- **Cold start inesperado**: embora a Edge seja rápida, a primeira invocação pode levar ~200 ms se o código precisar ser baixado. Mantenha o bundle pequeno.
- **Limite de KV writes**: o plano gratuito tem 10 k writes por segundo. Para alta taxa, considere sharding ou usar um banco externo.
- **Headers sensíveis**: nunca exponha tokens de API nos logs; use `console.error` apenas para mensagens de erro.

## 10. Próximos passos

- **Autenticação**: integre JWT ou Deno Deploy *Access Tokens* para proteger rotas.
- **Rate limiting**: use KV como contador de requisições por IP.
- **GraphQL**: o Deno tem bibliotecas como `graphql_deno` que rodam na Edge sem problemas.
- **Deploy multi‑region**: configure *custom domains* com geolocalização para melhorar ainda mais a latência.

## Conclusão

Deno Deploy demonstra que construir APIs serverless não precisa ser um labirinto de configuração. Com TypeScript nativo, rotas simples, cache de borda e um KV distribuído, você obtém um stack completo que roda próximo ao usuário final, reduzindo latência e custos operacionais. O fluxo de desenvolvimento — código local, push no GitHub, CI/CD automático — é enxuto e agradável, permitindo que a equipe foque na lógica de negócio ao invés de infraestrutura.

Se você ainda está usando containers pesados ou bancos locais para protótipos, experimente migrar para a Edge. Comece pequeno, monitore métricas e, quando o padrão se firmar, escale sem precisar re‑arquitetar a base.

*Boa codificação!*

---

_Este post foi totalmente gerado por uma IA autônoma, sem intervenção humana._

[Veja o código que gerou este post](https://github.com/cleissonbarbosa/cleissonbarbosa.github.io/blob/main/generate_post/README.md){:target="_blank"}
