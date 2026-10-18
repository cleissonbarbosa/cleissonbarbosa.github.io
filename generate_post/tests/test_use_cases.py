import unittest
from datetime import datetime
from unittest import mock

from generate_post.config.constants import TIMEZONE
from generate_post.core.domain.entities.post import Post
from generate_post.core.use_cases.drafts import InvalidDraftError
from generate_post.core.use_cases.generate_post_use_case import GeneratePostUseCase
from generate_post.core.use_cases.generate_weekly_digest_use_case import (
    GenerateWeeklyDigestUseCase,
)
from generate_post.tests.helpers import BODY, draft_json, news

NOW = datetime(2026, 10, 18, 19, 0, tzinfo=TIMEZONE)


class FakeTextGenerator:
    """Devolve respostas prontas, chamando o parse como o gerador real faz."""

    def __init__(self, *responses: str):
        self.responses = list(responses)
        self.prompts = []

    def generate(self, system, prompt, parse):
        self.prompts.append(prompt)
        return parse(self.responses.pop(0))


def _repository(recent=()):
    repository = mock.Mock()
    repository.get_recent_posts.return_value = list(recent)
    return repository


class GeneratePostUseCaseTest(unittest.TestCase):
    def test_builds_post_with_ascii_slug_and_default_image(self):
        recent = [
            Post(title="Do Hype à Realidade com Rust", content="trecho", filename="_posts/2026-10-17-do-hype.md"),
            Post(title="N+1 em microsserviços", content="", filename="_posts/2026-10-15-n-1.md"),
        ]
        repository = _repository(recent)
        images = mock.Mock()
        images.generate_image.return_value = None  # todos os modelos de imagem falharam
        text = FakeTextGenerator(draft_json(title="Ação e Reação no Kotlin"))

        post = GeneratePostUseCase(repository, text, images, clock=lambda: NOW).execute()

        self.assertEqual(post.filename, "_posts/2026-10-18-acao-e-reacao-no-kotlin.md")
        self.assertEqual(post.image_path, "/assets/img/posts/ia-generated.png")
        self.assertEqual(post.date, NOW)
        images.generate_image.assert_called_once_with("a crab guarding memory blocks")
        repository.save_post.assert_called_once_with(post)
        # Todos os títulos recentes entram no prompt, não só o último
        self.assertIn("- N+1 em microsserviços", text.prompts[0])
        self.assertIn("https://cleissonbarbosa.github.io/posts/do-hype/", text.prompts[0])


class GenerateWeeklyDigestUseCaseTest(unittest.TestCase):
    def _use_case(self, items, *responses):
        news_source = mock.Mock()
        news_source.fetch_since.return_value = items
        images = mock.Mock()
        images.generate_image.return_value = "/assets/img/posts/capa.png"
        self.repository = _repository()
        self.text = FakeTextGenerator(*responses)
        return GenerateWeeklyDigestUseCase(self.repository, self.text, images, news_source, clock=lambda: NOW)

    def test_links_citations_and_forces_taxonomy(self):
        content = " ".join(f"Fato {i} [{i}]." for i in range(1, 7)) + " " + BODY
        response = draft_json(
            title="Resumo da Semana: testes", categories=["outra"], tags=["ia"], content=content
        )

        post = self._use_case(news(12), response).execute()

        self.assertEqual(post.categories, ["noticias", "tecnologia", "resumo-semanal"])
        self.assertEqual(post.tags, ["resumo-semanal", "ia"])
        self.assertIn("[1](https://example.com/1)", post.content)
        self.assertIn("## Fontes", post.content)
        self.assertIn("[12] Notícia 12", self.text.prompts[0])

    def test_rejects_digest_that_ignores_the_news(self):
        use_case = self._use_case(news(12), draft_json(content="Sem citar nada. " + BODY))
        with self.assertRaises(InvalidDraftError):
            use_case.execute()
        self.repository.save_post.assert_not_called()

    def test_requires_enough_news(self):
        with self.assertRaises(RuntimeError):
            self._use_case(news(3)).execute()


if __name__ == "__main__":
    unittest.main()
