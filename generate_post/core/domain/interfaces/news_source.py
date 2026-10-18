from abc import ABC, abstractmethod
from datetime import datetime

from ..entities.news_item import NewsItem


class NewsSourceInterface(ABC):
    """Interface para fonte de notícias do resumo semanal"""

    @abstractmethod
    def fetch_since(self, since: datetime) -> list[NewsItem]:
        """Retorna as notícias publicadas a partir de ``since``"""
