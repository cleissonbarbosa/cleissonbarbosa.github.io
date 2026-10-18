import html
import logging
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable, Optional
from urllib.parse import urlsplit, urlunsplit

import requests

from generate_post.core.domain.entities.news_item import NewsItem
from generate_post.core.domain.interfaces.news_source import NewsSourceInterface

logger = logging.getLogger(__name__)

# Fontes gratuitas e sem chave. Os links vêm direto dos feeds, então são as
# URLs reais e permanentes das notícias (o grounding do Gemini devolvia
# redirects do Google que expiram e viravam 404 nos resumos antigos).
_FEEDS = (
    ("GitHub Changelog", "https://github.blog/changelog/feed/"),
    ("InfoQ", "https://feed.infoq.com/"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("Lobsters", "https://lobste.rs/rss"),
    ("The Hacker News", "https://feeds.feedburner.com/TheHackersNews"),
    ("BleepingComputer", "https://www.bleepingcomputer.com/feed/"),
    ("Hugging Face", "https://huggingface.co/blog/feed.xml"),
    ("Cloudflare Blog", "https://blog.cloudflare.com/rss/"),
    ("AWS News Blog", "https://aws.amazon.com/blogs/aws/feed/"),
    ("Microsoft DevBlogs", "https://devblogs.microsoft.com/feed/"),
    ("The Verge", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("TechCrunch", "https://techcrunch.com/category/artificial-intelligence/feed/"),
)

# Os pontos do Hacker News são o melhor sinal gratuito de "o que bombou na semana"
_HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
_HN_MIN_POINTS = 150
_HN_LIMIT = 25

_PER_FEED_LIMIT = 6
_MAX_ITEMS = 80
_MAX_RESPONSE_BYTES = 5 * 1024 * 1024
_MAX_PAGE_BYTES = 512 * 1024
_SUMMARY_CHARS = 280
_TITLE_CHARS = 200
_TIMEOUT = 15
_USER_AGENT = (
    "Mozilla/5.0 (compatible; cleissonbarbosa-weekly-digest/1.0; "
    "+https://github.com/cleissonbarbosa/cleissonbarbosa.github.io)"
)

_TAG_RE = re.compile(r"<[^>]+>")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_META_RE = re.compile(r"<meta\s[^>]*>", re.IGNORECASE)
_ATTR_RE = re.compile(r'([\w:-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')')
_DESCRIPTION_KEYS = ("og:description", "description", "twitter:description")
# Rodapé que o WordPress anexa à descrição dos itens
_WP_FOOTER_RE = re.compile(r"\s*The post .+ appeared first on .+$")


class FeedNewsSource(NewsSourceInterface):
    """Coleta notícias do Hacker News e de feeds RSS/Atom de tecnologia."""

    def __init__(self, feeds: Iterable[tuple[str, str]] = _FEEDS):
        self._feeds = tuple(feeds)
        self._session = requests.Session()
        self._session.headers["User-Agent"] = _USER_AGENT

    def fetch_since(self, since: datetime) -> list[NewsItem]:
        with ThreadPoolExecutor(max_workers=8) as pool:
            hn = pool.submit(self._fetch_hacker_news, since)
            feeds = [pool.submit(self._fetch_feed, name, url, since) for name, url in self._feeds]
            batches = [hn.result()] + [f.result() for f in feeds]

        items = _dedupe(item for batch in batches for item in batch)[:_MAX_ITEMS]

        # O Hacker News só tem título; a descrição da página dá contexto ao modelo
        with ThreadPoolExecutor(max_workers=8) as pool:
            items = list(pool.map(self._with_summary, items))

        names = ["Hacker News"] + [name for name, _ in self._feeds]
        logger.info(
            "Notícias coletadas: %d (%s)",
            len(items),
            ", ".join(f"{name}: {len(batch)}" for name, batch in zip(names, batches, strict=True)),
        )
        return items

    def _fetch_hacker_news(self, since: datetime) -> list[NewsItem]:
        try:
            response = self._session.get(
                _HN_SEARCH_URL,
                params={
                    "tags": "story",
                    "numericFilters": f"created_at_i>{int(since.timestamp())},points>{_HN_MIN_POINTS}",
                    "hitsPerPage": 100,
                },
                timeout=_TIMEOUT,
            )
            response.raise_for_status()
            hits = response.json().get("hits", [])
        except (requests.RequestException, ValueError) as e:
            logger.warning("Hacker News indisponível: %s", e)
            return []

        items = []
        for hit in sorted(hits, key=lambda h: h.get("points") or 0, reverse=True):
            url = _safe_url(hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}")
            title = _plain_text(hit.get("title") or "", _TITLE_CHARS)
            if url and title:
                items.append(
                    NewsItem(
                        title=title,
                        url=url,
                        source="Hacker News",
                        published=datetime.fromtimestamp(hit.get("created_at_i", 0), tz=timezone.utc),
                        score=hit.get("points") or 0,
                    )
                )
        return items[:_HN_LIMIT]

    def _fetch_feed(self, name: str, url: str, since: datetime) -> list[NewsItem]:
        try:
            root = ET.fromstring(self._get_limited(url, _MAX_RESPONSE_BYTES))
        except (requests.RequestException, ET.ParseError) as e:
            logger.warning("Feed %s indisponível: %s", name, e)
            return []

        items = [
            item
            for item in (_parse_entry(entry, name) for entry in root.iter() if _local(entry.tag) in ("item", "entry"))
            if item and item.published >= since
        ]
        items.sort(key=lambda i: i.published, reverse=True)
        return items[:_PER_FEED_LIMIT]

    def _with_summary(self, item: NewsItem) -> NewsItem:
        # Discussões do próprio HN não têm descrição útil na página
        if item.summary or urlsplit(item.url).hostname == "news.ycombinator.com":
            return item
        try:
            page = self._get_limited(item.url, _MAX_PAGE_BYTES).decode("utf-8", "replace")
        except requests.RequestException:
            return item
        summary = _page_description(page)
        return replace(item, summary=summary) if summary else item

    def _get_limited(self, url: str, limit: int) -> bytes:
        with self._session.get(url, timeout=_TIMEOUT, stream=True) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(64 * 1024):
                chunks.append(chunk)
                size += len(chunk)
                if size >= limit:
                    break
            return b"".join(chunks)[:limit]


def _parse_entry(entry: ET.Element, source: str) -> Optional[NewsItem]:
    fields: dict[str, str] = {}
    link = ""
    for child in entry:
        name = _local(child.tag)
        if name == "link":
            # RSS: <link>url</link>; Atom: <link rel="alternate" href="url"/>
            if child.get("href") and child.get("rel", "alternate") == "alternate":
                link = link or child.get("href", "")
            elif child.text and child.text.strip():
                link = link or child.text.strip()
        elif name not in fields:
            fields[name] = "".join(child.itertext())

    published = _parse_date(
        fields.get("pubDate") or fields.get("published") or fields.get("updated") or fields.get("date") or ""
    )
    url = _safe_url(link)
    title = _plain_text(fields.get("title", ""), _TITLE_CHARS)
    if not (published and url and title):
        return None

    summary = _plain_text(fields.get("description") or fields.get("summary") or "", _SUMMARY_CHARS)
    return NewsItem(title=title, url=url, source=source, published=published, summary=summary)


def _page_description(page: str) -> str:
    found: dict[str, str] = {}
    for tag in _META_RE.findall(page):
        attrs = {k.lower(): (v1 or v2) for k, v1, v2 in _ATTR_RE.findall(tag)}
        key = (attrs.get("property") or attrs.get("name") or "").lower()
        if key in _DESCRIPTION_KEYS and attrs.get("content"):
            found.setdefault(key, attrs["content"])
    for key in _DESCRIPTION_KEYS:
        if key in found:
            return _plain_text(found[key], _SUMMARY_CHARS)
    return ""


def _parse_date(text: str) -> Optional[datetime]:
    text = text.strip()
    if not text:
        return None
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _plain_text(raw: str, limit: int) -> str:
    """HTML (às vezes escapado duas vezes nos feeds) para texto puro e curto."""
    text = html.unescape(_TAG_RE.sub(" ", html.unescape(raw)))
    text = _WP_FOOTER_RE.sub("", " ".join(_CONTROL_RE.sub(" ", text).split()))
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "…"


def _safe_url(url: str) -> str:
    """Só http(s), e sem caracteres que quebrariam o link em Markdown."""
    url = (url or "").strip()
    if urlsplit(url).scheme not in ("http", "https"):
        return ""
    return url.replace(" ", "%20").replace("(", "%28").replace(")", "%29")


def _dedupe(items: Iterable[NewsItem]) -> list[NewsItem]:
    seen: set[str] = set()
    unique = []
    for item in items:
        key = _url_key(item.url)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _url_key(url: str) -> str:
    parts = urlsplit(url)
    query = "&".join(p for p in parts.query.split("&") if p and not p.startswith("utm_"))
    host = parts.netloc.lower().removeprefix("www.")
    return urlunsplit(("", host, parts.path.rstrip("/"), query, ""))


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""
