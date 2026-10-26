"""The single place that creates OpenAI clients (see CLAUDE.md "OpenAI usage rules").

Keeping client creation here means the API key, timeouts and retry policy are configured once,
and every other module asks this one for a client instead of building its own.
"""

from openai import AsyncOpenAI

from app.config import Settings


def make_openai_client(settings: Settings) -> AsyncOpenAI | None:
    """Return an async OpenAI client, or None when no API key is configured.

    Returning None (instead of failing) lets the API still start, so `/ready` can report
    clearly that the key is missing.
    """
    if settings.openai_api_key is None:
        return None
    return AsyncOpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        base_url=settings.openai_base_url,  # None means the official api.openai.com
        timeout=settings.llm_request_timeout_s,
        max_retries=settings.llm_max_retries,
    )
