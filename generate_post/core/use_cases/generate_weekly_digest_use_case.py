import logging
import re
from datetime import datetime

from generate_post.core.domain.entities.post import Post
from generate_post.core.domain.interfaces.content_generator_service import (
    ContentGeneratorServiceInterface,
)
from generate_post.core.domain.interfaces.image_generator_service import (
    ImageGeneratorServiceInterface,
)
from generate_post.core.domain.interfaces.post_repository import (
    PostRepositoryInterface,
)

logger = logging.getLogger(__name__)

_DEFAULT_IMAGE = "/assets/img/posts/ia-generated.png"
_SLUG_RE = re.compile(r"\W+")


class GenerateWeeklyDigestUseCase:
    """Caso de uso para geração de resumo semanal de notícias."""

    def __init__(
        self,
        post_repository: PostRepositoryInterface,
        content_generator: ContentGeneratorServiceInterface,
        image_generator: ImageGeneratorServiceInterface,
    ):
        self._post_repository = post_repository
        self._content_generator = content_generator
        self._image_generator = image_generator

    def execute(self) -> Post:
        # Gera conteúdo usando Google Search grounding
        prompt = self._content_generator.create_prompt()
        generated_text = self._content_generator.generate_content(prompt)
        post_data = self._content_generator.parse_generated_content(generated_text)

        title = post_data["title"]
        categories = post_data["categories"]
        tags = post_data["tags"]
        content = post_data["content"]

        slug = _SLUG_RE.sub("-", title.lower()).strip("-")
        date = datetime.now()

        # Gera imagem
        image_path = self._image_generator.generate_image(
            title, categories, tags, content
        )

        post = Post(
            title=title,
            categories=categories,
            tags=tags,
            content=content,
            date=date,
            image_path=image_path or _DEFAULT_IMAGE,
            slug=slug,
            filename=f"_posts/{date:%Y-%m-%d}-{slug}.md",
        )

        self._post_repository.save_post(post)
        return post
