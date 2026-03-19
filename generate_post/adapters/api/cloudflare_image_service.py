import base64
import logging
import random
import uuid
from typing import Optional

import requests

from generate_post.core.domain.interfaces.image_generator_service import (
    ImageGeneratorServiceInterface,
)
from generate_post.config.env_config import EnvConfig
from generate_post.config.constants import ASSETS_DIR
from generate_post.utils.retry_decorator import retry

logger = logging.getLogger(__name__)

_IMAGE_ASSET_PREFIX = "/assets/img/posts"

_MODEL_CONFIGS = {
    "black-forest-labs/flux-1-schnell": lambda prompt: {
        "prompt": prompt,
        "steps": 8,
    },
    "leonardo/lucid-origin": lambda prompt: {
        "prompt": prompt,
        "guidance": 4.5,
        "width": 1120,
        "height": 1120,
        "steps": 25,
    },
    "leonardo/phoenix-1.0": lambda prompt: {
        "prompt": prompt,
        "negative_prompt": (
            "text, words, letters, watermark, "
            "signature, logo, low quality, "
            "blurry, pixelated, distorted"
        ),
        "width": 1024,
        "height": 1024,
        "steps": 25,
        "guidance": 4,
    },
}

_BINARY_SIGNATURES = (b"\x89PNG", b"\xff\xd8\xff")


class CloudflareImageService(ImageGeneratorServiceInterface):
    """Implementação do serviço de geração de imagens usando a API Cloudflare AI"""

    def __init__(self, env_config: Optional[EnvConfig] = None):
        self._env = env_config or EnvConfig.from_env()
        self._session = requests.Session()

    def create_image_prompt(
        self, title: str, categories: str, tags: str, content_preview: str
    ) -> str:
        """Cria um prompt para a IA gerar uma imagem relacionada ao post"""
        return (
            f"Professional digital illustration for a programming blog post. "
            f"Topic: {title}. "
            f"Key concepts: {categories}, {tags}. "
            f"Context: {content_preview[:300]}. "
            f"Style: Modern tech aesthetic with clean lines, vibrant gradients, "
            f"and abstract geometric shapes representing code and technology. "
            f"Include subtle visual metaphors related to the technical concepts. "
            f"Color palette: deep blues, electric purples, cyan accents on dark background. "
            f"No text, no watermarks, no logos, no people."
        )

    @retry(max_attempts=3, delay=3)
    def generate_image(
        self, title: str, categories: str, tags: str, content_preview: str
    ) -> Optional[str]:
        """Gera uma imagem relacionada ao post usando Cloudflare Workers AI"""
        try:
            self._env.validate_cloudflare()
        except ValueError:
            logger.warning(
                "Credenciais Cloudflare não encontradas. Pulando geração de imagem."
            )
            return None

        prompt = self.create_image_prompt(title, categories, tags, content_preview)
        logger.info("Prompt da imagem: %s...", prompt[:100])

        model = random.choice(list(_MODEL_CONFIGS))
        logger.info("Modelo de imagem selecionado: %s", model)

        req_json = _MODEL_CONFIGS[model](prompt)

        url = (
            f"https://api.cloudflare.com/client/v4/accounts/"
            f"{self._env.cf_account_id}/ai/run/@cf/{model}"
        )

        response = self._session.post(
            url,
            headers={
                "Authorization": f"Bearer {self._env.cf_api_token}",
                "Content-Type": "application/json",
            },
            json=req_json,
            timeout=120,
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
