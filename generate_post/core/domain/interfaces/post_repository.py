from abc import ABC, abstractmethod

from ..entities.post import Post


class PostRepositoryInterface(ABC):
    """Interface para repositório de posts"""

    @abstractmethod
    def save_post(self, post: Post) -> bool:
        """Salva um post no repositório"""

    @abstractmethod
    def get_recent_posts(self, limit: int) -> list[Post]:
        """Recupera os posts mais recentes, do mais novo para o mais antigo"""
