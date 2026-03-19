#!/usr/bin/env python3
import logging
import sys

from generate_post.adapters.api import (
    GeminiContentService,
    CloudflareImageService,
)
from generate_post.adapters.cli.cli_handler import CLIHandler
from generate_post.adapters.repositories.file_post_repository import (
    FilePostRepository,
)
from generate_post.config.env_config import EnvConfig
from generate_post.core.use_cases.generate_post_use_case import (
    GeneratePostUseCase,
)

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    """Função principal — composition root da aplicação."""
    _setup_logging()

    try:
        env = EnvConfig.from_env()

        post_repository = FilePostRepository()
        content_generator = GeminiContentService(env_config=env)
        image_generator = CloudflareImageService(env_config=env)

        use_case = GeneratePostUseCase(
            post_repository=post_repository,
            content_generator=content_generator,
            image_generator=image_generator,
        )

        cli_handler = CLIHandler(use_case, env_config=env)
        success = cli_handler.execute()

        sys.exit(0 if success else 1)

    except Exception:
        logger.exception("Erro fatal na execução da aplicação")
        sys.exit(1)


if __name__ == "__main__":
    main()
