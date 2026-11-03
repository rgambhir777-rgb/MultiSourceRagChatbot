"""The single place that creates OpenAI clients (see CLAUDE.md "OpenAI usage rules").

Two model roles:
- "generator" (gpt-6.1-sol): writes the final answer.
- "judge" (gpt-6-luna): small, fast, cheap decisions (route, grade, grounding check).

Every client gets its model, reasoning effort, output-token cap, timeout and retry policy from
Settings, so nothing about cost or latency is decided anywhere else in the code.
"""

from typing import Any, Literal

from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI

from app.config import Settings

ModelRole = Literal["generator", "judge"]


def make_openai_client(settings: Settings) -> AsyncOpenAI | None:
    """Return a raw async OpenAI client (used by /ready), or None when no key is configured.

    Returning None (instead of failing) lets the API still start, so `/ready` can report
    clearly that the key is missing.
    """
    if settings.openai_api_key is None:
        return None
    return AsyncOpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        base_url=settings.openai_base_url,  # always explicit (see OPENAI_DEFAULT_BASE_URL)
        timeout=settings.llm_request_timeout_s,
        max_retries=settings.llm_max_retries,
    )


class MissingAPIKeyError(RuntimeError):
    """OPENAI_API_KEY is not set, so no answer can be generated."""


def make_chat_model(settings: Settings, role: ModelRole, *, streaming: bool = False) -> ChatOpenAI:
    """A LangChain chat model for one role, with every cost/latency knob from Settings."""
    if settings.openai_api_key is None:
        raise MissingAPIKeyError("OPENAI_API_KEY is not set; add it to .env")
    if role == "generator":
        model, effort = settings.llm_generator_model, settings.llm_generator_reasoning_effort
    else:
        model, effort = settings.llm_judge_model, settings.llm_judge_reasoning_effort
    return ChatOpenAI(
        model=model,
        reasoning_effort=effort,
        max_tokens=settings.llm_max_output_tokens,  # hard cap on output (and so on cost)
        timeout=settings.llm_request_timeout_s,
        max_retries=settings.llm_max_retries,  # retries 429/5xx with exponential backoff
        api_key=settings.openai_api_key.get_secret_value(),
        base_url=settings.openai_base_url,
        streaming=streaming,
        stream_usage=True,  # report token usage even when streaming
    )


def estimate_cost_usd(settings: Settings, usage_by_model: dict[str, dict[str, Any]]) -> float:
    """Estimated cost of the given token usage, using the per-model prices in Settings.

    `usage_by_model` is what LangChain's UsageMetadataCallbackHandler collects:
    {"gpt-6.1-sol": {"input_tokens": 1200, "output_tokens": 150, ...}, ...}.
    """
    prices = {
        settings.llm_generator_model: (
            settings.llm_generator_price_in,
            settings.llm_generator_price_out,
        ),
        settings.llm_judge_model: (settings.llm_judge_price_in, settings.llm_judge_price_out),
    }
    total = 0.0
    for model, usage in usage_by_model.items():
        price_in, price_out = prices.get(_base_model(model, prices), (0.0, 0.0))
        total += usage.get("input_tokens", 0) * price_in / 1_000_000
        total += usage.get("output_tokens", 0) * price_out / 1_000_000
    return total


def _base_model(model: str, prices: dict[str, tuple[float, float]]) -> str:
    """OpenAI may report a dated variant ("gpt-6-luna-2026-09-01"); match it to our model."""
    return next((name for name in prices if model == name or model.startswith(f"{name}-")), model)
