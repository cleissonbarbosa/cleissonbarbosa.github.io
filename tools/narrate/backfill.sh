#!/usr/bin/env bash
# Backfill MP3 narration for every post that doesn't yet have `audio:` in its
# frontmatter. Runs locally; extra args are forwarded to narrate.py (e.g.
# `./backfill.sh --voice pf_dora --max-posts 3`).
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)
cd "$REPO_DIR"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "❌ missing dependency: $1" >&2
    case "$1" in
      ffmpeg|espeak-ng)
        echo "   install with: sudo apt-get install -y espeak-ng ffmpeg" >&2 ;;
      python3)
        echo "   install Python 3.10+ (https://www.python.org/downloads/)" >&2 ;;
    esac
    exit 1
  fi
}
need python3
need ffmpeg
need espeak-ng

VENV="$REPO_DIR/.venv-narrate"
if [ ! -d "$VENV" ]; then
  echo "==> creating virtualenv at $VENV"
  python3 -m venv "$VENV"
fi
# shellcheck source=/dev/null
source "$VENV/bin/activate"

echo "==> installing python deps"
pip install --quiet --upgrade pip
pip install --quiet -r "$SCRIPT_DIR/requirements.txt"

echo
echo "==> pending posts"
python "$SCRIPT_DIR/narrate.py" --all-missing --dry-run

echo
echo "==> generating audio (this can take several minutes per post on CPU)"
python "$SCRIPT_DIR/narrate.py" --all-missing "$@"

echo
echo "==> done. review the diff and commit:"
echo "    git status"
echo "    git add _posts assets/audio"
echo "    git commit -m 'Backfill narrated audio for retroactive posts'"
