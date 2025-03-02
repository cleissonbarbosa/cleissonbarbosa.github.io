import re
from datetime import datetime

from generate_post.core.domain.entities.post import Post
from generate_post.core.domain.interfaces.post_repository import (
    PostRepositoryInterface,
)  # noqa
from generate_post.core.domain.interfaces.content_generator_service import (
    ContentGeneratorServiceInterface,
)
from generate_post.core.domain.interfaces.image_generator_service import (
    ImageGeneratorServiceInterface,
)


class GeneratePostUseCase:
    """Caso de uso para geração de post"""

    def __init__(
        self,
        post_repository: PostRepositoryInterface,
        content_generator: ContentGeneratorServiceInterface,
        image_generator: ImageGeneratorServiceInterface,
    ):
        self.post_repository = post_repository
        self.content_generator = content_generator
        self.image_generator = image_generator

    def execute(self) -> Post:
        """Executa o caso de uso de geração de post"""
        # Recupera o último post para contexto
        last_post_dict = None
        last_post = self.post_repository.get_last_post()
        if last_post:
            last_post_dict = last_post.to_dict()

        # Cria prompt e gera conteúdo
        prompt = self.content_generator.create_prompt(last_post_dict)
        generated_text = self.content_generator.generate_content(prompt)

        # Extrai informações do texto gerado
        post_data = self.content_generator.parse_generated_content(
            generated_text
        )  # noqa
        title = post_data["title"]
        categories = post_data["categories"]
        tags = post_data["tags"]
        content = post_data["content"]

        # Criar um slug simples para o título
        slug = re.sub(r"\W+", "-", title.lower()).strip("-")

        # Obter a data atual no formato YYYY-MM-DD
        date = datetime.now()
        date_str = date.strftime("%Y-%m-%d")

        # Gerar imagem para o post
        image_path = self.image_generator.generate_image(
            title, categories, tags, content
        )

        # Criar objeto Post
        post = Post(
            title=title,
            categories=categories,
            tags=tags,
            content=content,
            date=date,
            image_path=image_path or "/assets/img/posts/ia-generated.png",
            slug=slug,
            filename=f"_posts/{date_str}-{slug}.md",
        )

        # Salvar o post
        self.post_repository.save_post(post)

        return post
