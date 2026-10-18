import json
from datetime import datetime, timezone
from unittest import mock

from generate_post.config.env_config import EnvConfig
from generate_post.core.domain.entities.news_item import NewsItem

ENV = EnvConfig(gemini_api_key="g", cf_api_token="t", cf_account_id="acc", github_output=None)

BODY = "Parágrafo com conteúdo técnico relevante. " * 80


def draft_json(**overrides) -> str:
    data = {
        "title": "Rust: ownership na prática",
        "description": "Um guia direto sobre ownership.",
        "categories": ["Programação", "Rust"],
        "tags": ["rust", "memória"],
        "image_prompt": "a crab guarding memory blocks",
        "content": BODY,
    }
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


def http_response(status: int, payload=None, content: bytes | None = None, headers=None):
    response = mock.Mock(status_code=status, headers=headers or {"Content-Type": "application/json"})
    response.text = json.dumps(payload) if payload is not None else ""
    response.json.return_value = payload
    response.content = content if content is not None else response.text.encode()
    return response


def news(n: int) -> list[NewsItem]:
    return [
        NewsItem(
            title=f"Notícia {i}",
            url=f"https://example.com/{i}",
            source="Exemplo",
            published=datetime(2026, 10, 15, tzinfo=timezone.utc),
        )
        for i in range(1, n + 1)
    ]
