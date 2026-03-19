from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class Post:
    """Entidade que representa um post do blog"""

    title: str
    categories: str
    tags: str
    content: str
    date: datetime | None = None
    image_path: str | None = None
    slug: str | None = None
    filename: str | None = None

    def __post_init__(self):
        if self.date is None:
            self.date = datetime.now()

    def to_dict(self) -> dict:
        """Converte o post para um dicionário"""
        return asdict(self)
