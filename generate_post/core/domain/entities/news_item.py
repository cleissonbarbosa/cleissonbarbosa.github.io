from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class NewsItem:
    """Notícia coletada de um feed, usada como fonte do resumo semanal."""

    title: str
    url: str
    source: str
    published: datetime
    summary: str = ""
    # Sinal de relevância quando a fonte oferece (pontos no Hacker News)
    score: int = 0
