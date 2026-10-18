#!/usr/bin/env python3
import argparse
import logging
import sys
from datetime import datetime

from generate_post.adapters.api import (
    CloudflareImageService,
    CloudflareTextGenerator,
    FallbackTextGenerator,
    GeminiTextGenerator,
)
from generate_post.adapters.cli.cli_handler import CLIHandler
from generate_post.adapters.news import FeedNewsSource
from generate_post.adapters.repositories.file_post_repository import (
    FilePostRepository,
)
from generate_post.config.constants import TIMEZONE
from generate_post.config.env_config import EnvConfig
from generate_post.core.use_cases.generate_post_use_case import (
    GeneratePostUseCase,
)
from generate_post.core.use_cases.generate_weekly_digest_use_case import (
    GenerateWeeklyDigestUseCase,
)

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gerador de posts para o blog")
    parser.add_argument(
        "--weekly-digest",
        action="store_true",
        help="Gera um resumo semanal de notícias a partir de feeds e do Hacker News",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Só monta e imprime o prompt (coletando as notícias, no resumo); "
        "não chama modelos de IA nem grava arquivos",
    )
    return parser.parse_args()


def main():
    """Função principal — composition root da aplicação."""
    _setup_logging()

    try:
        args = _parse_args()
        env = EnvConfig.from_env()

        post_repository = FilePostRepository()
        image_generator = CloudflareImageService(env_config=env)
        # Gemini (free tier) primeiro; Workers AI usa as mesmas credenciais
        # das imagens e só entra se todos os modelos Gemini falharem
        text_generator = FallbackTextGenerator(
            [GeminiTextGenerator(env_config=env), CloudflareTextGenerator(env_config=env)]
        )

        if args.weekly_digest:
            use_case = GenerateWeeklyDigestUseCase(
                post_repository=post_repository,
                text_generator=text_generator,
                image_generator=image_generator,
                news_source=FeedNewsSource(),
            )
        else:
            use_case = GeneratePostUseCase(
                post_repository=post_repository,
                text_generator=text_generator,
                image_generator=image_generator,
            )

        if args.dry_run:
            if args.weekly_digest:
                prompt, _ = use_case.build_prompt(datetime.now(TIMEZONE))
            else:
                prompt = use_case.build_prompt()
            print(prompt)
            sys.exit(0)

        cli_handler = CLIHandler(use_case, env_config=env)
        success = cli_handler.execute()

        sys.exit(0 if success else 1)

    except Exception:
        logger.exception("Erro fatal na execução da aplicação")
        sys.exit(1)


if __name__ == "__main__":
    main()
