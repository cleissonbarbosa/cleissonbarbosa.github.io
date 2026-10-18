import logging
from typing import Callable, Optional, Sequence, TypeVar

import requests

from generate_post.config.env_config import EnvConfig
from generate_post.core.domain.interfaces.text_generator import TextGeneratorInterface
from generate_post.utils.model_fallback import ModelUnavailableError, first_successful
from generate_post.utils.retry_decorator import retry

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Modelos abertos disponíveis no plano Workers Free (10.000 neurons/dia, os
# mesmos créditos das imagens). Um post custa ~500 neurons no gpt-oss-120b.
# kimi-k2.6, glm-5.3 e deepseek-v4 exigem o plano pago.
_MODELS = (
    "@cf/openai/gpt-oss-120b",
    "@cf/google/gemma-4-26b-a4b-it",
)

_PERMANENT_STATUS = {400, 403, 404}


class CloudflareTextGenerator(TextGeneratorInterface):
    """Geração de texto pelo Workers AI (endpoint compatível com OpenAI)."""

    name = "cloudflare"

    def __init__(
        self,
        env_config: Optional[EnvConfig] = None,
        models: Sequence[str] = _MODELS,
        timeout: int = 240,
    ):
        self._env = env_config or EnvConfig.from_env()
        self._models = models
        self._timeout = timeout
        self._session = requests.Session()

    def is_configured(self) -> bool:
        return bool(self._env.cf_api_token and self._env.cf_account_id)

    def generate(self, system: str, prompt: str, parse: Callable[[str], T]) -> T:
        self._env.validate_cloudflare()
        return first_successful(
            self._models, lambda model: parse(self._generate_text(model, system, prompt))
        )

    @retry(max_attempts=2, delay=5, giveup=(ModelUnavailableError, requests.Timeout))
    def _generate_text(self, model: str, system: str, prompt: str) -> str:
        response = self._session.post(
            f"https://api.cloudflare.com/client/v4/accounts/"
            f"{self._env.cf_account_id}/ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._env.cf_api_token}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 16384,
            },
            timeout=self._timeout,
        )

        if response.status_code in _PERMANENT_STATUS:
            raise ModelUnavailableError(
                f"Status: {response.status_code}, Resposta: {response.text[:500]}"
            )
        if response.status_code != 200:
            raise requests.RequestException(
                f"Status: {response.status_code}, Resposta: {response.text[:500]}"
            )

        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise ValueError(f"Resposta sem conteúdo: {str(data)[:500]}")

        choice = choices[0]
        if choice.get("finish_reason") == "length":
            raise ModelUnavailableError("Resposta truncada (finish_reason=length)")

        logger.info("Cloudflare %s: uso %s", model, data.get("usage"))
        return (choice.get("message") or {}).get("content") or ""
