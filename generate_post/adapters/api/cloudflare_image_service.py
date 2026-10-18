import base64
import logging
import uuid
from typing import Optional

import requests

from generate_post.core.domain.interfaces.image_generator_service import (
    ImageGeneratorServiceInterface,
)
from generate_post.config.env_config import EnvConfig
from generate_post.config.constants import ASSETS_DIR
from generate_post.utils.model_fallback import first_successful
from generate_post.utils.retry_decorator import retry

logger = logging.getLogger(__name__)

_IMAGE_ASSET_PREFIX = "/assets/img/posts"

# Proporção 40:21 do cabeçalho de post do tema Chirpy (múltiplos de 16 para o FLUX.2)
_WIDTH, _HEIGHT = 1280, 672

# Ordem de preferência. Os FLUX.2 só aceitam multipart/form-data; os demais, JSON.
# Custo aproximado por imagem (free tier: 10.000 neurons/dia): klein-9b ~1.360,
# klein-4b ~160, lucid-origin ~4.100, flux-1-schnell ~100.
_MODEL_CONFIGS = {
    "black-forest-labs/flux-2-klein-9b": (
        "multipart",
        lambda prompt: {"prompt": prompt, "width": _WIDTH, "height": _HEIGHT},
    ),
    "black-forest-labs/flux-2-klein-4b": (
        "multipart",
        lambda prompt: {"prompt": prompt, "width": _WIDTH, "height": _HEIGHT},
    ),
    "leonardo/lucid-origin": (
        "json",
        lambda prompt: {
            "prompt": prompt,
            "guidance": 4.5,
            "width": _WIDTH,
            "height": _HEIGHT,
            "steps": 25,
        },
    ),
    # Não aceita dimensões (sai 1024x1024); fica como última reserva.
    "black-forest-labs/flux-1-schnell": (
        "json",
        lambda prompt: {"prompt": prompt, "steps": 8},
    ),
}

_BINARY_SIGNATURES = (b"\x89PNG", b"\xff\xd8\xff")


class CloudflareImageService(ImageGeneratorServiceInterface):
    """Implementação do serviço de geração de imagens usando a API Cloudflare AI"""

    def __init__(self, env_config: Optional[EnvConfig] = None):
        self._env = env_config or EnvConfig.from_env()
        self._session = requests.Session()

    def create_image_prompt(self, description: str) -> str:
        """Combina a descrição visual do post com o estilo fixo do blog"""
        return (
            f"Wide editorial illustration for a software engineering blog post: "
            f"{description[:600]}. "
            f"Style: modern tech aesthetic with clean lines, vibrant gradients "
            f"and abstract geometric shapes; subtle visual metaphors for the "
            f"technical concepts. Color palette: deep blues, electric purples, "
            f"cyan accents on dark background. "
            f"No text, no letters, no watermarks, no logos, no people."
        )

    def generate_image(self, description: str) -> Optional[str]:
        """Gera a imagem de capa usando Cloudflare Workers AI"""
        try:
            self._env.validate_cloudflare()
        except ValueError:
            logger.warning(
                "Credenciais Cloudflare não encontradas. Pulando geração de imagem."
            )
            return None

        prompt = self.create_image_prompt(description)
        logger.info("Prompt da imagem: %s...", prompt[:150])

        try:
            return first_successful(
                list(_MODEL_CONFIGS),
                lambda model: self._generate_with_model(model, prompt),
            )
        except RuntimeError:
            # Sem imagem o post ainda sai (com a imagem padrão); perder o post
            # inteiro por causa da capa seria pior
            logger.exception("Nenhum modelo de imagem funcionou")
            return None

    @retry(max_attempts=2, delay=3)
    def _generate_with_model(self, model: str, prompt: str) -> str:
        kind, build_payload = _MODEL_CONFIGS[model]
        payload = build_payload(prompt)

        url = (
            f"https://api.cloudflare.com/client/v4/accounts/"
            f"{self._env.cf_account_id}/ai/run/@cf/{model}"
        )
        headers = {"Authorization": f"Bearer {self._env.cf_api_token}"}

        if kind == "multipart":
            # (None, valor) faz o requests enviar campos de formulário sem arquivo
            files = {key: (None, str(value)) for key, value in payload.items()}
            response = self._session.post(
                url, headers=headers, files=files, timeout=120
            )
        else:
            response = self._session.post(
                url, headers=headers, json=payload, timeout=120
            )

        if response.status_code != 200:
            raise requests.RequestException(
                f"Erro ao gerar imagem. Status: {response.status_code}, "
                f"Resposta: {response.text[:500]}"
            )

        return self._save_response_image(response)

    def _save_response_image(self, response: requests.Response) -> str:
        """Processa a resposta e salva a imagem no disco."""
        image_filename = f"{uuid.uuid4()}.png"
        image_path = ASSETS_DIR / image_filename
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)

        content_type = response.headers.get("Content-Type", "")

        # Resposta binária direta
        if self._is_binary_image(content_type, response.content):
            image_path.write_bytes(response.content)
            logger.info("Imagem binária salva: %s", image_path)
            return f"{_IMAGE_ASSET_PREFIX}/{image_filename}"

        # Resposta JSON com base64
        try:
            data = response.json()
        except ValueError:
            image_path.write_bytes(response.content)
            logger.warning("Resposta não-JSON salva como imagem: %s", image_path)
            return f"{_IMAGE_ASSET_PREFIX}/{image_filename}"

        if not data.get("success", False):
            raise requests.RequestException(f"Erro na resposta da API: {data}")

        result = data.get("result")
        if not result:
            raise requests.RequestException(
                f"Campo 'result' não encontrado na resposta: {data}"
            )

        image_b64 = result.get("image", result) if isinstance(result, dict) else result
        image_path.write_bytes(base64.b64decode(image_b64))
        logger.info("Imagem base64 decodificada e salva: %s", image_path)
        return f"{_IMAGE_ASSET_PREFIX}/{image_filename}"

    @staticmethod
    def _is_binary_image(content_type: str, content: bytes) -> bool:
        """Verifica se a resposta contém uma imagem binária."""
        if "image/" in content_type:
            return True
        return any(content.startswith(sig) for sig in _BINARY_SIGNATURES)
