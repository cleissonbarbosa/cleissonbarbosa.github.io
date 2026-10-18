import logging
from typing import Protocol

from generate_post.core.domain.entities.post import Post
from generate_post.config.env_config import EnvConfig

logger = logging.getLogger(__name__)


class _UseCaseProtocol(Protocol):
    def execute(self) -> Post: ...


class CLIHandler:
    """Manipulador de linha de comando para geração de post"""

    def __init__(
        self,
        generate_post_use_case: _UseCaseProtocol,
        env_config: EnvConfig,
    ):
        self._use_case = generate_post_use_case
        self._env = env_config

    def execute(self) -> bool:
        """Executa o caso de uso de geração de post a partir da CLI"""
        try:
            post = self._use_case.execute()
            self._write_github_output(post)
            return True
        except Exception:
            logger.exception("Erro durante a geração do post")
            return False

    def _write_github_output(self, post: Post) -> None:
        """Escreve as informações do post para o output do GitHub Actions"""
        github_output = self._env.github_output
        if not github_output:
            return

        outputs = {
            "post_title": post.title,
            "post_slug": post.slug,
            "post_categories": ",".join(post.categories),
            "post_tags": ",".join(post.tags),
            "post_filename": post.filename,
            "post_image": post.image_path.removeprefix("/") if post.image_path else "",
        }
        with open(github_output, "a", encoding="utf-8") as f:
            for key, value in outputs.items():
                # Uma quebra de linha no valor criaria outra saída no GITHUB_OUTPUT
                f.write(f"{key}={' '.join(str(value or '').split())}\n")
