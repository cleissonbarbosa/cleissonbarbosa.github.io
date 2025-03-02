import time
from functools import wraps

from generate_post.config.constants import MAX_RETRIES, RETRY_DELAY


def retry(max_attempts=MAX_RETRIES, delay=RETRY_DELAY):
    """Decorator para implementar retry em funções"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            last_exception = None

            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    last_exception = e
                    wait_time = delay * (
                        2 ** (attempts - 1)
                    )  # Exponential backoff  # noqa
                    print(
                        f"Tentativa {attempts}/{max_attempts} falhou: {str(e)}. Aguardando {wait_time}s..."  # noqa
                    )
                    time.sleep(wait_time)

            print(
                f"Todas as {max_attempts} tentativas falharam. Último erro: {last_exception}"  # noqa
            )
            raise last_exception

        return wrapper

    return decorator
