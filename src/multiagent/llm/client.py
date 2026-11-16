"""Cached Mistral client + retry with backoff on transient errors."""
import time

try:
    from mistralai import Mistral  # SDK 1.x
except ImportError:  # SDK >= 3 renamed the import path, kept the call surface
    from mistralai.client import Mistral

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 4

_client: Mistral | None = None


def get_client(api_key: str) -> Mistral:
    global _client
    if _client is None:
        _client = Mistral(api_key=api_key)
    return _client


def complete_with_retry(client: Mistral, **kwargs):
    """chat.complete with backoff for rate limits and transient server errors."""
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return client.chat.complete(**kwargs)
        except Exception as e:  # SDK error classes vary per version; use status code
            status = getattr(e, "status_code", None)
            if status not in RETRYABLE_STATUS or attempt == MAX_RETRIES - 1:
                raise
            last_error = e
            time.sleep(min(1.5 * 2**attempt, 20))
    raise last_error  # pragma: no cover - loop always returns or raises
