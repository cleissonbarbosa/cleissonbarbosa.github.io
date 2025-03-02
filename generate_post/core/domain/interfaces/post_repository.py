from abc import ABC, abstractmethod
from typing import Optional

from ..entities.post import Post


class PostRepositoryInterface(ABC):
    """Interface para repositório de posts"""

    @abstractmethod
    def save_post(self, post: Post) -> bool:
        """Salva um post no repositório"""
        pass

    @abstractmethod
    def get_last_post(self) -> Optional[Post]:
        """Recupera o último post do repositório"""
        pass
