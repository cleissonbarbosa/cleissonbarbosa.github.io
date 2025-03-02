from dataclasses import dataclass
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

    def to_dict(self):
        """Converte o post para um dicionário"""
        return {
            "title": self.title,
            "categories": self.categories,
            "tags": self.tags,
            "content": self.content,
            "date": self.date,
            "image_path": self.image_path,
            "slug": self.slug,
            "filename": self.filename,
        }
