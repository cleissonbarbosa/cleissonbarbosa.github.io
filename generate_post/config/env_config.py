import os


class EnvConfig:
    """Gerencia as configurações de ambiente do aplicativo"""

    @staticmethod
    def get_gemini_api_key():
        """Retorna a chave da API Gemini"""
        return os.getenv("GEMINI_API_KEY")

    @staticmethod
    def get_cf_api_token():
        """Retorna o token da API Cloudflare"""
        return os.getenv("CF_AI_API_KEY")

    @staticmethod
    def get_cf_account_id():
        """Retorna o ID da conta Cloudflare"""
        return os.getenv("CF_ACCOUNT_ID")

    @staticmethod
    def get_github_output():
        """Retorna o caminho do arquivo de output do GitHub Actions"""
        return os.getenv("GITHUB_OUTPUT")
