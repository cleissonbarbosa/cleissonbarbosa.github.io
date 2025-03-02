from pathlib import Path
import os

# Diretório raiz do projeto
ROOT_DIR = Path(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # noqa
)

# Diretório de assets para posts
ASSETS_DIR = ROOT_DIR / "assets" / "img" / "posts"

# Diretório de posts
POSTS_DIR = ROOT_DIR / "_posts"

# Configuração de retries
MAX_RETRIES = 3
RETRY_DELAY = 2  # segundos
