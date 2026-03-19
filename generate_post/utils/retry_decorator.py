import logging
import time
from functools import wraps

from generate_post.config.constants import MAX_RETRIES, RETRY_DELAY

logger = logging.getLogger(__name__)


def retry(max_attempts=MAX_RETRIES, delay=RETRY_DELAY):
    """Decorator para implementar retry com exponential backoff."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts:
                        wait_time = delay * (2 ** (attempt - 1))
                        logger.warning(
                            "Tentativa %d/%d de %s falhou: %s. " "Aguardando %ds...",
                            attempt,
                            max_attempts,
                            func.__qualname__,
                            e,
                            wait_time,
                        )
                        time.sleep(wait_time)

            logger.error(
                "Todas as %d tentativas de %s falharam.",
                max_attempts,
                func.__qualname__,
            )
            raise last_exception  # type: ignore[misc]

        return wrapper

    return decorator
