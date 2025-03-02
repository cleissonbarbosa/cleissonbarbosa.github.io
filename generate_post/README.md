# Generate Post

Um sistema automatizado para geração de posts de blog utilizando IA, seguindo os princípios da Clean Architecture.

## Estrutura do Projeto

```
generate_post/
├── __init__.py
├── main.py             # Ponto de entrada da aplicação
├── README.md           # Este arquivo
├── adapters/           # Implementações concretas das interfaces
│   ├── api/            # Serviços de API externos
│   ├── cli/            # Interface de linha de comando
│   └── repositories/   # Implementações de repositórios
├── config/             # Configurações da aplicação
├── core/               # Regras de negócio independentes
│   ├── domain/         # Entidades e interfaces do domínio
│   │   ├── entities/   # Entidades de domínio
│   │   └── interfaces/ # Interfaces de repositórios e serviços
│   └── use_cases/      # Casos de uso da aplicação
└── utils/              # Utilitários diversos
```

## Requisitos

- Python 3.9+
- Chaves de API:
  - Google Gemini API (para geração de conteúdo)
  - Cloudflare Workers AI (para geração de imagens)

## Configuração

Defina as variáveis de ambiente necessárias:

```bash
export GEMINI_API_KEY="sua-chave-da-api-gemini"
export CF_AI_API_KEY="seu-token-da-api-cloudflare"
export CF_ACCOUNT_ID="seu-id-da-conta-cloudflare"
```

## Uso

Execute o script principal:

```bash
./generate_post/main.py
```

Ou como módulo Python:

```bash
python -m generate_post.main
```

## Integração com GitHub Actions

Para uso com GitHub Actions, a saída será gravada no arquivo definido pela variável `GITHUB_OUTPUT`.

## Personalização

- Para modificar o prompt de geração de conteúdo, edite `adapters/api/gemini_content_service.py`
- Para modificar o prompt de geração de imagem, edite `adapters/api/cloudflare_image_service.py`
- Para alterar o formato do post, edite `adapters/repositories/file_post_repository.py`