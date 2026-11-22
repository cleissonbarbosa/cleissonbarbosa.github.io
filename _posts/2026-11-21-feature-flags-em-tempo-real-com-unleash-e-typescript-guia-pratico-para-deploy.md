---
title: "Feature Flags em Tempo Real com Unleash e TypeScript: Guia Prático para Deploy Seguro"
author: ia
date: 2026-11-21 23:02:11 -0300
description: "Aprenda a implementar feature flags usando Unleash, TypeScript e React, com estratégias avançadas de rollout e integração CI/CD."
image:
  path: /assets/img/posts/8f56fbb1-154a-4f53-b186-eb0b26f41935.png
  alt: "Feature Flags em Tempo Real com Unleash e TypeScript: Guia Prático para Deploy Seguro"
categories: ["programação", "feature flags", "typescript"]
tags: ["feature flags", "unleash", "typescript", "nodejs", "react", "ci", "ai-generated"]
audio: /assets/audio/posts/feature-flags-em-tempo-real-com-unleash-e-typescript-guia-pratico-para-deploy.mp3
---

## Por que Feature Flags são essenciais hoje

A pressão por entregas rápidas não desaparece; o que muda é a forma como mitigamos risco. **Feature flags** (ou *toggles*) permitem ativar, desativar ou variar comportamentos de código sem precisar de um novo deploy. Em ambientes de micro‑serviços, CI/CD agressivo e equipes distribuídas, isso deixa de ser um luxo e vira necessidade.

Mas nem toda solução de toggle é igual. Muitos projetos acabam usando *if‑else* espalhados no código ou arquivos de configuração estáticos, o que gera dívida técnica e dificulta auditoria. O **Unleash** nasce como um *feature toggle platform* open‑source que traz controle centralizado, métricas e integração nativa com TypeScript/Node.

Neste post vamos montar, do zero, um pipeline completo:

1. **Unleash Server** rodando em Docker
2. **Cliente Node/TS** para backend
3. **Proxy React** para frontend
4. Estratégias avançadas (gradual rollout, A/B testing)
5. Integração com CI/CD para validar flags antes de produção

Ao final, você terá um código pronto para ser copiado, testado e evoluído.

---

## 1. Arquitetura recomendada

```
+-------------------+       +-------------------+       +-------------------+
|  Unleash Server   | <---> |  Unleash Proxy    | <---> |  Aplicação Front  |
+-------------------+       +-------------------+       +-------------------+
        ^   ^                         ^   ^
        |   |                         |   |
        |   +-------------------------+   |
        |                                 |
        v                                 v
+-------------------+               +-------------------+
|  Backend (Node)   |               |  CI/CD (GitHub)   |
+-------------------+               +-------------------+
```

* **Unleash Server**: fonte da verdade, persiste flags em PostgreSQL ou SQLite.
* **Unleash Proxy**: camada de cache e segurança que expõe apenas o que o cliente precisa, ideal para browsers.
* **Cliente Node**: consulta flags diretamente ao server (ou ao proxy) usando SDK oficial.
* **Cliente React**: consome o proxy via SDK React, garantindo *SSR* e *CSR*.
* **CI/CD**: validações automatizadas que garantem que nenhuma flag seja deixada em estado inconsistente.

A separação entre server e proxy evita que credenciais sensíveis (tokens de admin) cheguem ao browser e ainda permite escalar o proxy horizontalmente.

---

## 2. Subindo o Unleash Server com Docker Compose

Crie um diretório `unleash-demo` e adicione o seguinte `docker-compose.yml`:

```yaml
version: "3.8"
services:
  unleash-db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: unleash
      POSTGRES_PASSWORD: unleashpw
      POSTGRES_DB: unleash
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: unless-stopped

  unleash-server:
    image: unleashorg/unleash-server:latest
    depends_on:
      - unleash-db
    environment:
      DATABASE_URL: postgres://unleash:unleashpw@unleash-db:5432/unleash
      INIT_CLIENT_API_TOKENS: default:mysecrettoken
    ports:
      - "4242:4242"
    restart: unless-stopped

  unleash-proxy:
    image: unleashorg/unleash-proxy:latest
    depends_on:
      - unleash-server
    environment:
      UNLEASH_URL: http://unleash-server:4242/api
      UNLEASH_API_TOKEN: mysecrettoken
    ports:
      - "3000:3000"
    restart: unless-stopped

volumes:
  pgdata:
```

> **Dica:** o token `mysecrettoken` será usado pelos clientes. Guarde‑o em um secret manager na produção.

Execute `docker compose up -d` e acesse o painel admin em `http://localhost:4242`. Use `admin`/`unleash` como credenciais padrão (documentado em [Unleash docs](https://unleash.github.io/docs/){:target="_blank"}).

---

## 3. Definindo a primeira flag

No painel admin, clique em **Create new feature toggle** e preencha:

* **Name**: `newCheckoutFlow`
* **Description**: *Ativa a nova jornada de checkout baseada em React Server Components.*
* **Type**: *Release toggle* (simples ON/OFF)

Salve. A flag agora está visível tanto no server quanto no proxy.

---

## 4. Integrando no backend Node/TS

Instale o SDK oficial:

```bash
npm i unleash-client @types/unleash-client
```

Crie `src/featureFlags.ts`:

```typescript
import { Unleash } from 'unleash-client';

// Configurações típicas de produção devem vir de variáveis de ambiente
const unleash = new Unleash({
  url: process.env.UNLEASH_URL || 'http://localhost:4242/api/',
  appName: 'order-service',
  instanceId: `order-${process.pid}`,
  customHeaders: {
    Authorization: `Bearer ${process.env.UNLEASH_TOKEN}`,
  },
});

/**
 * Wrapper síncrono que garante que o SDK já está pronto.
 * Em produção, você pode aguardar o evento "ready" antes de iniciar o server HTTP.
 */
export function isEnabled(flag: string, context: Record<string, any> = {}): boolean {
  if (!unleash.isReady()) {
    // fallback conservador: desabilita a feature até termos certeza
    return false;
  }
  return unleash.isEnabled(flag, context);
}

// Exemplo de uso em um handler Express
import express from 'express';
const app = express();

app.get('/checkout', (req, res) => {
  const useNewFlow = isEnabled('newCheckoutFlow', { userId: req.query.userId });
  if (useNewFlow) {
    // redireciona para a nova UI hospedada em outro micro‑serviço
    return res.redirect('/new-checkout');
  }
  // fluxo legacy
  res.send('Checkout tradicional');
});

app.listen(8080, () => console.log('API rodando na porta 8080'));
```

### 4.1. Estratégia de contexto avançado

Unleash permite *constraints* baseadas em atributos do usuário (por exemplo, `region: EU`). No código acima, o `context` pode receber `userId`, `environment`, `sessionId`, etc. Isso abre caminho para *gradual rollout* por segmento.

---

## 5. Consumindo flags no frontend React com o Proxy

Instale o SDK React e o proxy client:

```bash
npm i @unleash/proxy-client-react
```

Crie um provider global em `src/UnleashProvider.tsx`:

```tsx
import React from 'react';
import { UnleashProvider as ProxyProvider } from '@unleash/proxy-client-react';

export const UnleashProvider: React.FC = ({ children }) => (
  <ProxyProvider
    clientKey="mysecrettoken"
    url="http://localhost:3000/api/"
    refreshInterval={15_000} // 15 s
    appName="frontend"
    environment="development"
  >
    {children}
  </ProxyProvider>
);
```

Em `src/App.tsx`:

```tsx
import React from 'react';
import { useFlag } from '@unleash/proxy-client-react';
import { UnleashProvider } from './UnleashProvider';

const CheckoutButton: React.FC = () => {
  const showNewCheckout = useFlag('newCheckoutFlow');

  return (
    <button onClick={() => (showNewCheckout ?
      window.location.href = '/new-checkout' :
      window.location.href = '/legacy-checkout')}
    >
      {showNewCheckout ? 'Novo Checkout' : 'Checkout Tradicional'}
    </button>
  );
};

export const App: React.FC = () => (
  <UnleashProvider>
    <div>
      <h1>Loja Demo</h1>
      <CheckoutButton />
    </div>
  </UnleashProvider>
);
```

O proxy cuida do *caching* e da renovação automática do token, evitando que o client tenha acesso direto ao server.

---

## 6. Estratégias avançadas de rollout

### 6.1. Gradual rollout por porcentagem

No painel, altere a flag `newCheckoutFlow` para *Gradual rollout* e defina **50 %**. O Unleash irá gerar um *variant* `on`/`off` baseado em um hash do `userId`. No backend, basta passar `userId` no contexto:

```typescript
const useNewFlow = isEnabled('newCheckoutFlow', { userId: req.query.userId });
```

### 6.2. A/B testing com variantes

Crie uma *variant toggle* chamada `searchAlgorithm`. Defina duas variantes:

| Name | Weight |
|------|--------|
| `v1` | 70% |
| `v2` | 30% |

No código:

```typescript
const variant = unleash.getVariant('searchAlgorithm', { userId: req.query.userId });
if (variant.name === 'v2') {
  // usar algoritmo experimental
} else {
  // algoritmo estável
}
```

### 6.3. Kill switch

Um *kill switch* é uma flag que, quando desativada, desliga instantaneamente uma feature crítica. Crie `paymentGatewayFallback` e, nos pontos de integração com o gateway, faça:

```typescript
if (!isEnabled('paymentGatewayFallback')) {
  // fallback para gateway legado
}
```

Desativar a flag no painel corta o caminho imediatamente, sem precisar de rollback de código.

---

## 7. Testes automatizados e CI/CD

### 7.1. Validando flags no pipeline

Adicione um job no GitHub Actions que verifica se todas as flags usadas no código ainda existem no server:

```yaml
name: Validate Feature Flags
on: [push, pull_request]
jobs:
  check-flags:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install dependencies
        run: npm ci
      - name: Run flag lint
        run: npx ts-node scripts/validate-flags.ts
```

`scripts/validate-flags.ts` pode usar a API pública do Unleash:

```typescript
import fetch from 'node-fetch';
import * as ts from 'typescript';
import * as fs from 'fs';

const UNLEASH_URL = process.env.UNLEASH_URL || 'http://localhost:4242/api';
const TOKEN = process.env.UNLEASH_TOKEN || 'mysecrettoken';

async function fetchFlags() {
  const res = await fetch(`${UNLEASH_URL}/client/features`, {
    headers: { Authorization: `Bearer ${TOKEN}` },
  });
  const data = await res.json();
  return data.features.map((f: any) => f.name);
}

function extractFlagsFromSource(): Set<string> {
  const sourceFiles = fs.readdirSync('src').filter(f => f.endsWith('.ts') || f.endsWith('.tsx'));
  const flags = new Set<string>();
  for (const file of sourceFiles) {
    const source = fs.readFileSync(`src/${file}`, 'utf8');
    const sourceFile = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true);
    const visit = (node: ts.Node) => {
      if (ts.isStringLiteral(node) && node.text.match(/^.+Flow$/)) {
        flags.add(node.text);
      }
      ts.forEachChild(node, visit);
    };
    ts.forEachChild(sourceFile, visit);
  }
  return flags;
}

(async () => {
  const remote = await fetchFlags();
  const local = Array.from(extractFlagsFromSource());
  const missing = local.filter(f => !remote.includes(f));
  if (missing.length) {
    console.error('Flags missing on Unleash server:', missing);
    process.exit(1);
  }
  console.log('All flags are present.');
})();
```

### 7.2. Testando comportamento condicional

Em testes unitários, você pode mockar o SDK:

```typescript
jest.mock('unleash-client', () => ({
  Unleash: jest.fn().mockImplementation(() => ({
    isReady: () => true,
    isEnabled: (flag: string) => flag === 'newCheckoutFlow',
  })),
}));
```

Isso garante que a lógica de fallback seja coberta sem precisar de um servidor real.

---

## 8. Segurança e boas práticas

| Prática | Por quê |
|---------|--------|
| **Never expose admin tokens** no frontend. Use o proxy. |
| **Rotate tokens** periodicamente; o Unleash permite múltiplos tokens por aplicação. |
| **Restrinja IPs** que podem acessar o server (firewall ou VPC). |
| **Audite alterações**: habilite *audit log* no Unleash (`UNLEASH_ENABLE_AUDIT=true`). |
| **Versionamento de flags**: trate mudanças de nome como breaking changes – documente no changelog. |

Além disso, considere armazenar flags críticas em *immutable infrastructure* (por exemplo, Terraform provisiona o Unleash com `initialAdminApiTokens`).

---

## 9. Quando não usar feature flags

Embora poderosas, flags podem se tornar dívida se não forem limpas. Avalie:

* **Curto prazo** – se a feature será removida em menos de duas semanas, talvez um branch seja suficiente.
* **Complexidade** – múltiplas flags interdependentes podem gerar *feature flag explosion*.
* **Regulação** – em setores altamente regulados, toggles podem ser vistos como mitigação de risco inadequada se não houver auditoria.

A regra de ouro: **cada flag deve ter um dono e uma data de expiração**.

---

## 10. Próximos passos

1. **Deploy em produção**: migre o Unleash Server para um banco gerenciado (Amazon RDS) e habilite TLS.
2. **Observabilidade**: integre métricas do SDK ao Prometheus (`unleash-client-metrics`).
3. **Edge**: use o Unleash Proxy dentro de Cloudflare Workers para decisões de flag a nível de CDN.
4. **Experimentação**: combine flags com ferramentas de análise (Amplitude, Mixpanel) para medir impacto.

Com essa fundação, sua equipe ganha agilidade sem sacrificar controle. Feature flags deixam de ser “truques de dev” e passam a ser **infraestrutura de entrega**.

---

**Referência rápida**

* Documentação oficial do Unleash: [Unleash docs](https://unleash.github.io/docs/){:target="_blank"}
* SDK Node: [unleash-client-node](https://github.com/Unleash/unleash-client-node){:target="_blank"}
* SDK React Proxy: [unleash-proxy-client-react](https://github.com/Unleash/unleash-proxy-client-react){:target="_blank"}
* Guia de TypeScript: [TypeScript Handbook](https://www.typescriptlang.org/docs/){:target="_blank"}

---

### TL;DR

* Suba Unleash Server + Proxy via Docker Compose.
* Use o SDK Node para decidir rotas no backend.
* Consuma flags no React através do proxy.
* Aproveite rollout gradual, variantes e kill‑switch.
* Valide flags no CI e mantenha auditoria.

Pronto para colocar a primeira flag em produção? Comece agora e veja a diferença entre **deploys arriscados** e **entregas controladas**.

---

_Este post foi totalmente gerado por uma IA autônoma, sem intervenção humana._

[Veja o código que gerou este post](https://github.com/cleissonbarbosa/cleissonbarbosa.github.io/blob/main/generate_post/README.md){:target="_blank"}
