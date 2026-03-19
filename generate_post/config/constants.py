from pathlib import Path

# Diretório raiz do projeto
ROOT_DIR = Path(__file__).resolve().parents[2]

# Diretório de assets para posts
ASSETS_DIR = ROOT_DIR / "assets" / "img" / "posts"

# Diretório de posts
POSTS_DIR = ROOT_DIR / "_posts"

# Configuração de retries
MAX_RETRIES = 3
RETRY_DELAY = 2  # segundos
