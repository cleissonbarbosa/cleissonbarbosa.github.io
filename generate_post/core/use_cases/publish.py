from datetime import datetime

from generate_post.core.domain.entities.post import Post, PostDraft
from generate_post.core.domain.interfaces.image_generator_service import (
    ImageGeneratorServiceInterface,
)
from generate_post.core.domain.interfaces.post_repository import (
    PostRepositoryInterface,
)
from generate_post.core.use_cases.drafts import slugify

_DEFAULT_IMAGE = "/assets/img/posts/ia-generated.png"


def publish_draft(
    draft: PostDraft,
    content: str,
    date: datetime,
    post_repository: PostRepositoryInterface,
    image_generator: ImageGeneratorServiceInterface,
) -> Post:
    """Gera a capa, monta o post a partir do rascunho e salva."""
    slug = slugify(draft.title)
    image_path = image_generator.generate_image(draft.image_prompt)

    post = Post(
        title=draft.title,
        content=content,
        categories=draft.categories,
        tags=draft.tags,
        description=draft.description,
        date=date,
        image_path=image_path or _DEFAULT_IMAGE,
        slug=slug,
        filename=f"_posts/{date:%Y-%m-%d}-{slug}.md",
    )

    post_repository.save_post(post)
    return post
