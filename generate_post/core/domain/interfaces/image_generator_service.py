from abc import ABC, abstractmethod
from typing import Optional


class ImageGeneratorServiceInterface(ABC):
    """Interface para serviço de geração de imagens"""

    @abstractmethod
    def generate_image(self, description: str) -> Optional[str]:
        """Gera a imagem de capa e retorna o caminho relativo (None se falhar)"""
