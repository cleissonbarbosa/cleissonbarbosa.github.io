import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class EnvConfig:
    """Configurações de ambiente carregadas uma única vez no startup."""

    gemini_api_key: Optional[str]
    cf_api_token: Optional[str]
    cf_account_id: Optional[str]
    github_output: Optional[str]

    @classmethod
    def from_env(cls) -> "EnvConfig":
        """Carrega todas as variáveis de ambiente de uma vez."""
        return cls(
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            cf_api_token=os.getenv("CF_AI_API_KEY"),
            cf_account_id=os.getenv("CF_ACCOUNT_ID"),
            github_output=os.getenv("GITHUB_OUTPUT"),
        )

    def validate_gemini(self) -> None:
        """Valida se as credenciais do Gemini estão presentes."""
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY não definida")

    def validate_cloudflare(self) -> None:
        """Valida se as credenciais do Cloudflare estão presentes."""
        if not self.cf_api_token or not self.cf_account_id:
            raise ValueError("CF_AI_API_KEY e CF_ACCOUNT_ID devem estar definidas")
