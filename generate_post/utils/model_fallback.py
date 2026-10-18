import logging
from typing import Callable, Sequence, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ModelUnavailableError(RuntimeError):
    """O modelo não consegue atender a requisição; repetir não adianta."""


def first_successful(
    models: Sequence[str], attempt: Callable[[str], T], kind: str = "Modelo"
) -> T:
    """Tenta cada modelo na ordem e devolve o primeiro resultado bem-sucedido.

    Provedores aposentam modelos sem aviso no código; com uma lista ordenada,
    um modelo removido (404) ou instável só custa uma chamada a mais.
    """
    if not models:
        raise RuntimeError(f"Nenhum {kind.lower()} configurado")

    failures = []
    for model in models:
        logger.info("%s selecionado: %s", kind, model)
        try:
            return attempt(model)
        except Exception as e:
            logger.warning("%s %s falhou, tentando o próximo: %s", kind, model, e)
            failures.append(f"{model}: {e}")

    raise RuntimeError(
        f"Nenhum {kind.lower()} conseguiu gerar o conteúdo:\n" + "\n".join(failures)
    )
