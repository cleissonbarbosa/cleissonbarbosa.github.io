from abc import ABC, abstractmethod
from typing import Callable, TypeVar

T = TypeVar("T")


class TextGeneratorInterface(ABC):
    """Interface para serviço de geração de texto"""

    @abstractmethod
    def generate(self, system: str, prompt: str, parse: Callable[[str], T]) -> T:
        """Gera texto e devolve o resultado de ``parse``.

        Se ``parse`` levantar exceção (resposta fora do formato), a
        implementação deve tentar outro modelo antes de desistir.
        """
