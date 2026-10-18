import logging
from typing import Callable, Optional, Sequence, TypeVar

import requests

from generate_post.config.env_config import EnvConfig
from generate_post.core.domain.interfaces.text_generator import TextGeneratorInterface
from generate_post.utils.model_fallback import ModelUnavailableError, first_successful
from generate_post.utils.retry_decorator import retry

logger = logging.getLogger(__name__)

T = TypeVar("T")

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# Ordem de preferência; todos com free tier. gemini-2.5-* ficou restrito a
# quem já usava e fica por último como reserva.
_MODELS = (
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
)

# Status que dizem que o modelo não atende esta chave (aposentado, sem acesso,
# payload incompatível). Repetir não adianta: o certo é ir para o próximo modelo.
_PERMANENT_STATUS = {400, 403, 404}


class GeminiTextGenerator(TextGeneratorInterface):
    """Geração de texto pela API Gemini (generateContent) com fallback de modelos."""

    name = "gemini"

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
        self._session.headers["Content-Type"] = "application/json"

    def is_configured(self) -> bool:
        return bool(self._env.gemini_api_key)

    def generate(self, system: str, prompt: str, parse: Callable[[str], T]) -> T:
        self._env.validate_gemini()
        return first_successful(
            self._models, lambda model: parse(self._generate_text(model, system, prompt))
        )

    @retry(max_attempts=2, delay=5, giveup=(ModelUnavailableError, requests.Timeout))
    def _generate_text(self, model: str, system: str, prompt: str) -> str:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_ONLY_HIGH",
                }
            ],
            # Sem temperature: o Gemini 3 recomenda o padrão (1.0) e o 3.6+ ignora
            # o campo. O limite de saída cobre também os tokens de thinking.
            "generationConfig": {
                "responseMimeType": "application/json",
                "maxOutputTokens": 32768,
            },
        }

        response = self._session.post(
            f"{_BASE_URL}/{model}:generateContent",
            headers={"x-goog-api-key": self._env.gemini_api_key},
            json=body,
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
        candidates = data.get("candidates")
        if not candidates or "content" not in candidates[0]:
            raise ValueError(f"Resposta sem conteúdo: {str(data)[:500]}")

        candidate = candidates[0]
        # MAX_TOKENS publicaria um post cortado no meio da frase; SAFETY,
        # RECITATION etc. trazem conteúdo incompleto. Repetir tende a dar o mesmo.
        finish_reason = candidate.get("finishReason", "STOP")
        if finish_reason != "STOP":
            raise ModelUnavailableError(f"Resposta incompleta (finishReason={finish_reason})")

        usage = data.get("usageMetadata", {})
        logger.info(
            "Gemini %s: %s tokens de entrada, %s de saída, %s de thinking",
            model,
            usage.get("promptTokenCount"),
            usage.get("candidatesTokenCount"),
            usage.get("thoughtsTokenCount"),
        )

        return "".join(
            part["text"]
            for part in candidate["content"].get("parts", [])
            if "text" in part and not part.get("thought")
        )
