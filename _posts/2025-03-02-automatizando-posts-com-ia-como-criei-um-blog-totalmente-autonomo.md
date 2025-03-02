---
title: "Automatizando Posts com IA sem gastar 1 real"
author: cleissonb
date: 2025-03-02 00:00:00 -0300
image:
  path: /assets/img/posts/0e8b3761-2e70-6843-80fd-4cf7dec6755e.png
  alt: "Automatizando Posts com IA sem gastar 1 real"
categories: [Automação, IA, Python]
tags: [inteligência artificial, automação, python, gemini api, cloudflare workers ai, github actions, clean architecture]
pin: false
---

## Introdução

Sempre acreditei que a automação é o caminho para liberar nossa mente para tarefas mais criativas. Como desenvolvedor e entusiasta de IA, decidi aplicar esse princípio ao meu próprio blog. O resultado? Um sistema completamente autônomo que gera dois posts técnicos por semana, sem qualquer intervenção humana. Neste artigo, vou compartilhar como construí esse sistema usando APIs gratuitas do [Google Gemini](https://ai.google.dev/gemini-api/docs/quickstart){:target="_blank"} e [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai){:target="_blank"}, seguindo os princípios da Clean Architecture.

## Por que Automatizar a Criação de Conteúdo?

Todos os projetos que faço e compartilho neste blog têm como objetivo meu crescimento técnico pessoal. Este blog também funciona como um "dump" de coisas que estou estudando e que gostaria de deixar registrado. Automações com IAs é o que estou estudando nesse momento, mas não queria apenas um gerador de texto aleatório – precisava de um sistema que:

1. **Criasse conteúdo técnico de qualidade** sobre programação, desenvolvimento e tecnologias
2. **Mantivesse a consistência** com o estilo dos meus posts anteriores
3. **Funcionasse de forma totalmente autônoma**, sem precisar ficar mexendo toda hora
4. **Utilizasse recursos gratuitos** para não gastar nada 
5. **Seguisse boas práticas de engenharia de software**

## R. Daneel Olivaw: O Autor Robótico

Para dar uma identidade própria aos posts gerados automaticamente, criei um alter ego para a IA: [R. Daneel Olivaw](https://en.wikipedia.org/wiki/R._Daneel_Olivaw){:target="_blank"}. Esse nome não foi escolhido por acaso - é uma homenagem ao personagem robô das obras de [Isaac Asimov](https://pt.wikipedia.org/wiki/Isaac_Asimov){:target="_blank"}, onde a inicial "R" significa "Robô". Nos contos de Asimov, Daneel é um robô humanóide avançado capaz de se misturar à sociedade humana.

Cada post gerado automaticamente é assinado por "[R. Daneel Olivaw](https://en.wikipedia.org/wiki/R._Daneel_Olivaw){:target="_blank"}", enquanto os que escrevo manualmente continuam com minha assinatura pessoal. Essa distinção clara permite que os leitores saibam na hora a origem do conteúdo que estão consumindo.

Além disso, todo post gerado por IA contém uma nota ao final informando explicitamente que foi totalmente gerado por uma IA autônoma, sem intervenção humana, junto com um link para o código-fonte que tornou isso possível.

## A Arquitetura do Sistema

Decidi construir o sistema seguindo os princípios da [Clean Architecture](https://medium.com/@gabrielfernandeslemos/clean-architecture-uma-abordagem-baseada-em-princ%C3%ADpios-bf9866da1f9c){:target="_blank"} para garantir um código organizado, testável e fácil de manter. Veja como está estruturado:

```
generate_post/
├── __init__.py
├── main.py             # Ponto de entrada da aplicação
├── adapters/           # Implementações concretas das interfaces
│   ├── api/            # Serviços de API externos
│   ├── cli/            # Interface de linha de comando
│   └── repositories/   # Implementações de repositórios
├── config/             # Configurações da aplicação
├── core/               # Regras de negócio independentes
│   ├── domain/         # Entidades e interfaces do domínio
│   ├── use_cases/      # Casos de uso da aplicação
└── utils/              # Utilitários diversos
```

Essa estrutura permite uma clara separação de responsabilidades e torna o sistema facilmente extensível para novos recursos no futuro.

## Como Funciona o Sistema

O fluxo de funcionamento é surpreendentemente simples:

1. **Obtenção de contexto**: O sistema dá uma olhada nos meus posts anteriores para manter o mesmo estilo e temas 
2. **Geração de conteúdo**: A API do [Google Gemini](https://ai.google.dev/gemini-api/docs/quickstart){:target="_blank"} cria o texto do post com base nesse contexto
3. **Geração de imagens**: A API do [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai){:target="_blank"} cria uma imagem de capa legal para o post
4. **Criação de arquivo markdown**: O sistema formata tudo direitinho no padrão [Jekyll](https://jekyllrb.com/){:target="_blank"} do blog
5. **Publicação**: Tudo é enviado para o GitHub via pull request, pronto para o copilot revisar
6. **Automação**: O GitHub Actions cuida de toda a parte de execução e publicação

### A Magia do GitHub Actions

A verdadeira automação vem do [GitHub Actions](https://github.com/features/actions){:target="_blank"}, que executa todo esse fluxo de forma programada:

```yml
name: Generate weekly posts

on:
  schedule:
    - cron: "0 22 * * 3,6" # Toda quarta e sábado às 22:00 UTC
  workflow_dispatch:

...
```

Configurei para que sejam gerados [dois posts semanais](https://crontab.cronhub.io/){:target="_blank"} - às quartas e sábados - sem que eu precise levantar um dedo. O GitHub Actions cuida de tudo, desde rodar o script até criar a pull request com o novo post.

## Gerando Conteúdo com o Google Gemini

O coração do sistema é o gerador de conteúdo que utiliza o Google Gemini - uma das melhores IAs generativas disponíveis gratuitamente. O mais legal é que o sistema usa randomização para escolher entre diferentes [modelos do Gemini](https://ai.google.dev/gemini-api/docs/models/gemini?hl=pt-br){:target="_blank"}:

```python
# Seleção de modelo
model_name = random.choice(
    [
        "gemini-1.5-flash-001",
        "gemini-2.0-flash-001",
        "gemini-2.0-pro-exp-02-05",
        "gemini-2.0-flash-thinking-exp-01-21",
    ]
)
```

Isso traz mais variação aos textos gerados, evitando que os posts fiquem muito parecidos entre si.

O prompt que uso para gerar os posts é cuidadosamente elaborado para:

1. Criar um título cativante em português
2. Sugerir categorias e tags relevantes
3. Estruturar o post com introdução, desenvolvimento e conclusão
4. Incluir exemplos práticos de código quando relevante
5. Adicionar links e referências externas
6. Manter um tom conversacional em primeira pessoa

## Gerando Imagens com Cloudflare Workers AI

Para as imagens de capa, utilizo o [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai){:target="_blank"} - outro serviço com uma generosa camada gratuita. O sistema gera uma imagem baseada no título e conteúdo do post, criando uma identidade visual única para cada artigo.

O mais bacana é que tanto o [Gemini](https://ai.google.dev/gemini-api/docs/quickstart){:target="_blank"} quanto o [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai){:target="_blank"} oferecem APIs gratuitas com limites bem generosos, permitindo que todo o sistema funcione sem gastar um centavo.

## Desafios e Lições Aprendidas

O desenvolvimento do sistema não foi moleza:

1. **Consistência de estilo**: Garantir que os posts mantivessem um estilo parecido com os meus próprios textos foi um desafio que exigiu várias tentativas no prompt.

2. **Limitações de API**: As APIs gratuitas têm limites de uso, então precisei implementar estratégias de retry e backoff para lidar com falhas.

3. **Qualidade das imagens**: Criar prompts que gerassem imagens bonitas e relevantes para cada post exigiu bastante experimentação (ainda não estou satisfeito com as imagens geradas).

4. **Metadados do Jekyll**: O sistema precisa gerar corretamente os metadados no formato Front Matter do [Jekyll](https://jekyllrb.com/){:target="_blank"} para que o blog funcione direitinho.

Uma das maiores lições foi perceber o quão importante é o prompt engineering para obter resultados de qualidade. Um bom prompt faz toda a diferença na qualidade do conteúdo gerado. O que me ajudou nesse ponto foi ter ajudado na tradução do projeto [Prompt Engineering Guide](https://github.com/dair-ai/Prompt-Engineering-Guide){:target="_blank"}.

## Resultados e Métricas

O sistema tem funcionado muito bem:

- **Geração consistente**: Dois posts por semana, sem falhas
- **Qualidade de conteúdo**: Posts tecnicamente precisos e bem estruturados
- **Economia de tempo**: Aproximadamente 8-10 horas economizadas por semana
- **Custo zero**: Usando apenas recursos gratuitos

Fiquei impressionado com a qualidade dos posts gerados. Em alguns casos, a IA produziu conteúdo que eu mesmo não teria pensado em escrever, trazendo uma diversidade interessante aos temas do blog.

## Transparência e Identificação

Um aspecto importante deste projeto é a transparência com os leitores. Para isso, implementei algumas características distintivas nos posts gerados automaticamente:

1. **Autoria explícita**: Cada post gerado pela IA é claramente identificado como sendo de autoria de "R. Daneel Olivaw (Autonomous AI)" no metadado do front matter do [Jekyll](https://jekyllrb.com/){:target="_blank"}.

2. **Tag especial**: Todos os posts gerados automaticamente recebem a tag "ai-generated", facilitando sua identificação e filtragem.

3. **Nota de rodapé**: Ao final de cada post gerado por IA, é incluída automaticamente a seguinte nota:

```markdown
_Este post foi totalmente gerado por uma IA autônoma, sem intervenção humana._

[Veja o código que gerou este post](https://github.com/cleissonbarbosa/cleissonbarbosa.github.io/blob/main/generate_post/README.md)
```

Essa abordagem garante total transparência com os leitores e também serve como uma forma interessante de mostrar o potencial da geração de conteúdo por IA.

## Como Replicar Esse Sistema

Se você quer criar seu próprio blog autônomo, aqui estão os passos básicos:

1. **Configure as APIs**:
   - Consiga uma chave para o Google Gemini API [aqui](https://ai.google.dev/gemini-api/docs/quickstart){:target="_blank"}
   - Crie uma conta no Cloudflare e configure o Workers AI [seguindo este guia](https://developers.cloudflare.com/workers-ai/){:target="_blank"}

2. **Clone o repositório**:
   ```bash
   git clone https://github.com/cleissonbarbosa/cleissonbarbosa.github.io
   cd cleissonbarbosa.github.io/generate_post
   ```

3. **Configure as variáveis de ambiente**:
   ```bash
   export GEMINI_API_KEY="sua-chave-da-api-gemini"
   export CF_AI_API_KEY="seu-token-da-api-cloudflare"
   export CF_ACCOUNT_ID="seu-id-da-conta-cloudflare"
   ```

4. **Execute o script**:
   ```bash
   python generate_post/main.py
   ```

5. **Configure o GitHub Actions** para automatizar a geração seguindo o modelo no meu repositório.

## Conclusão

Criar um sistema de geração autônoma de posts foi uma experiência fascinante que combinou meu interesse por automação, IA e arquitetura de software. O mais impressionante é como as APIs gratuitas do Google e Cloudflare possibilitaram construir algo tão funcional sem gastar nada.

Este projeto demonstra como podemos usar a IA não apenas como um assistente, mas como um criador autônomo de conteúdo. É claro que sempre haverá espaço para a escrita humana - e continuo escrevendo posts manualmente quando tenho vontade. Mas ter um sistema que mantém meu blog ativo enquanto foco em outros projetos é uma vantagem incrível.

O futuro da criação de conteúdo provavelmente será uma mistura de contribuições humanas e de IA. Este projeto é apenas um pequeno passo nessa direção, explorando o que é possível hoje com as ferramentas disponíveis gratuitamente.

## Links

- [Repositório do projeto](https://github.com/cleissonbarbosa/cleissonbarbosa.github.io){:target="_blank"}
- [Google Gemini API](https://ai.google.dev/){:target="_blank"}
- [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai){:target="_blank"}
- [GitHub Actions](https://github.com/features/actions){:target="_blank"}
- [Obras de Isaac Asimov sobre robôs](https://en.wikipedia.org/wiki/Robot_series){:target="_blank"}

---

_Você pode explorar o código completo deste sistema no [repositório do GitHub](https://github.com/cleissonbarbosa/cleissonbarbosa.github.io/tree/main/generate_post){:target="_blank"}. Pull requests são bem-vindas!_