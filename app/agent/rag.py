"""Baseline (non-agentic) RAG: retrieve → prompt → generate an answer with citations.

This is the simple pipeline that Session 7's agent improves on (it adds routing, relevance
grading, query rewriting and a grounding check). It stays useful as a comparison baseline.
"""

import re
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import mlflow
import structlog
import tiktoken
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.agent.llm import estimate_cost_usd
from app.agent.prompts import ANSWER_SYSTEM_PROMPT, NOT_FOUND_ANSWER, answer_user_prompt
from app.config import Settings
from app.retrieval.retriever import RetrievedChunk, Retriever

log = structlog.get_logger(__name__)

_CITATION = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True)
class Source:
    """One source shown to the model, numbered as in the answer's [n] citations."""

    number: int
    source: str
    location: str
    text: str
    cited: bool


@dataclass(frozen=True)
class Answer:
    text: str
    sources: list[Source]
    usage: dict[str, dict[str, Any]] = field(default_factory=dict)  # tokens per model
    cost_usd: float = 0.0
    latency_ms: float = 0.0


def cited_numbers(text: str, source_count: int) -> set[int]:
    """Source numbers the answer actually cites (ignoring numbers that don't exist)."""
    return {n for n in map(int, _CITATION.findall(text)) if 1 <= n <= source_count}


def fit_to_budget(
    question: str, chunks: Sequence[RetrievedChunk], settings: Settings
) -> list[RetrievedChunk]:
    """Keep the best chunks that fit PROMPT_MAX_TOKENS (chunks arrive best-first, so the
    least relevant ones are dropped first). Bounds the cost of every request."""
    encoding = _encoding(settings.tokenizer_encoding)
    kept = list(chunks)
    while kept:
        prompt = ANSWER_SYSTEM_PROMPT + answer_user_prompt(question, kept)
        if len(encoding.encode(prompt, disallowed_special=())) <= settings.prompt_max_tokens:
            break
        kept.pop()
    return kept


def build_messages(question: str, chunks: Sequence[RetrievedChunk]) -> list[BaseMessage]:
    return [
        SystemMessage(ANSWER_SYSTEM_PROMPT),
        HumanMessage(answer_user_prompt(question, chunks)),
    ]


def message_text(content: str | list[Any]) -> str:
    """Model replies are usually a string; some APIs return a list of content parts."""
    if isinstance(content, str):
        return content
    return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)


def to_sources(chunks: Sequence[RetrievedChunk], answer: str) -> list[Source]:
    cited = cited_numbers(answer, len(chunks))
    return [
        Source(number=i, source=c.source, location=c.citation, text=c.text, cited=i in cited)
        for i, c in enumerate(chunks, start=1)
    ]


class SimpleRag:
    """Retrieve, then answer with the generator model. One LLM call per question."""

    def __init__(self, settings: Settings, retriever: Retriever, llm: BaseChatModel) -> None:
        self._settings = settings
        self._retriever = retriever
        self._llm = llm

    @mlflow.trace(name="simple_rag", span_type="CHAIN")
    def answer(self, question: str) -> Answer:
        started = time.perf_counter()
        with mlflow.start_span(name="retrieve", span_type="RETRIEVER") as span:
            span.set_inputs({"question": question})
            chunks = fit_to_budget(question, self._retriever.retrieve(question), self._settings)
            span.set_outputs([c.citation for c in chunks])
        if not chunks:  # nothing to ground an answer in: don't spend money on an LLM call
            return Answer(NOT_FOUND_ANSWER, [], latency_ms=_ms_since(started))

        usage = UsageMetadataCallbackHandler()
        reply = self._llm.invoke(build_messages(question, chunks), config={"callbacks": [usage]})
        text = message_text(reply.content).strip()
        cost = estimate_cost_usd(self._settings, usage.usage_metadata)
        answer = Answer(
            text, to_sources(chunks, text), usage.usage_metadata, cost, _ms_since(started)
        )
        log.info(
            "answer_generated",
            sources=len(chunks),
            cited=sum(s.cited for s in answer.sources),
            tokens={m: u.get("total_tokens") for m, u in usage.usage_metadata.items()},
            cost_usd=round(cost, 6),
            latency_ms=answer.latency_ms,
        )
        return answer


def _ms_since(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


@lru_cache(maxsize=4)
def _encoding(name: str) -> tiktoken.Encoding:
    return tiktoken.get_encoding(name)
