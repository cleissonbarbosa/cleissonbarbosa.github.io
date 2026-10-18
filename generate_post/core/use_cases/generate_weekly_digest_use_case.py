import logging
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Callable

from generate_post.config.constants import TIMEZONE
from generate_post.core.domain.entities.news_item import NewsItem
from generate_post.core.domain.entities.post import Post
from generate_post.core.domain.interfaces.image_generator_service import (
    ImageGeneratorServiceInterface,
)
from generate_post.core.domain.interfaces.news_source import NewsSourceInterface
from generate_post.core.domain.interfaces.post_repository import (
    PostRepositoryInterface,
)
from generate_post.core.domain.interfaces.text_generator import TextGeneratorInterface
from generate_post.core.use_cases import prompts
from generate_post.core.use_cases.drafts import (
    InvalidDraftError,
    link_citations,
    parse_draft,
)
from generate_post.core.use_cases.publish import publish_draft

logger = logging.getLogger(__name__)

_WINDOW = timedelta(days=7)
# Com menos que isso os feeds falharam e o resumo sairia raso
_MIN_NEWS = 10
# Um resumo que cita poucas notícias provavelmente ignorou a lista
_MIN_CITED = 5

_CATEGORIES = ["noticias", "tecnologia", "resumo-semanal"]
_DEFAULT_TAGS = ["resumo-semanal", "noticias", "tecnologia", "ia", "desenvolvimento"]


class GenerateWeeklyDigestUseCase:
    """Caso de uso para geração de resumo semanal de notícias."""

    def __init__(
        self,
        post_repository: PostRepositoryInterface,
        text_generator: TextGeneratorInterface,
        image_generator: ImageGeneratorServiceInterface,
        news_source: NewsSourceInterface,
        clock: Callable[[], datetime] = lambda: datetime.now(TIMEZONE),
    ):
        self._post_repository = post_repository
        self._text_generator = text_generator
        self._image_generator = image_generator
        self._news_source = news_source
        self._clock = clock

    def build_prompt(self, end: datetime) -> tuple[str, list[NewsItem]]:
        start = end - _WINDOW
        items = self._news_source.fetch_since(start)
        if len(items) < _MIN_NEWS:
            raise RuntimeError(
                f"Só {len(items)} notícias coletadas (mínimo {_MIN_NEWS}); "
                "verifique os feeds antes de gerar o resumo"
            )
        return prompts.digest_prompt(items, start, end), items

    def execute(self) -> Post:
        now = self._clock()
        prompt, items = self.build_prompt(now)

        def parse(text: str):
            draft = parse_draft(text, _CATEGORIES, _DEFAULT_TAGS)
            content, cited = link_citations(draft.content, items)
            if len(cited) < _MIN_CITED:
                raise InvalidDraftError(
                    f"O resumo citou só {len(cited)} notícias (mínimo {_MIN_CITED})"
                )
            logger.info("Notícias citadas: %d de %d", len(cited), len(items))
            tags = draft.tags if "resumo-semanal" in draft.tags else ["resumo-semanal", *draft.tags][:8]
            return replace(draft, categories=_CATEGORIES, tags=tags), content

        draft, content = self._text_generator.generate(prompts.DIGEST_SYSTEM, prompt, parse)
        return publish_draft(draft, content, now, self._post_repository, self._image_generator)
