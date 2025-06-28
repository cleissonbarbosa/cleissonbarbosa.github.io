---
title: "Apresentando ASL Viewer: Uma Biblioteca React para Visualizar Workflows da AWS Step Functions"
author: cleissonb
date: 2025-06-28 00:00:00 -0300
image:
  path: /assets/img/posts/5874903e-49da-4ae5-836a-a1efdc4451a3.png
  alt: "Demonstração do ASL Viewer"
categories: [React, AWS, Frontend]
tags: [react, aws, step-functions, asl, typescript, frontend, visualization, open-source]
pin: true
---

## Introdução

Se você já trabalhou com AWS Step Functions, sabe o quão poderoso ele é para orquestrar processos complexos. No entanto, uma dificuldade que sempre encontrei foi a de exibir o status de um workflow de forma visual em uma aplicação frontend. Como um usuário poderia acompanhar em que etapa do processo um determinado job se encontra?

Foi para resolver esse problema que criei a **ASL Viewer**, uma biblioteca React de código aberto. O objetivo principal é permitir que desenvolvedores frontend possam facilmente renderizar e exibir workflows de Step Functions em suas aplicações. A ideia é que, no futuro, seja possível conectar a visualização com o estado real da execução na AWS, permitindo acompanhar o progresso em tempo real.

<div align="center">
    <img src="https://raw.githubusercontent.com/cleissonbarbosa/asl-viewer/main/assets/screenshot-complex-workflow.gif" alt="ASL Viewer Demo" style="width:100%; max-width:700px;"/>
</div>

## Funcionalidades Principais

A `asl-viewer` foi construída com TypeScript e oferece um conjunto robusto de funcionalidades para facilitar a vida dos desenvolvedores:

- 🎨 **Visualização Interativa:** Renderiza workflows ASL como grafos interativos.
- 🌓 **Suporte a Temas:** Vem com temas claro e escuro prontos para usar.
- ✅ **Validação de ASL:** Valida a sintaxe e a semântica do seu código ASL para garantir que está tudo certo.
- 🔄 **Layout Automático:** Organiza automaticamente o layout do grafo para a melhor visualização.
- 📱 **Responsivo:** Funciona bem em diferentes tamanhos de tela.
- 🖱️ **Interativo:** Suporta handlers de clique para estados e conexões, além de permitir arrastar e dar zoom.
- 📄 **Suporte a JSON e YAML:** Carregue seus workflows a partir de objetos, URLs ou arquivos locais em ambos os formatos.
- 🔧 **Extensível:** Fácil de customizar e estender, com suporte completo a TypeScript.

## Instalação e Uso Rápido

Para começar a usar a `asl-viewer` no seu projeto React, basta instalar o pacote via `npm` ou `yarn`:

```bash
npm install asl-viewer
# ou
yarn add asl-viewer
```

**Importante:** Você precisa importar o arquivo CSS para que o componente seja exibido corretamente.

```javascript
import "asl-viewer/dist/index.css";
```

Aqui está um exemplo básico de como usar o componente:

```tsx
import React from "react";
import { WorkflowViewer } from "asl-viewer";
import "asl-viewer/dist/index.css"; // CSS obrigatório

const workflow = {
  Comment: "Um exemplo simples e mínimo de um workflow",
  StartAt: "HelloWorld",
  States: {
    HelloWorld: {
      Type: "Pass",
      Result: "Hello World!",
      End: true,
    },
  },
};

function App() {
  return (
    <WorkflowViewer
      definition={workflow}
      theme="dark"
      width={800}
      height={600}
    />
  );
}
```

## Carregando Workflows de Diferentes Fontes

A biblioteca é flexível e permite carregar definições de workflows de várias fontes:

### Carregando de uma URL

```tsx
import React from "react";
import { WorkflowViewer } from "asl-viewer";
import "asl-viewer/dist/index.css";

function App() {
  const workflowUrl = "https://raw.githubusercontent.com/user/repo/main/workflow.json";
  return <WorkflowViewer url={workflowUrl} />;
}
```

### Carregando de um Arquivo (Upload)

```tsx
import React, { useState } from "react";
import { WorkflowViewer, FileUploader } from "asl-viewer";
import "asl-viewer/dist/index.css";

function App() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  return (
    <div>
      <FileUploader onFileSelect={setSelectedFile} />
      {selectedFile && <WorkflowViewer file={selectedFile} />}
    </div>
  );
}
```

## Desafios e Aprendizados

Desenvolver a `asl-viewer` foi uma jornada cheia de aprendizados:

1.  **Renderização de Grafos:** O maior desafio foi criar uma representação visual clara e eficiente para os grafos. Optei por usar a biblioteca [React Flow](https://reactflow.dev/){:target="_blank"}, que se mostrou incrivelmente poderosa para criar nós customizados, gerenciar o estado do grafo e lidar com interações complexas como zoom e arrastar.

2.  **Layout Automático:** Garantir que workflows complexos fossem exibidos de forma organizada exigiu a implementação de um algoritmo de layout. Estudei diferentes abordagens e acabei adaptando um algoritmo de layout em camadas (layered layout) para organizar os nós de forma hierárquica.

3.  **Compatibilidade com ASL:** O Amazon States Language tem muitas nuances. Dar suporte a todos os tipos de estados, regras de `Choice` e fluxos paralelos exigiu uma análise cuidadosa da especificação e a criação de uma camada de validação robusta.

4.  **API Flexível:** Um dos meus objetivos era criar uma API que fosse ao mesmo tempo simples para casos de uso básicos e poderosa para customizações avançadas. Encontrar esse equilíbrio foi fundamental para tornar a biblioteca útil para um público amplo.

## Conclusão

A `asl-viewer` nasceu para resolver um desafio prático: dar visibilidade sobre o andamento de processos complexos de backend diretamente na interface do usuário. Com ela, desenvolvedores frontend ganham uma ferramenta poderosa para exibir workflows de Step Functions de forma clara e intuitiva.

O projeto é de código aberto e a versão atual já estabelece uma base sólida. O próximo grande passo é evoluir da visualização estática para a dinâmica:

- **Implementar visualização da execução em tempo real:** Conectar com a AWS para destacar o estado atual do workflow (em execução, sucesso, falha).
- **Permitir ações interativas:** Adicionar a capacidade de, por exemplo, pausar ou retomar a execução de um workflow diretamente pela interface.
- **Melhorar a performance:** Otimizar a renderização para workflows com centenas de estados.
- **Adicionar suporte a plugins:** Criar um sistema de extensibilidade para customizar comportamentos e visualizações.

## Links

- [Repositório do Projeto no GitHub](https://github.com/cleissonbarbosa/asl-viewer){:target="_blank"}
- [Storybook com Exemplos Interativos](https://cleissonbarbosa.github.io/asl-viewer/){:target="_blank"}
- [Pacote no NPM](https://www.npmjs.com/package/asl-viewer){:target="_blank"}

---

_Você pode encontrar o código completo no nosso [repositório do GitHub](https://github.com/cleissonbarbosa/asl-viewer){:target="_blank"}. Ficarei feliz em receber contribuições e pull requests!_
