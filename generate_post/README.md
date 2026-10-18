# Generate Post

Sistema que gera os posts do blog com IA, usando só APIs com plano gratuito.

- **Post técnico** (quarta e sábado): o modelo escolhe um tema diferente dos 15 posts mais recentes e escreve o post completo.
- **Resumo semanal** (domingo): coleta as notícias da semana no Hacker News e em feeds RSS de tecnologia, e o modelo escreve o resumo citando cada notícia como `[n]`. As citações viram links para a URL original, e a seção "Fontes" lista só o que foi citado.

## Provedores

| Etapa | Provedor | Modelos, em ordem de preferência |
|---|---|---|
| Texto | Google Gemini (free tier) | `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3-flash-preview`, `gemini-2.5-flash` |
| Texto (reserva) | Cloudflare Workers AI | `@cf/openai/gpt-oss-120b`, `@cf/google/gemma-4-26b-a4b-it` |
| Imagem | Cloudflare Workers AI | `flux-2-klein-9b`, `flux-2-klein-4b`, `lucid-origin`, `flux-1-schnell` |
| Notícias | Hacker News (API Algolia) + feeds RSS/Atom | sem chave |

Cada provedor tenta os modelos na ordem. Um modelo aposentado (404), uma resposta truncada ou fora do formato passa para o próximo. Só se todos os modelos Gemini falharem entra o Workers AI. Se nenhuma imagem for gerada, o post sai com `assets/img/posts/ia-generated.png`.

O modelo responde em JSON (`title`, `description`, `categories`, `tags`, `image_prompt`, `content`). O código valida o conteúdo e grava o front matter com valores entre aspas, então nenhum texto do modelo consegue quebrar o YAML do Jekyll.

## Configuração

```bash
export GEMINI_API_KEY="sua-chave-da-api-gemini"
export CF_AI_API_KEY="seu-token-da-api-cloudflare"   # Workers AI: imagens e texto reserva
export CF_ACCOUNT_ID="seu-id-da-conta-cloudflare"
```

No plano Workers Free há 10.000 neurons por dia. Uma imagem no `flux-2-klein-9b` custa cerca de 1.400, e um post no `gpt-oss-120b` cerca de 500.

## Uso

```bash
python generate_post.py                  # post técnico
python generate_post.py --weekly-digest  # resumo semanal
python generate_post.py --weekly-digest --dry-run  # imprime o prompt com as notícias, sem chamar IA
```

Para atualizar modelos ou feeds, edite as listas `_MODELS` em `adapters/api/` e `_FEEDS` em `adapters/news/feed_news_source.py`.

## Estrutura

- `core/use_cases/prompts.py`: persona, regras e formato de saída dos prompts
- `core/use_cases/drafts.py`: validação do JSON, slug e links das citações
- `adapters/api/`: Gemini, Workers AI (texto e imagem) e a cadeia de fallback
- `adapters/news/`: coleta de notícias
- `adapters/repositories/file_post_repository.py`: leitura e escrita dos arquivos em `_posts/`

## Testes

```bash
python -m unittest discover -s generate_post/tests -t .
```

## Integração com GitHub Actions

Os workflows `generate-post.yml` e `generate-weekly-digest.yml` rodam o script e leem as saídas gravadas no arquivo da variável `GITHUB_OUTPUT`.
