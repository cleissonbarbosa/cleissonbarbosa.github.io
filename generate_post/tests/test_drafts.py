import unittest

from generate_post.core.use_cases.drafts import (
    InvalidDraftError,
    clean_labels,
    link_citations,
    parse_draft,
    slugify,
)
from generate_post.tests.helpers import BODY, draft_json, news

DEFAULTS = (["programação"], ["programação"])


class ParseDraftTest(unittest.TestCase):
    def test_valid_json(self):
        draft = parse_draft(draft_json(), *DEFAULTS)
        self.assertEqual(draft.title, "Rust: ownership na prática")
        self.assertEqual(draft.categories, ["programação", "rust"])
        self.assertEqual(draft.tags, ["rust", "memória"])
        self.assertEqual(draft.image_prompt, "a crab guarding memory blocks")

    def test_code_fence_and_raw_newlines(self):
        # Modelos às vezes cercam o JSON com ``` e deixam quebras cruas nas strings
        text = '```json\n{"title": "T", "content": "linha 1\nlinha 2 ' + BODY + '"}\n```'
        draft = parse_draft(text, *DEFAULTS)
        self.assertTrue(draft.content.startswith("linha 1\nlinha 2"))
        self.assertEqual(draft.categories, ["programação"])
        self.assertEqual(draft.image_prompt, "T")

    def test_rejects_short_or_missing_content(self):
        with self.assertRaises(InvalidDraftError):
            parse_draft(draft_json(content="curto"), *DEFAULTS)
        with self.assertRaises(InvalidDraftError):
            parse_draft("Desculpe, não posso ajudar.", *DEFAULTS)
        with self.assertRaises(InvalidDraftError):
            parse_draft(draft_json(title=""), *DEFAULTS)

    def test_strips_title_markup_and_repeated_heading(self):
        draft = parse_draft(
            draft_json(title='**"Rust" #1**', content="# Rust 1\n\n" + BODY), *DEFAULTS
        )
        self.assertEqual(draft.title, "Rust 1")
        self.assertTrue(draft.content.startswith("Parágrafo"))

    def test_long_description_is_truncated(self):
        draft = parse_draft(draft_json(description="palavra " * 60), *DEFAULTS)
        self.assertLessEqual(len(draft.description), 200)
        self.assertTrue(draft.description.endswith("…"))


class CleanLabelsTest(unittest.TestCase):
    def test_rejects_sentences(self):
        # Caso real de 01/08: um parágrafo virou tag e quebrou o build do Jekyll
        labels = clean_labels(
            ["WASM", "que prometia exatamente isso: código portável", "## Intro", "fim de frase."]
        )
        self.assertEqual(labels, ["wasm"])

    def test_accepts_string_dedupes_and_caps(self):
        self.assertEqual(clean_labels("C#, .NET, node.js, c#"), ["c#", ".net", "node.js"])
        self.assertEqual(len(clean_labels([f"t{i}" for i in range(20)])), 8)
        self.assertEqual(clean_labels(None), [])


class SlugifyTest(unittest.TestCase):
    def test_ascii_slug(self):
        self.assertEqual(slugify("Ação & Reação: o Zero-Cost às vezes custa caro"), "acao-reacao-o-zero-cost-as-vezes-custa-caro")

    def test_long_title_cut_at_word(self):
        slug = slugify("palavra " * 30)
        self.assertLessEqual(len(slug), 80)
        self.assertFalse(slug.endswith("-"))
        self.assertTrue(slug.endswith("palavra"))


class LinkCitationsTest(unittest.TestCase):
    def test_links_real_urls_and_lists_only_cited_sources(self):
        items = news(3)
        text, cited = link_citations(
            "Fato A [3]. Fato B [1][3]. Link inventado [veja aqui](https://fake.example). "
            "Citação com URL do modelo [2](https://errada.example). Fora da lista [9].",
            items,
        )
        self.assertEqual(cited, [3, 1, 2])
        self.assertIn('Fato A [3](https://example.com/3){:target="_blank"}', text)
        self.assertIn("[2](https://example.com/2)", text)
        self.assertNotIn("fake.example", text)
        self.assertNotIn("errada.example", text)
        self.assertIn("Link inventado veja aqui.", text)
        self.assertIn("Fora da lista .", text)
        fontes = text.split("## Fontes")[1]
        self.assertEqual(fontes.count("- ["), 3)

    def test_no_citations(self):
        text, cited = link_citations("Sem fontes.", news(2))
        self.assertEqual((text, cited), ("Sem fontes.", []))


if __name__ == "__main__":
    unittest.main()
