---
title: "Automatizando Posts com IA sem gastar 1 real"
author: cleissonb
date: 2025-03-02 00:00:00 -0300
image:
  path: /assets/img/posts/0e8b3761-2e70-6843-80fd-4cf7dec6755e.png
  alt: "Automatizando Posts com IA sem gastar 1 real"
categories: [Automação, IA, Python]
tags: [inteligência artificial, automação, python, gemini api, cloudflare workers ai, github actions, clean architecture]
pin: true
---

## Introdução

Eu tenho uma implicância antiga com tarefas repetitivas. Quando percebo que estou fazendo a mesma coisa pela terceira vez, minha reação quase automática é abrir o editor e tentar transformar aquilo em script. Com o blog aconteceu a mesma coisa. Eu queria continuar publicando com frequência, mas sem transformar escrita em uma esteira manual. Foi daí que saiu a ideia de usar [Google Gemini](https://ai.google.dev/gemini-api/docs/quickstart){:target="_blank"} e [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai){:target="_blank"} para gerar posts técnicos sem gastar nada.

Desde a primeira versão desse experimento, mexi bastante no projeto. O que antes era um fluxo único virou dois caminhos diferentes: um para artigos técnicos completos e outro para um resumo semanal de notícias sobre desenvolvimento, IA e segurança. No meio disso, também fui aparando as arestas mais chatas. Os prompts ficaram melhores, a geração de imagem parou de quebrar por qualquer detalhe, e a publicação agora passa por validações antes do merge. Hoje o resultado está bem menos com cara de demo e bem mais com cara de pipeline editorial.

## Atualização: o que mudou no gerador

O projeto de hoje já está bem diferente da versão original. As mudanças que mais mexeram na qualidade do resultado foram estas:

1. Agora existe um modo separado para gerar um digest semanal com notícias reais da última semana.
2. O resumo semanal passou a usar Google Search grounding no Gemini para não ficar solto de fonte.
3. O fluxo padrão olha para o último post publicado antes de escrever o próximo, o que ajuda a evitar repetição de tema e abordagem.
4. A geração de imagens ficou mais resistente porque o pipeline alterna entre modelos diferentes da Cloudflare e trata respostas em formatos distintos.
5. O GitHub Actions ganhou validações de front matter, corpo e imagem antes de liberar auto-merge.

## Por que eu quis automatizar a criação de conteúdo?

Este blog sempre funcionou como meu caderno de laboratório. Eu escrevo aqui sobre coisas que estou estudando, testando ou simplesmente tentando entender melhor. Como eu estava mergulhado em automação com IA, fazia sentido usar o próprio blog como campo de teste. Só que eu não queria um gerador que cuspisse texto técnico genérico. O sistema precisava:

1. escrever sobre programação, desenvolvimento e tecnologia de um jeito que eu realmente toparia publicar;
2. manter algum parentesco com o tom que eu uso nos textos manuais;
3. rodar sozinho, sem me transformar em operador de esteira;
4. caber no orçamento de zero reais;
5. continuar organizado o bastante para eu não me arrepender seis meses depois.

## R. Daneel Olivaw: o autor robótico

Dar um nome para a IA foi meio brincadeira, meio decisão editorial. Escolhi [R. Daneel Olivaw](https://en.wikipedia.org/wiki/R._Daneel_Olivaw){:target="_blank"} por causa do personagem robô das obras de [Isaac Asimov](https://pt.wikipedia.org/wiki/Isaac_Asimov){:target="_blank"}. A inicial "R" vem de "robô", e a referência fazia sentido para um sistema que escreve sozinho, mas não tenta fingir que é humano.

Hoje isso aparece de um jeito simples: os posts automáticos usam `author: ia` no front matter, e o site resolve esse valor em `_data/authors.yml` para R. Daneel Olivaw (Autonomous AI). Os textos escritos manualmente continuam com minha assinatura normal. Essa separação me parece importante. Eu não queria poluir o template do blog, mas também não queria misturar autoria humana com conteúdo gerado por pipeline como se fosse a mesma coisa.

Também deixei uma nota no fim de cada post gerado por IA, com um link para o código que tornou aquilo possível. Transparência aqui não é detalhe cosmético. É parte do experimento.

## Como o fluxo funciona hoje

Hoje o processo está mais ou menos assim:

1. No fluxo tradicional, o sistema busca o último post publicado e usa título, URL e um resumo do conteúdo como contexto para o próximo artigo.
2. O [Gemini](https://ai.google.dev/gemini-api/docs/quickstart){:target="_blank"} gera o texto principal tentando fugir do assunto e da abordagem do post anterior.
3. Quando eu executo com `--weekly-digest`, entra um serviço separado que busca notícias reais da semana, organiza os temas e injeta as fontes no resultado.
4. A [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai){:target="_blank"} gera a imagem de capa, com fallback para a imagem padrão do blog se as credenciais não estiverem disponíveis.
5. O sistema monta o markdown no formato do [Jekyll](https://jekyllrb.com/){:target="_blank"}, adiciona a tag `ai-generated` e inclui a nota de transparência no final.
6. O GitHub Actions abre uma pull request, valida o que foi gerado e só depois faz o merge automático.

### Onde o GitHub Actions entra nisso

A automação de verdade mora no [GitHub Actions](https://github.com/features/actions){:target="_blank"}. Dá para rodar tudo localmente, claro, mas é o pipeline que evita que eu vire operador de rotina. O resumo semanal, por exemplo, ganhou uma agenda própria:

```yml
name: Generate Weekly News Digest

on:
  schedule:
      - cron: "0 20 * * 0" # Todo domingo às 20:00 UTC
  workflow_dispatch:

...
```

Além dele, mantive um workflow separado para os posts tradicionais. Hoje a coisa ficou mais organizada: o fluxo padrão pode ser disparado manualmente quando eu quiser gerar um artigo novo, enquanto o resumo semanal roda sozinho aos domingos. Nos dois casos, o pipeline gera o conteúdo, salva post e imagem como artifact, cria uma pull request e só libera o auto-merge depois das validações.

## Como estou usando o Google Gemini

O Gemini continua sendo o núcleo do gerador, só que agora em dois caminhos bem diferentes.

Para os posts completos, o serviço padrão alterna entre modelos mais novos do [Gemini](https://ai.google.dev/gemini-api/docs/models/gemini?hl=pt-br){:target="_blank"}:

```python
_MODELS = [
   "gemini-2.5-flash",
   "gemini-2.5-pro",
   "gemini-3-flash-preview",
]
```

Mas a principal melhoria não foi a lista de modelos. Foi o contexto. Em vez de pedir um artigo isolado, eu passo para o modelo o último post publicado, com URL e resumo. Isso força o gerador a escolher outro tema, variar a abordagem e não reciclar assunto com tanta facilidade. Parece detalhe pequeno, mas fez bastante diferença.

Hoje o prompt do fluxo padrão pede, entre outras coisas:

1. um título bom em português;
2. categorias e tags coerentes;
3. uma estrutura de artigo que faça sentido;
4. exemplos práticos quando couber;
5. links no formato do blog;
6. primeira pessoa;
7. opinião, experiência e analogia suficientes para o texto não soar como manual de produto.

Para o resumo semanal, eu separei um serviço próprio com modelos que suportam [Google Search grounding](https://ai.google.dev/gemini-api/docs/grounding?hl=pt-br){:target="_blank"} de maneira mais confiável:

```python
_GROUNDED_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash"]
```

Esse fluxo pede ao Gemini para buscar notícias reais dos últimos 7 dias, agrupar os assuntos por tema e escrever um texto entre 1500 e 3000 palavras. O pós-processamento foi a parte chata e, por isso mesmo, a mais importante. O código lê o `groundingMetadata`, encaixa citações inline só onde a busca realmente sustenta o trecho, remove links inventados pelo modelo e monta uma seção final de Fontes. Sem isso, o digest ficava convincente, mas frouxo. Com isso, ele ficou bem mais útil.

## Como estou gerando as imagens

Para as capas, eu continuo usando o [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai){:target="_blank"}, mas aprendi rápido que depender de um único modelo era um jeito eficiente de fazer a automação falhar no pior momento. Hoje o pipeline alterna entre `flux-1-schnell`, `lucid-origin` e `phoenix-1.0`, cada um com parâmetros próprios.

Também precisei tratar a parte menos glamourosa da integração. A API da Cloudflare às vezes responde com imagem binária direta e às vezes com JSON em base64. Não é difícil de resolver, mas é o tipo de detalhe que transforma automação em loteria quando você ignora. Além disso, deixei um fallback para a imagem padrão do blog caso as credenciais não estejam disponíveis. Prefiro publicar com uma capa genérica do que quebrar o fluxo inteiro por causa dessa etapa.

O ponto continua o mesmo do começo: tanto o [Gemini](https://ai.google.dev/gemini-api/docs/quickstart){:target="_blank"} quanto o [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai){:target="_blank"} me deixaram tocar o projeto sem gastar dinheiro.

## O que deu trabalho de verdade

O projeto parece bem alinhado quando aparece resumido em diagrama, mas os problemas reais foram bem mais específicos:

1. Consistência de estilo. Fazer o texto lembrar a minha voz sem cair num clone ruim exigiu muita iteração de prompt e bastante contexto.
2. Instabilidade de API. Serviço gratuito é ótimo até começar a responder fora do padrão ou limitar uso. Retry com exponential backoff virou obrigação.
3. Grounding do Gemini. Nem todo modelo faz busca com a mesma confiabilidade, então eu precisei separar explicitamente os que funcionavam bem o suficiente para o digest.
4. Citações no digest. O `groundingSupports` trabalha com byte offsets em UTF-8. Se eu limpasse o texto antes de injetar as citações, os índices quebravam.
5. Descobrir o último post. No começo eu usei `mtime` do arquivo. Foi um erro. Depois de checkout e merge, a noção de "mais recente" ficava confusa. Ordenar pelo nome do arquivo com prefixo de data resolveu isso do jeito certo.
6. Qualidade do pipeline. Gerar o post era só metade do trabalho. O workflow também precisava validar front matter, tamanho mínimo do corpo e integridade da imagem antes de liberar merge.

Se teve uma lição central aqui, foi esta: prompt ruim cobra duas vezes. Primeiro na geração. Depois na limpeza. Ter ajudado na tradução do [Prompt Engineering Guide](https://github.com/dair-ai/Prompt-Engineering-Guide){:target="_blank"} me deu uma base boa para mexer nisso sem transformar o projeto em um festival de tentativa aleatória.

## Onde o projeto está hoje

Hoje eu já não vejo isso como um brinquedo para fazer post sozinho. Vejo como um pipeline editorial pequeno, mas funcional. Ele já tem:

- um fluxo para artigos técnicos sob demanda;
- um fluxo para digest semanal aos domingos;
- mais variedade temática porque o gerador olha para o último post antes de escrever;
- citações inline e seção de fontes no resumo semanal;
- pull request, validação de arquivo, validação de imagem e auto-merge;
- custo zero, usando apenas os recursos gratuitos das plataformas.

O resumo semanal foi a parte que mais me surpreendeu. Ele saiu do terreno da curiosidade e virou algo que eu realmente abriria para acompanhar a semana sem precisar caçar notícia em vinte abas.

## Transparência com quem lê

Se tem uma decisão da qual eu não abro mão aqui, é deixar claro quando o texto veio de um pipeline autônomo. Para isso, mantive algumas regras simples:

1. Cada post gerado pela IA usa a chave `author: ia`, que o site resolve para "R. Daneel Olivaw (Autonomous AI)".
2. Todo post automático recebe a tag `ai-generated`.
3. No fim de cada texto entra a seguinte nota:

```markdown
_Este post foi totalmente gerado por uma IA autônoma, sem intervenção humana._

[Veja o código que gerou este post](https://github.com/cleissonbarbosa/cleissonbarbosa.github.io/blob/main/generate_post/README.md)
```
4. No digest semanal, além da autoria, o texto também ganha citações inline e uma seção final de fontes baseada no grounding do Gemini.

Eu acho esse ponto importante por honestidade mesmo. A graça do experimento está justamente em mostrar o que foi automatizado, não em esconder.

## Como replicar esse sistema

Se você quiser montar algo parecido, o caminho básico é este:

1. Configure as APIs.
   - Consiga uma chave para o Google Gemini API [aqui](https://ai.google.dev/gemini-api/docs/quickstart){:target="_blank"}.
   - Crie uma conta no Cloudflare e configure o Workers AI [seguindo este guia](https://developers.cloudflare.com/workers-ai/){:target="_blank"}.

2. Clone o repositório.
   ```bash
   git clone https://github.com/cleissonbarbosa/cleissonbarbosa.github.io
   cd cleissonbarbosa.github.io
   ```

3. Configure as variáveis de ambiente.
   ```bash
   export GEMINI_API_KEY="sua-chave-da-api-gemini"
   export CF_AI_API_KEY="seu-token-da-api-cloudflare"
   export CF_ACCOUNT_ID="seu-id-da-conta-cloudflare"
   ```

4. Execute o gerador.
   ```bash
   python generate_post.py
   ```

   Para gerar especificamente o resumo semanal:

   ```bash
   python generate_post.py --weekly-digest
   ```

5. Configure o GitHub Actions para automatizar os dois fluxos.
   - `generate-post.yml` para posts tradicionais.
   - `generate-weekly-digest.yml` para o resumo semanal com pull request, validação e auto-merge.

## Conclusão

Montar esse gerador foi divertido justamente porque misturou três coisas de que eu gosto: automação, IA e arquitetura de software. Mas, olhando hoje, o que mais me interessa no projeto não é a ideia de "blog que escreve sozinho". É a ideia de usar IA como parte de um processo editorial controlado, com contexto, validação e transparência.

Tem dias em que eu quero escrever tudo manualmente. Tem dias em que prefiro deixar o pipeline cuidar do trabalho repetitivo. Para mim, o ponto não é substituir uma coisa pela outra. É ganhar mais tempo para testar ideias, estudar assuntos novos e escrever quando eu realmente tiver algo meu para dizer.

## Links

- [Repositório do projeto](https://github.com/cleissonbarbosa/cleissonbarbosa.github.io){:target="_blank"}
- [Google Gemini API](https://ai.google.dev/){:target="_blank"}
- [Google Search grounding do Gemini](https://ai.google.dev/gemini-api/docs/grounding){:target="_blank"}
- [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai){:target="_blank"}
- [GitHub Actions](https://github.com/features/actions){:target="_blank"}
- [Obras de Isaac Asimov sobre robôs](https://en.wikipedia.org/wiki/Robot_series){:target="_blank"}

---

_Você pode explorar o código completo deste sistema no [repositório do GitHub](https://github.com/cleissonbarbosa/cleissonbarbosa.github.io/tree/main/generate_post){:target="_blank"}. Pull requests são bem-vindas!_