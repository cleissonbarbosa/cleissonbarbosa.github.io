from dataclasses import dataclass, asdict, field
from datetime import datetime


@dataclass(frozen=True)
class PostDraft:
    """Conteúdo devolvido pelo modelo de texto, já validado."""

    title: str
    description: str
    categories: list[str]
    tags: list[str]
    content: str
    image_prompt: str


@dataclass
class Post:
    """Entidade que representa um post do blog"""

    title: str
    content: str
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    description: str = ""
    date: datetime | None = None
    image_path: str | None = None
    slug: str | None = None
    filename: str | None = None

    def to_dict(self) -> dict:
        """Converte o post para um dicionário"""
        return asdict(self)
