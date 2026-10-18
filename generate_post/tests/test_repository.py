import json
import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from generate_post.adapters.repositories.file_post_repository import FilePostRepository
from generate_post.config.constants import TIMEZONE
from generate_post.core.domain.entities.post import Post
from generate_post.tests.helpers import BODY

# Mesmas verificações do job validate_and_merge dos workflows
_WORKFLOW_CHECKS = [
    r'^title:\s*".+"',
    r"^author:\s*.+",
    r"^date:\s*[0-9]{4}-[0-9]{2}-[0-9]{2}",
    r"^categories:\s*\[.+\]",
    r"^tags:\s*\[.+\]",
    r"^\s+path:\s*/.+",
]


class FilePostRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.posts_dir = Path(self.tmp.name) / "_posts"
        self.repo = FilePostRepository(posts_dir=self.posts_dir)

    def tearDown(self):
        self.tmp.cleanup()

    def _save(self, name: str, title: str) -> Path:
        path = self.posts_dir / name
        self.repo.save_post(
            Post(
                title=title,
                content=BODY,
                categories=["programação", "c#"],
                tags=["a: b", "[x]"],
                description='Descrição com "aspas"',
                date=datetime(2026, 10, 18, 19, 5, tzinfo=TIMEZONE),
                image_path="/assets/img/posts/x.png",
                filename=str(path),
            )
        )
        return path

    def test_front_matter_is_safe_and_passes_workflow_checks(self):
        path = self._save("2026-10-18-x.md", 'Rust: o "zero-cost" #1 & *mais*')
        front_matter = path.read_text(encoding="utf-8").split("---")[1]

        for pattern in _WORKFLOW_CHECKS:
            self.assertRegex(front_matter, re.compile(pattern, re.MULTILINE))

        fields = dict(line.split(": ", 1) for line in front_matter.strip().splitlines() if ": " in line and not line.startswith(" "))
        # Os valores são JSON, que também é YAML válido: nada vira Hash
        self.assertEqual(json.loads(fields["title"]), 'Rust: o "zero-cost" #1 & *mais*')
        self.assertEqual(json.loads(fields["categories"]), ["programação", "c#"])
        self.assertEqual(json.loads(fields["tags"]), ["a: b", "[x]", "ai-generated"])
        self.assertEqual(json.loads(fields["description"]), 'Descrição com "aspas"')
        self.assertEqual(fields["date"], "2026-10-18 19:05:00 -0300")

    def test_recent_posts_newest_first_without_footer(self):
        self._save("2026-10-01-velho.md", "Velho")
        self._save("2026-10-18-novo.md", 'Novo "post"')
        (self.posts_dir / "2026-09-01-antigo.md").write_text(
            '---\ntitle: "Antigo à mão"\n---\n\nTexto antigo\n', encoding="utf-8"
        )

        posts = self.repo.get_recent_posts(limit=2)

        self.assertEqual([p.title for p in posts], ['Novo "post"', "Velho"])
        self.assertEqual(posts[0].filename, "_posts/2026-10-18-novo.md")
        self.assertEqual(posts[0].content, BODY.strip())
        self.assertEqual(self.repo.get_recent_posts(limit=5)[-1].title, "Antigo à mão")


if __name__ == "__main__":
    unittest.main()
