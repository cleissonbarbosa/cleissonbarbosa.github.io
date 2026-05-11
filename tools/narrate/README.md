# narrate — Audio narration generator

Generates MP3 narration for posts using [Kokoro](https://github.com/hexgrad/kokoro)
TTS (CPU inference, free, runs in GitHub Actions). Hooks into the
`_includes/audio-player.html` component by writing an `audio:` field into the
post frontmatter.

## Local usage

System deps:

```bash
sudo apt-get install -y espeak-ng ffmpeg
```

Python deps:

```bash
pip install -r tools/narrate/requirements.txt
```

Narrate one post:

```bash
python tools/narrate/narrate.py _posts/2026-05-10-foo.md
```

Backfill every post lacking audio:

```bash
python tools/narrate/narrate.py --all-missing --max-posts 5
```

Useful flags:

| Flag | Default | Notes |
|------|---------|-------|
| `--voice` | `pf_dora` | Kokoro voice id (pt-BR: `pf_dora`, `pm_alex`, `pm_santa`) |
| `--lang` | `p` | Kokoro language code (`p`=pt-br, `a`=en-us, `b`=en-uk, ...) |
| `--speed` | `1.0` | Playback speed multiplier baked into the audio |
| `--bitrate` | `64k` | MP3 bitrate (mono) |
| `--min-words` | `200` | Skip posts shorter than this |
| `--dry-run` | — | Show which posts would be narrated |
| `--max-posts` | `0` | Cap how many posts to narrate per run |

## How it works

1. Reads the markdown file and splits YAML frontmatter from body.
2. Strips code fences, image syntax, kramdown attribute lists, HTML tags, etc.
3. Sends clean text through Kokoro (`KPipeline`) at 24 kHz.
4. Encodes the resulting waveform to a 64 kbps mono MP3 via `ffmpeg`,
   embedding the title/author/album as ID3 metadata.
5. Writes the file to `assets/audio/posts/<slug>.mp3`.
6. Inserts `audio: /assets/audio/posts/<slug>.mp3` into the post frontmatter.

## CI/CD

`.github/workflows/generate-audio.yml` runs on push to `main` whenever a file
under `_posts/` changes, generates audio for any new post missing the field,
commits the result and opens a PR.
