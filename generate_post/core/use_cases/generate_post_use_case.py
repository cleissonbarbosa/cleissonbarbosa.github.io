from datetime import datetime
from typing import Callable

from generate_post.config.constants import TIMEZONE
from generate_post.core.domain.entities.post import Post
from generate_post.core.domain.interfaces.image_generator_service import (
    ImageGeneratorServiceInterface,
)
from generate_post.core.domain.interfaces.post_repository import (
    PostRepositoryInterface,
)
from generate_post.core.domain.interfaces.text_generator import TextGeneratorInterface
from generate_post.core.use_cases import prompts
from generate_post.core.use_cases.drafts import parse_draft
from generate_post.core.use_cases.publish import publish_draft

# Títulos recentes entram no prompt para o modelo não repetir temas
_RECENT_POSTS = 15
_DEFAULT_LABELS = ["programação"]


class GeneratePostUseCase:
    """Caso de uso para geração de post"""

    def __init__(
        self,
        post_repository: PostRepositoryInterface,
        text_generator: TextGeneratorInterface,
        image_generator: ImageGeneratorServiceInterface,
        clock: Callable[[], datetime] = lambda: datetime.now(TIMEZONE),
    ):
        self._post_repository = post_repository
        self._text_generator = text_generator
        self._image_generator = image_generator
        self._clock = clock

    def build_prompt(self) -> str:
        return prompts.post_prompt(self._post_repository.get_recent_posts(_RECENT_POSTS))

    def execute(self) -> Post:
        """Executa o caso de uso de geração de post"""
        draft = self._text_generator.generate(
            prompts.POST_SYSTEM,
            self.build_prompt(),
            lambda text: parse_draft(text, _DEFAULT_LABELS, _DEFAULT_LABELS),
        )
        return publish_draft(
            draft, draft.content, self._clock(), self._post_repository, self._image_generator
        )
