import json
import logging
import re
from datetime import datetime
from pathlib import Path

from generate_post.config.constants import POSTS_DIR
from generate_post.core.domain.entities.post import Post
from generate_post.core.domain.interfaces.post_repository import (
    PostRepositoryInterface,
)

logger = logging.getLogger(__name__)

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.+?)\n---\s*\n", re.DOTALL)
_TITLE_RE = re.compile(r'^title:\s*"(.+)"\s*$', re.MULTILINE)
_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")

_FOOTER_START = "\n\n---\n\n_Este post foi totalmente gerado por uma IA"
_GENERATED_BY = (
    "\n\n---\n\n"
    "_Este post foi totalmente gerado por uma IA autônoma, "
    "sem intervenção humana._\n\n"
    "[Veja o código que gerou este post]"
    "(https://github.com/cleissonbarbosa/"
    "cleissonbarbosa.github.io/blob/main/"
    'generate_post/README.md){:target="_blank"}\n'
)


def _yaml_str(value: str) -> str:
    """Serializa uma string como escalar YAML entre aspas duplas.

    Strings JSON são escalares YAML válidos: nenhum texto vindo do modelo
    consegue virar Hash ou quebrar o front matter.
    """
    return json.dumps(value, ensure_ascii=False)


def _yaml_list(values: list[str]) -> str:
    return "[" + ", ".join(_yaml_str(v) for v in values) + "]"


class FilePostRepository(PostRepositoryInterface):
    """Implementação do repositório de posts usando sistema de arquivos"""

    def __init__(self, posts_dir: Path = POSTS_DIR):
        self._posts_dir = posts_dir

    def save_post(self, post: Post) -> bool:
        """Salva um post como arquivo markdown"""
        if not post.filename:
            raise ValueError("Post.filename é obrigatório para salvar")

        full_path = Path(post.filename)
        full_path.parent.mkdir(parents=True, exist_ok=True)

        date = post.date or datetime.now().astimezone()
        title = _yaml_str(post.title)
        lines = [
            "---",
            f"title: {title}",
            "author: ia",
            f"date: {date:%Y-%m-%d %H:%M:%S %z}",
        ]
        if post.description:
            lines.append(f"description: {_yaml_str(post.description)}")
        lines += [
            "image:",
            f"  path: {post.image_path}",
            f"  alt: {title}",
            f"categories: {_yaml_list(post.categories)}",
            f"tags: {_yaml_list(post.tags + ['ai-generated'])}",
            "---",
            "",
            "",
        ]

        full_path.write_text(
            "\n".join(lines) + post.content.strip() + _GENERATED_BY,
            encoding="utf-8",
        )

        logger.info("Post gerado: %s", post.filename)
        logger.info("Imagem do post: %s", post.image_path)
        return True

    def get_recent_posts(self, limit: int) -> list[Post]:
        """Recupera os posts mais recentes, do mais novo para o mais antigo"""
        # Ordena pelo nome do arquivo (data YYYY-MM-DD no prefixo)
        # em vez de st_mtime que pode mudar com git checkout
        files = sorted(self._posts_dir.glob("*.md"), key=lambda p: p.name, reverse=True)
        return [self._read_post(f) for f in files[:limit]]

    @staticmethod
    def _read_post(path: Path) -> Post:
        text = path.read_text(encoding="utf-8")

        fm_match = _FRONT_MATTER_RE.search(text)
        front_matter = fm_match.group(1) if fm_match else ""
        title_match = _TITLE_RE.search(front_matter)
        title = title_match.group(1) if title_match else path.stem[11:]
        # Títulos novos são strings JSON (com \" escapado); os antigos, texto cru
        try:
            title = json.loads(f'"{title}"')
        except json.JSONDecodeError:
            pass

        date_match = _DATE_RE.match(path.name)
        date = datetime.strptime(date_match.group(1), "%Y-%m-%d") if date_match else None

        content = text[fm_match.end() :] if fm_match else text
        content = content.split(_FOOTER_START)[0].strip()

        return Post(
            title=title,
            content=content,
            date=date,
            filename=f"_posts/{path.name}",
        )
