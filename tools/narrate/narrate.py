#!/usr/bin/env python3
"""Generate MP3 narration for a Jekyll post using Kokoro TTS.

Reads a markdown post, strips it down to readable text, runs Kokoro to produce
audio (24 kHz WAV) and re-encodes to 64 kbps mono MP3 via ffmpeg. Then updates
the post frontmatter so the audio-player.html include can render.
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import soundfile as sf
import yaml

LOGGER = logging.getLogger("narrate")

SAMPLE_RATE = 24_000
DEFAULT_VOICE = "pf_dora"
DEFAULT_LANG = "p"
DEFAULT_SPEED = 1.0
DEFAULT_MIN_WORDS = 200
DEFAULT_AUDIO_DIR = Path("assets/audio/posts")
DEFAULT_AUDIO_URL_PREFIX = "/assets/audio/posts"
DEFAULT_BITRATE = "64k"


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`]*`")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
IAL_RE = re.compile(r"\{:[^}]*\}")
HTML_TAG_RE = re.compile(r"<[^>]+>")
HEADER_MARK_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
BOLD_ITALIC_RE = re.compile(r"(\*{1,3}|_{1,3})(.+?)\1")
BLOCKQUOTE_RE = re.compile(r"^\s*>\s?", re.MULTILINE)
LIST_BULLET_RE = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
LIST_NUM_RE = re.compile(r"^\s*\d+\.\s+", re.MULTILINE)
WHITESPACE_RE = re.compile(r"[ \t]+")
BLANK_LINES_RE = re.compile(r"\n{3,}")


@dataclass
class PostParts:
    frontmatter: dict
    body: str
    raw_frontmatter: str


def parse_post(path: Path) -> PostParts:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"No YAML frontmatter found in {path}")
    raw_fm = match.group(1)
    fm = yaml.safe_load(raw_fm) or {}
    body = text[match.end():]
    return PostParts(frontmatter=fm, body=body, raw_frontmatter=raw_fm)


def strip_for_narration(markdown: str) -> str:
    """Convert markdown into a clean, narratable plain-text stream."""
    text = markdown
    text = FENCED_CODE_RE.sub(" ", text)
    text = IMAGE_RE.sub(" ", text)
    text = LINK_RE.sub(r"\1", text)
    text = INLINE_CODE_RE.sub(" ", text)
    text = IAL_RE.sub("", text)
    text = HTML_TAG_RE.sub(" ", text)
    text = HEADER_MARK_RE.sub("", text)
    text = BOLD_ITALIC_RE.sub(r"\2", text)
    text = BLOCKQUOTE_RE.sub("", text)
    text = LIST_BULLET_RE.sub("", text)
    text = LIST_NUM_RE.sub("", text)
    text = WHITESPACE_RE.sub(" ", text)
    text = BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def slug_for_post(path: Path) -> str:
    name = path.stem
    name = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", name)
    return name


def synthesize(text: str, voice: str, lang: str, speed: float) -> np.ndarray:
    """Run Kokoro and return a single concatenated waveform."""
    from kokoro import KPipeline  # imported lazily — heavy dep

    pipeline = KPipeline(lang_code=lang)
    chunks: list[np.ndarray] = []
    for _, _, audio in pipeline(text, voice=voice, speed=speed):
        if audio is None:
            continue
        if hasattr(audio, "detach"):
            audio = audio.detach().cpu().numpy()
        chunks.append(np.asarray(audio, dtype=np.float32))
    if not chunks:
        raise RuntimeError("Kokoro produced no audio chunks")
    return np.concatenate(chunks)


def encode_mp3(wav_path: Path, mp3_path: Path, bitrate: str, metadata: dict) -> None:
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(wav_path),
        "-ac", "1",
        "-b:a", bitrate,
        "-codec:a", "libmp3lame",
    ]
    for key, value in metadata.items():
        if value:
            cmd.extend(["-metadata", f"{key}={value}"])
    cmd.append(str(mp3_path))
    subprocess.run(cmd, check=True)


def write_audio(text: str, mp3_path: Path, voice: str, lang: str, speed: float,
                bitrate: str, metadata: dict) -> None:
    waveform = synthesize(text, voice=voice, lang=lang, speed=speed)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        sf.write(tmp_path, waveform, SAMPLE_RATE)
        encode_mp3(tmp_path, mp3_path, bitrate=bitrate, metadata=metadata)
    finally:
        tmp_path.unlink(missing_ok=True)


def update_frontmatter(path: Path, audio_url: str) -> None:
    """Insert an `audio:` key into the post frontmatter, preserving formatting."""
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"No frontmatter to update in {path}")
    raw_fm = match.group(1)
    body = text[match.end():]

    line = f"audio: {audio_url}"
    if re.search(r"^audio:\s*.*$", raw_fm, re.MULTILINE):
        new_fm = re.sub(r"^audio:\s*.*$", line, raw_fm, count=1, flags=re.MULTILINE)
    else:
        new_fm = raw_fm.rstrip() + "\n" + line

    path.write_text(f"---\n{new_fm}\n---\n{body}", encoding="utf-8")


def discover_posts(posts_dir: Path) -> list[Path]:
    return sorted(p for p in posts_dir.glob("*.md") if p.is_file())


def needs_audio(post: Path, min_words: int) -> tuple[bool, str]:
    parts = parse_post(post)
    if parts.frontmatter.get("audio"):
        return False, "already has audio"
    text = strip_for_narration(parts.body)
    wc = word_count(text)
    if wc < min_words:
        return False, f"only {wc} words (< {min_words})"
    return True, f"{wc} words"


def narrate_one(post: Path, *, audio_dir: Path, url_prefix: str, voice: str,
                lang: str, speed: float, bitrate: str, min_words: int,
                site_title: str | None) -> Path | None:
    LOGGER.info("Processing %s", post)
    parts = parse_post(post)
    if parts.frontmatter.get("audio"):
        LOGGER.info("  skip: already has audio (%s)", parts.frontmatter["audio"])
        return None
    text = strip_for_narration(parts.body)
    wc = word_count(text)
    if wc < min_words:
        LOGGER.info("  skip: %d words below threshold %d", wc, min_words)
        return None
    LOGGER.info("  narrating %d words with voice=%s lang=%s speed=%s",
                wc, voice, lang, speed)

    slug = slug_for_post(post)
    mp3_path = audio_dir / f"{slug}.mp3"

    metadata = {
        "title": parts.frontmatter.get("title", slug),
        "artist": parts.frontmatter.get("author", ""),
        "album": site_title or "",
    }
    write_audio(text, mp3_path, voice=voice, lang=lang, speed=speed,
                bitrate=bitrate, metadata=metadata)
    url = f"{url_prefix.rstrip('/')}/{slug}.mp3"
    update_frontmatter(post, url)
    LOGGER.info("  wrote %s (%.1f KB)", mp3_path, mp3_path.stat().st_size / 1024)
    return mp3_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("posts", nargs="*", type=Path,
                        help="Specific post markdown files to narrate")
    parser.add_argument("--all-missing", action="store_true",
                        help="Scan _posts/ and narrate every post lacking audio")
    parser.add_argument("--posts-dir", default=Path("_posts"), type=Path)
    parser.add_argument("--audio-dir", default=DEFAULT_AUDIO_DIR, type=Path)
    parser.add_argument("--url-prefix", default=DEFAULT_AUDIO_URL_PREFIX,
                        help="URL prefix written into frontmatter")
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    parser.add_argument("--lang", default=DEFAULT_LANG,
                        help="Kokoro language code (p=pt-br, a=en-us, ...)")
    parser.add_argument("--speed", default=DEFAULT_SPEED, type=float)
    parser.add_argument("--bitrate", default=DEFAULT_BITRATE)
    parser.add_argument("--min-words", default=DEFAULT_MIN_WORDS, type=int)
    parser.add_argument("--max-posts", default=0, type=int,
                        help="Cap how many posts to narrate this run (0 = no cap)")
    parser.add_argument("--site-title", default=os.environ.get("SITE_TITLE", ""))
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be narrated without generating audio")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def select_posts(args: argparse.Namespace) -> Iterable[Path]:
    if args.posts:
        return [p.resolve() for p in args.posts]
    if args.all_missing:
        candidates = discover_posts(args.posts_dir)
        return [p for p in candidates if needs_audio(p, args.min_words)[0]]
    raise SystemExit("Pass post paths or --all-missing")


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    posts = list(select_posts(args))
    if not posts:
        LOGGER.info("Nothing to narrate.")
        return 0

    if args.max_posts and len(posts) > args.max_posts:
        LOGGER.info("Capping to %d of %d posts", args.max_posts, len(posts))
        posts = posts[: args.max_posts]

    if args.dry_run:
        for post in posts:
            ok, reason = needs_audio(post, args.min_words)
            LOGGER.info("%s -> %s (%s)", post, "narrate" if ok else "skip", reason)
        return 0

    args.audio_dir.mkdir(parents=True, exist_ok=True)
    failures: list[Path] = []
    for post in posts:
        try:
            narrate_one(
                post,
                audio_dir=args.audio_dir,
                url_prefix=args.url_prefix,
                voice=args.voice,
                lang=args.lang,
                speed=args.speed,
                bitrate=args.bitrate,
                min_words=args.min_words,
                site_title=args.site_title or None,
            )
        except Exception:  # noqa: BLE001
            LOGGER.exception("Failed to narrate %s", post)
            failures.append(post)

    if failures:
        LOGGER.error("%d post(s) failed: %s", len(failures), failures)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
