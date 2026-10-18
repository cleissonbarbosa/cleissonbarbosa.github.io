import re
from typing import Dict

# Regex compilado para limpeza do título
_TITLE_CLEAN_RE = re.compile(r'["#*]|(?:title:|Title:)')
_LABEL_PREFIX_RE = re.compile(r"^\s*(?:categorias|categories|tags)\s*:", re.IGNORECASE)
_LABEL_STRIP_RE = re.compile(r"[\[\]{}\"'`*]")
# Marcadores de Markdown no início ou pontuação de frase indicam corpo, não rótulo
_NOT_A_LABEL_RE = re.compile(r"^[#>|-]|[:;!?()]|\.$")

# Limites para reconhecer uma linha de rótulos. Se o modelo pular a linha de
# categorias/tags, a próxima linha é um parágrafo do corpo — e não pode virar
# tag (um "isso: código" no meio vira Hash no YAML e quebra o build do Jekyll).
_MAX_LABELS = 12
_MAX_LABEL_LEN = 40


def parse_generated_content(
    generated_text: str, default_categories: str, default_tags: str
) -> Dict:
    """Extrai título, categorias, tags e conteúdo do texto gerado.

    Formato esperado: título, categorias, tags e corpo, nessa ordem. Linhas
    de categorias/tags que não pareçam listas de rótulos são tratadas como
    início do corpo e substituídas pelos valores padrão.
    """
    lines = generated_text.strip().split("\n")

    title = _TITLE_CLEAN_RE.sub("", lines[0]).strip()
    idx = _next_non_empty(lines, 1)

    categories = _parse_labels(lines[idx]) if idx < len(lines) else None
    if categories is not None:
        idx = _next_non_empty(lines, idx + 1)

    tags = _parse_labels(lines[idx]) if idx < len(lines) else None
    if tags is not None:
        idx = _next_non_empty(lines, idx + 1)

    content = "\n".join(lines[idx:]).strip() if idx < len(lines) else ""

    return {
        "title": title,
        "categories": categories or default_categories,
        "tags": tags or default_tags,
        "content": content,
    }


def split_labels(labels: str) -> list[str]:
    """Converte 'a, b,c' em ['a', 'b', 'c'], descartando itens vazios."""
    return [label.strip() for label in labels.split(",") if label.strip()]


def _parse_labels(line: str) -> str | None:
    """Normaliza uma linha 'a, b, c'; None se ela não parecer uma lista de rótulos."""
    raw = _LABEL_STRIP_RE.sub("", _LABEL_PREFIX_RE.sub("", line))
    labels = split_labels(" ".join(raw.split()).lower())
    if (
        not labels
        or len(labels) > _MAX_LABELS
        or any(
            len(label) > _MAX_LABEL_LEN or _NOT_A_LABEL_RE.search(label)
            for label in labels
        )
    ):
        return None
    return ",".join(labels)


def _next_non_empty(lines: list[str], start: int) -> int:
    """Retorna o índice da próxima linha não-vazia a partir de start."""
    idx = start
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    return idx
