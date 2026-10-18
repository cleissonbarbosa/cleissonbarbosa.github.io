import logging
from typing import Callable, Protocol, Sequence, TypeVar

from generate_post.core.domain.interfaces.text_generator import TextGeneratorInterface
from generate_post.utils.model_fallback import first_successful

logger = logging.getLogger(__name__)

T = TypeVar("T")


class _Provider(Protocol):
    name: str

    def is_configured(self) -> bool: ...

    def generate(self, system: str, prompt: str, parse: Callable[[str], T]) -> T: ...


class FallbackTextGenerator(TextGeneratorInterface):
    """Tenta os provedores configurados em ordem (cada um com seus modelos)."""

    def __init__(self, providers: Sequence[_Provider]):
        self._providers = providers

    def generate(self, system: str, prompt: str, parse: Callable[[str], T]) -> T:
        configured = {p.name: p for p in self._providers if p.is_configured()}
        skipped = [p.name for p in self._providers if p.name not in configured]
        if skipped:
            logger.info("Provedores sem credenciais, ignorados: %s", ", ".join(skipped))

        return first_successful(
            list(configured),
            lambda name: configured[name].generate(system, prompt, parse),
            kind="Provedor",
        )
