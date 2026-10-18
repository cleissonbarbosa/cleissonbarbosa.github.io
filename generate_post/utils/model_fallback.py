import logging
from typing import Callable, Sequence, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def first_successful(models: Sequence[str], attempt: Callable[[str], T]) -> T:
    """Tenta cada modelo na ordem e devolve o primeiro resultado bem-sucedido.

    Provedores aposentam modelos sem aviso no código; com uma lista ordenada,
    um modelo removido (404) ou instável só custa uma chamada a mais.
    """
    failures = []
    for model in models:
        logger.info("Modelo selecionado: %s", model)
        try:
            return attempt(model)
        except Exception as e:
            logger.warning("Modelo %s falhou, tentando o próximo: %s", model, e)
            failures.append(f"{model}: {e}")

    raise RuntimeError("Nenhum modelo conseguiu gerar o conteúdo:\n" + "\n".join(failures))
