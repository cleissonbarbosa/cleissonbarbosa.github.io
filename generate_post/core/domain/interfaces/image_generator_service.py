from abc import ABC, abstractmethod
from typing import Optional


class ImageGeneratorServiceInterface(ABC):
    """Interface para serviço de geração de imagens"""

    @abstractmethod
    def generate_image(
        self, title: str, categories: str, tags: str, content_preview: str
    ) -> Optional[str]:
        """Gera uma imagem com base nas informações do post e retorna o caminho relativo"""  # noqa: E501
        pass

    @abstractmethod
    def create_image_prompt(
        self, title: str, categories: str, tags: str, content_preview: str
    ) -> str:
        """Cria um prompt para geração de imagem"""
        pass
