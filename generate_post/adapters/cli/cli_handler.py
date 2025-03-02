import traceback

from generate_post.core.domain.entities.post import Post
from generate_post.core.use_cases.generate_post_use_case import (
    GeneratePostUseCase,
)  # noqa
from generate_post.config.env_config import EnvConfig


class CLIHandler:
    """Manipulador de linha de comando para geração de post"""

    def __init__(self, generate_post_use_case: GeneratePostUseCase):
        self.generate_post_use_case = generate_post_use_case

    def execute(self) -> bool:
        """Executa o caso de uso de geração de post a partir da CLI"""
        try:
            # Executa o caso de uso
            post = self.generate_post_use_case.execute()

            # Output para GitHub Actions se necessário
            self._write_github_output(post)

            return True

        except Exception as e:
            print(f"Erro durante a geração do post: {e}")
            traceback.print_exc()
            return False

    def _write_github_output(self, post: Post) -> None:
        """Escreve as informações do post para o output do GitHub Actions"""
        github_output = EnvConfig.get_github_output()
        if github_output:
            with open(github_output, "a") as f:
                f.write(
                    f"""post_title={post.title}
post_slug={post.slug}
post_categories={post.categories}
post_tags={post.tags}
post_filename={post.filename}
post_image={post.image_path.removeprefix('/') if post.image_path else ''}
"""
                )
