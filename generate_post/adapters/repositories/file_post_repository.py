import os
from pathlib import Path
from typing import Optional
import re
from datetime import datetime

from generate_post.core.domain.entities.post import Post
from generate_post.core.domain.interfaces.post_repository import (
    PostRepositoryInterface,
)  # noqa
from generate_post.config.constants import POSTS_DIR


class FilePostRepository(PostRepositoryInterface):
    """Implementação do repositório de posts usando sistema de arquivos"""

    def save_post(self, post: Post) -> bool:
        """Salva um post como arquivo markdown"""
        try:
            # Front matter para o post
            front_matter = f"""---
title: "{post.title}"
author: ia
date: {post.date.strftime("%Y-%m-%d") if post.date else datetime.now().strftime("%Y-%m-%d")} 00:00:00 -0300
image:
  path: {post.image_path}
  alt: "{post.title}"
categories: [{post.categories}]
tags: [{post.tags}, ai-generated]
---

"""  # noqa

            generated_by = """

_Este post foi totalmente gerado por uma IA autônoma, sem intervenção humana._

[Veja o código que gerou este post](https://github.com/cleissonbarbosa/cleissonbarbosa.github.io/blob/main/generate_post/README.md){:target="_blank"}
"""  # noqa

            # Garantir que o diretório existe
            os.makedirs(os.path.dirname(post.filename), exist_ok=True)  # type: ignore  # noqa

            # Escrever o arquivo Markdown
            full_path = Path(post.filename if post.filename else "")
            if not full_path:
                raise ValueError("Filename is required")
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(front_matter + post.content + "\n\n---" + generated_by)

            print(f"Post gerado: {post.filename}")
            print(f"Imagem do post: {post.image_path}")

            return True
        except Exception as e:
            print(f"Erro ao salvar post: {e}")
            return False

    def get_last_post(self) -> Optional[Post]:
        """Recupera o último post do repositório"""
        try:
            post_files = list(POSTS_DIR.glob("*.md"))

            if not post_files:
                return None

            # Ordena por data de modificação (mais recente primeiro)
            last_post_file = sorted(
                post_files, key=lambda p: p.stat().st_mtime, reverse=True
            )[0]

            with open(last_post_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Extrair informações do Front Matter
            title_match = re.search(r'title: "([^"]+)"', content)
            title = title_match.group(1) if title_match else ""

            categories_match = re.search(r"categories: \[(.*)\]", content)
            categories = categories_match.group(1) if categories_match else ""

            tags_match = re.search(r"tags: \[(.*)\]", content)
            tags = tags_match.group(1) if tags_match else ""

            # Extrair data do nome do arquivo
            date_match = re.match(r"(\d{4}-\d{2}-\d{2})", last_post_file.name)
            date_str = date_match.group(1) if date_match else None
            date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else None  # noqa

            # Extrair conteúdo (tudo após o front matter)
            content_match = re.search(
                r"---\s*\n(.*?)(\n---\s*\n_Este post)", content, re.DOTALL
            )
            post_content = content_match.group(1) if content_match else ""

            # Criar objeto Post
            post = Post(
                title=title,
                categories=categories,
                tags=tags,
                content=post_content,
                date=date,
                filename=str(last_post_file),
            )

            return post

        except Exception as e:
            print(f"Erro ao recuperar último post: {e}")
            return None
