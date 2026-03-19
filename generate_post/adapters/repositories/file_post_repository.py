import logging
from pathlib import Path
from typing import Optional
import re
from datetime import datetime

from generate_post.core.domain.entities.post import Post
from generate_post.core.domain.interfaces.post_repository import (
    PostRepositoryInterface,
)
from generate_post.config.constants import POSTS_DIR

logger = logging.getLogger(__name__)

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.+?)\n---\s*\n", re.DOTALL)
_TITLE_RE = re.compile(r'title:\s*"([^"]+)"')
_CATEGORIES_RE = re.compile(r"categories:\s*\[(.*)?\]")
_TAGS_RE = re.compile(r"tags:\s*\[(.*)?\]")
_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


class FilePostRepository(PostRepositoryInterface):
    """Implementação do repositório de posts usando sistema de arquivos"""

    def save_post(self, post: Post) -> bool:
        """Salva um post como arquivo markdown"""
        if not post.filename:
            raise ValueError("Post.filename é obrigatório para salvar")

        full_path = Path(post.filename)
        full_path.parent.mkdir(parents=True, exist_ok=True)

        date_str = (
            post.date.strftime("%Y-%m-%d")
            if post.date
            else datetime.now().strftime("%Y-%m-%d")
        )

        front_matter = (
            f"---\n"
            f'title: "{post.title}"\n'
            f"author: ia\n"
            f"date: {date_str} 00:00:00 -0300\n"
            f"image:\n"
            f"  path: {post.image_path}\n"
            f'  alt: "{post.title}"\n'
            f"categories: [{post.categories}]\n"
            f"tags: [{post.tags}, ai-generated]\n"
            f"---\n\n"
        )

        generated_by = (
            "\n\n---\n\n"
            "_Este post foi totalmente gerado por uma IA autônoma, "
            "sem intervenção humana._\n\n"
            "[Veja o código que gerou este post]"
            "(https://github.com/cleissonbarbosa/"
            "cleissonbarbosa.github.io/blob/main/"
            'generate_post/README.md){:target="_blank"}\n'
        )

        full_path.write_text(
            front_matter + post.content + generated_by,
            encoding="utf-8",
        )

        logger.info("Post gerado: %s", post.filename)
        logger.info("Imagem do post: %s", post.image_path)
        return True

    def get_last_post(self) -> Optional[Post]:
        """Recupera o último post do repositório"""
        post_files = list(POSTS_DIR.glob("*.md"))
        if not post_files:
            return None

        # Ordena pelo nome do arquivo (data YYYY-MM-DD no prefixo)
        # em vez de st_mtime que pode mudar com git checkout
        last_post_file = max(post_files, key=lambda p: p.name)

        content = last_post_file.read_text(encoding="utf-8")

        # Extrair front matter
        fm_match = _FRONT_MATTER_RE.search(content)
        front_matter = fm_match.group(1) if fm_match else ""

        title_match = _TITLE_RE.search(front_matter)
        title = title_match.group(1) if title_match else ""

        categories_match = _CATEGORIES_RE.search(front_matter)
        categories = categories_match.group(1) if categories_match else ""

        tags_match = _TAGS_RE.search(front_matter)
        tags = tags_match.group(1) if tags_match else ""

        # Extrair data do nome do arquivo
        date_match = _DATE_RE.match(last_post_file.name)
        date = (
            datetime.strptime(date_match.group(1), "%Y-%m-%d") if date_match else None
        )

        # Conteúdo: tudo após o front matter
        post_content = content[fm_match.end() :].strip() if fm_match else ""

        return Post(
            title=title,
            categories=categories,
            tags=tags,
            content=post_content,
            date=date,
            filename=str(last_post_file),
        )
