#!/usr/bin/env python3
import sys

from generate_post.adapters.repositories.file_post_repository import (
    FilePostRepository,
)  # noqa
from generate_post.adapters.api import (
    GeminiContentService,
    CloudflareImageService,
)
from generate_post.core.use_cases.generate_post_use_case import (
    GeneratePostUseCase,
)  # noqa
from generate_post.adapters.cli.cli_handler import CLIHandler


def main():
    """Função principal da aplicação"""
    try:
        # Inicializa repositórios e serviços
        post_repository = FilePostRepository()
        content_generator = GeminiContentService()
        image_generator = CloudflareImageService()

        # Inicializa caso de uso
        generate_post_use_case = GeneratePostUseCase(
            post_repository=post_repository,
            content_generator=content_generator,
            image_generator=image_generator,
        )

        # Inicializa e executa o handler de CLI
        cli_handler = CLIHandler(generate_post_use_case)
        success = cli_handler.execute()

        # Retorna código de saída apropriado
        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"Erro fatal na execução da aplicação: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
