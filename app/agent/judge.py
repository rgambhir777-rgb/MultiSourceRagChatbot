"""The judge: small, structured decisions made by the cheap model (gpt-6-luna).

Each decision uses OpenAI *structured outputs*: the model must answer with JSON matching a
Pydantic schema, so the code gets e.g. `GradeResult(relevant_passages=[1, 3])` instead of
free text to parse.

The agent depends on the `Judge` protocol, not on OpenAI: tests pass a scripted fake.
Every real decision has a SAFE FALLBACK if the model call fails, so a hiccup never crashes a
chat. The fallbacks lean towards caution: search instead of chatting, keep chunks instead of
dropping them, and mark the answer "couldn't verify" instead of "verified".
"""

from collections.abc import Sequence
from typing import Protocol, TypeVar

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.agent.prompts import (
    GRADE_SYSTEM_PROMPT,
    GROUNDING_SYSTEM_PROMPT,
    REWRITE_SYSTEM_PROMPT,
    ROUTE_SYSTEM_PROMPT,
    grade_user_prompt,
    grounding_user_prompt,
    rewrite_user_prompt,
    route_user_prompt,
)
from app.agent.state import GradeResult, GroundingVerdict, RewrittenQuery, RouteDecision
from app.retrieval.retriever import RetrievedChunk

log = structlog.get_logger(__name__)
M = TypeVar("M", bound=BaseModel)


class Judge(Protocol):
    def route(self, question: str, history: str) -> RouteDecision: ...

    def grade(self, question: str, chunks: Sequence[RetrievedChunk]) -> list[int]: ...

    def rewrite(self, question: str, failed_query: str) -> str: ...

    def check_grounding(
        self, answer: str, chunks: Sequence[RetrievedChunk]
    ) -> GroundingVerdict | None: ...


class LLMJudge:
    """The real judge, backed by a chat model with structured outputs."""

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model

    def route(self, question: str, history: str) -> RouteDecision:
        decision = self._ask(
            RouteDecision, ROUTE_SYSTEM_PROMPT, route_user_prompt(question, history)
        )
        if decision is None or not decision.standalone_question.strip():
            return RouteDecision(route="retrieve", standalone_question=question)
        return decision

    def grade(self, question: str, chunks: Sequence[RetrievedChunk]) -> list[int]:
        """1-based numbers of the relevant chunks."""
        if not chunks:
            return []
        result = self._ask(GradeResult, GRADE_SYSTEM_PROMPT, grade_user_prompt(question, chunks))
        if result is None:
            return list(range(1, len(chunks) + 1))  # can't judge: keep everything
        return sorted({n for n in result.relevant_passages if 1 <= n <= len(chunks)})

    def rewrite(self, question: str, failed_query: str) -> str:
        result = self._ask(
            RewrittenQuery, REWRITE_SYSTEM_PROMPT, rewrite_user_prompt(question, failed_query)
        )
        return result.query.strip() if result and result.query.strip() else question

    def check_grounding(
        self, answer: str, chunks: Sequence[RetrievedChunk]
    ) -> GroundingVerdict | None:
        """None means "couldn't check": the answer is then shown as unverified."""
        return self._ask(
            GroundingVerdict, GROUNDING_SYSTEM_PROMPT, grounding_user_prompt(answer, chunks)
        )

    def _ask(self, schema: type[M], system: str, user: str) -> M | None:
        try:
            structured = self._model.with_structured_output(schema, strict=True)
            result = structured.invoke([SystemMessage(system), HumanMessage(user)])
        except Exception as exc:  # network, rate limit, malformed output: use the fallback
            log.warning("judge_failed", decision=schema.__name__, error=type(exc).__name__)
            return None
        return result if isinstance(result, schema) else None
