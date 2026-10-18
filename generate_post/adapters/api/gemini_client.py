import requests

from generate_post.utils.retry_decorator import retry

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# Status que dizem que o modelo não atende esta chave (aposentado, sem acesso,
# payload incompatível). Repetir não adianta: o certo é ir para o próximo modelo.
_PERMANENT_STATUS = {400, 403, 404}


class ModelUnavailableError(RuntimeError):
    """O modelo não consegue atender a requisição; tente o próximo da lista."""


@retry(max_attempts=2, delay=5, giveup=(ModelUnavailableError, requests.Timeout))
def generate_content(
    session: requests.Session, api_key: str, model: str, body: dict, timeout: int
) -> dict:
    """Chama generateContent e devolve o primeiro candidate completo."""
    response = session.post(
        f"{_BASE_URL}/{model}:generateContent",
        headers={"x-goog-api-key": api_key},
        json=body,
        timeout=timeout,
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
        raise ValueError(f"Formato de resposta inválido: {str(data)[:500]}")

    candidate = candidates[0]
    # Nos modelos com thinking, o raciocínio também consome maxOutputTokens;
    # aceitar MAX_TOKENS publicaria um post cortado no meio da frase.
    if candidate.get("finishReason") == "MAX_TOKENS":
        raise ValueError("Resposta truncada (finishReason=MAX_TOKENS)")

    return candidate


def text_parts(candidate: dict) -> list[tuple[int, str]]:
    """Retorna (índice, texto) das partes de texto da resposta, sem pensamentos."""
    return [
        (i, part["text"])
        for i, part in enumerate(candidate["content"].get("parts", []))
        if "text" in part and not part.get("thought")
    ]
