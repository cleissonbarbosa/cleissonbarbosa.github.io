"""Validação da resposta do modelo e montagem do texto final do post."""

import json
import re
import unicodedata

from generate_post.core.domain.entities.news_item import NewsItem
from generate_post.core.domain.entities.post import PostDraft

# Abaixo disso a resposta foi cortada ou o modelo ignorou o pedido de extensão
_MIN_CONTENT_CHARS = 2500
_MAX_TITLE_CHARS = 150
_MAX_DESCRIPTION_CHARS = 200
_MAX_SLUG_CHARS = 80

_MAX_LABELS = 8
_MAX_LABEL_CHARS = 40
_LABEL_STRIP_RE = re.compile(r"[\[\]{}\"'`*]")
# Marcadores de Markdown ou pontuação de frase indicam texto, não rótulo
_NOT_A_LABEL_RE = re.compile(r"^[#>|-]|[:;!?()]|\.$")
_TITLE_STRIP_RE = re.compile(r'["#*`]|^(?:title|título):\s*', re.IGNORECASE)
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$")


class InvalidDraftError(ValueError):
    """A resposta do modelo não tem o formato ou a qualidade esperados."""


def parse_draft(text: str, default_categories: list[str], default_tags: list[str]) -> PostDraft:
    """Converte a resposta JSON do modelo em um rascunho validado."""
    data = _load_json_object(text)

    title = " ".join(_TITLE_STRIP_RE.sub("", str(data.get("title", ""))).split())
    if not title or len(title) > _MAX_TITLE_CHARS:
        raise InvalidDraftError(f"Título ausente ou longo demais: {title[:200]!r}")

    content = _strip_repeated_title(str(data.get("content", "")).strip(), title)
    if len(content) < _MIN_CONTENT_CHARS:
        raise InvalidDraftError(f"Conteúdo curto demais ({len(content)} caracteres)")

    description = _truncate(" ".join(str(data.get("description", "")).split()), _MAX_DESCRIPTION_CHARS)
    image_prompt = " ".join(str(data.get("image_prompt", "")).split()) or title

    return PostDraft(
        title=title,
        description=description,
        categories=clean_labels(data.get("categories")) or default_categories,
        tags=clean_labels(data.get("tags")) or default_tags,
        content=content,
        image_prompt=image_prompt,
    )


def clean_labels(value) -> list[str]:
    """Normaliza categorias/tags, descartando itens que pareçam frases."""
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, list):
        return []

    labels: list[str] = []
    for item in value:
        label = " ".join(_LABEL_STRIP_RE.sub("", str(item)).split()).lower()
        if (
            label
            and len(label) <= _MAX_LABEL_CHARS
            and not _NOT_A_LABEL_RE.search(label)
            and label not in labels
        ):
            labels.append(label)
    return labels[:_MAX_LABELS]


def slugify(title: str) -> str:
    """Slug ASCII para nome de arquivo e URL ("Ação & Reação" -> "acao-reacao")."""
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
    if len(slug) > _MAX_SLUG_CHARS:
        slug = slug[:_MAX_SLUG_CHARS].rsplit("-", 1)[0]
    return slug or "post"


_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)(?:\{[^}]*\})?")
_CITATION_RE = re.compile(r"\[(\d{1,3})\](?!\()")


def link_citations(content: str, items: list[NewsItem]) -> tuple[str, list[int]]:
    """Troca as citações [n] pelos links reais das notícias e lista as fontes.

    Retorna o texto final e os números das notícias citadas.

    Links escritos pelo próprio modelo são removidos (mantendo o texto), pois
    só as URLs vindas dos feeds são confiáveis.
    """
    text = _MARKDOWN_LINK_RE.sub(_keep_citation_or_text, content)

    cited: list[int] = []

    def replace(match: re.Match) -> str:
        number = int(match.group(1))
        if not 1 <= number <= len(items):
            return ""
        if number not in cited:
            cited.append(number)
        return f'[{number}]({items[number - 1].url}){{:target="_blank"}}'

    text = _CITATION_RE.sub(replace, text)
    if not cited:
        return text, cited

    sources = "\n".join(
        f'- [{n}] [{_escape_brackets(items[n - 1].title)}]({items[n - 1].url}){{:target="_blank"}} — {items[n - 1].source}'
        for n in sorted(cited)
    )
    return f"{text.rstrip()}\n\n## Fontes\n\n{sources}\n", cited


def _keep_citation_or_text(match: re.Match) -> str:
    """[3](url-do-modelo) vira [3] (religado depois); [texto](url) vira texto."""
    label = match.group(1)
    return f"[{label}]" if label.isdigit() else label


def _load_json_object(text: str) -> dict:
    cleaned = _CODE_FENCE_RE.sub("", text.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise InvalidDraftError(f"Resposta sem objeto JSON: {text[:200]!r}")
    try:
        # strict=False aceita quebras de linha cruas dentro das strings,
        # comuns quando o modelo escreve Markdown longo em JSON
        data = json.loads(cleaned[start : end + 1], strict=False)
    except json.JSONDecodeError as e:
        raise InvalidDraftError(f"JSON inválido: {e}") from e
    if not isinstance(data, dict):
        raise InvalidDraftError("A resposta JSON não é um objeto")
    return data


def _strip_repeated_title(content: str, title: str) -> str:
    """Remove um '# Título' inicial: o tema já exibe o título do post."""
    first_line, _, rest = content.partition("\n")
    if first_line.startswith("# ") and _TITLE_STRIP_RE.sub("", first_line).strip().lower() == title.lower():
        return rest.lstrip()
    return content


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def _escape_brackets(text: str) -> str:
    return text.replace("[", "(").replace("]", ")")
