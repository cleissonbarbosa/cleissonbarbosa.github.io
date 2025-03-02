from abc import ABC, abstractmethod
from typing import Optional, Dict


class ContentGeneratorServiceInterface(ABC):
    """Interface para serviço de geração de conteúdo"""

    @abstractmethod
    def generate_content(self, prompt: str) -> str:
        """Gera conteúdo a partir de um prompt"""
        pass

    @abstractmethod
    def create_prompt(self, last_post: Optional[Dict] = None) -> str:
        """Cria um prompt para geração de conteúdo"""
        pass

    @abstractmethod
    def parse_generated_content(self, content: str) -> Dict:
        """Extrai informações de um conteúdo gerado"""
        pass
