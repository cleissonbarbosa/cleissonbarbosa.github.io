import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from unittest import mock

import requests

from generate_post.adapters.news.feed_news_source import FeedNewsSource, _parse_entry
from generate_post.tests.helpers import http_response

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item><title>Nova vers\xc3\xa3o &amp; mais</title><link>https://ex.com/a?utm_source=rss</link>
<pubDate>Thu, 15 Oct 2026 10:00:00 +0000</pubDate>
<description>&lt;p&gt;Resumo &lt;b&gt;importante&lt;/b&gt;.&lt;/p&gt; The post X appeared first on Blog.</description></item>
<item><title>Antiga</title><link>https://ex.com/old</link><pubDate>Mon, 01 Sep 2026 10:00:00 +0000</pubDate></item>
<item><title>Link perigoso</title><link>javascript:alert(1)</link><pubDate>Thu, 15 Oct 2026 10:00:00 +0000</pubDate></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Atom post</title><link rel="alternate" href="https://ex.com/atom(1)"/>
<link rel="replies" href="https://ex.com/comments"/>
<updated>2026-10-16T08:30:00Z</updated><summary>Resumo atom</summary></entry>
</feed>"""

SINCE = datetime(2026, 10, 11, tzinfo=timezone.utc)


class ParseEntryTest(unittest.TestCase):
    def test_rss_item(self):
        entry = ET.fromstring(RSS).find("channel/item")
        item = _parse_entry(entry, "Blog")
        self.assertEqual(item.title, "Nova versão & mais")
        self.assertEqual(item.summary, "Resumo importante .")
        self.assertEqual(item.published, datetime(2026, 10, 15, 10, tzinfo=timezone.utc))

    def test_atom_entry_uses_alternate_link(self):
        entry = ET.fromstring(ATOM)[0]
        item = _parse_entry(entry, "Atom")
        self.assertEqual(item.url, "https://ex.com/atom%281%29")
        self.assertEqual(item.published, datetime(2026, 10, 16, 8, 30, tzinfo=timezone.utc))


class FeedNewsSourceTest(unittest.TestCase):
    def test_collects_filters_dedupes_and_enriches(self):
        source = FeedNewsSource(feeds=[("Blog", "https://ex.com/rss"), ("Atom", "https://ex.com/atom"), ("Fora", "https://down")])
        hn = {
            "hits": [
                {"title": "Mesma notícia", "url": "https://www.ex.com/a/", "points": 300, "created_at_i": 1792065600, "objectID": "1"},
                {"title": "Ask HN: algo", "url": None, "points": 200, "created_at_i": 1792065600, "objectID": "2"},
                {"title": "Página nova", "url": "https://site.com/p", "points": 500, "created_at_i": 1792065600, "objectID": "3"},
            ]
        }
        bodies = {
            "https://ex.com/rss": RSS,
            "https://ex.com/atom": ATOM,
            "https://site.com/p": b'<html><head><meta content="Descri\xc3\xa7\xc3\xa3o da p\xc3\xa1gina" property="og:description"></head></html>',
        }

        def limited(url, limit):
            if url not in bodies:
                raise requests.ConnectionError("fora do ar")
            return bodies[url]

        source._get_limited = limited
        source._session.get = mock.Mock(return_value=_json_response(hn))

        items = source.fetch_since(SINCE)

        self.assertEqual(
            [(i.source, i.title) for i in items],
            [
                ("Hacker News", "Página nova"),
                ("Hacker News", "Mesma notícia"),  # o item do RSS com a mesma URL sai
                ("Hacker News", "Ask HN: algo"),
                ("Atom", "Atom post"),
            ],
        )
        self.assertEqual(items[0].summary, "Descrição da página")
        self.assertEqual(items[0].score, 500)
        self.assertEqual(items[2].url, "https://news.ycombinator.com/item?id=2")
        params = source._session.get.call_args.kwargs["params"]
        self.assertIn(f"created_at_i>{int(SINCE.timestamp())}", params["numericFilters"])

    def test_hacker_news_down_is_not_fatal(self):
        source = FeedNewsSource(feeds=[("Atom", "https://ex.com/atom")])
        source._get_limited = lambda url, limit: ATOM
        source._session.get = mock.Mock(side_effect=requests.ConnectionError("fora"))
        self.assertEqual([i.title for i in source.fetch_since(SINCE)], ["Atom post"])


def _json_response(payload):
    response = http_response(200, payload)
    response.raise_for_status = mock.Mock()
    return response


if __name__ == "__main__":
    unittest.main()
