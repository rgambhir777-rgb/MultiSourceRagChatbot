"""The agent's shared state, and the structured outputs of the judge model.

LangGraph passes one `AgentState` dict through the graph. Each node returns only the fields it
changes; LangGraph merges them in. Fields with a *reducer* (`Annotated[..., reducer]`) are
combined instead of replaced: `messages` appends new chat messages, `steps` appends progress.
"""

import operator
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from app.retrieval.retriever import RetrievedChunk

Route = Literal["retrieve", "direct"]


def add_steps(existing: list[str] | None, new: list[str] | None) -> list[str]:
    """Reducer for `steps`: append new progress lines; `None` starts a fresh list (each new
    question resets the progress of the previous one)."""
    if new is None:
        return []
    return [*(existing or []), *new]


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]  # the whole conversation
    question: str  # the user's latest message, as typed
    standalone_question: str  # the same, rewritten to make sense without the conversation
    route: Route
    search_query: str  # what we search for (may be rewritten)
    rewrites: int
    chunks: list[RetrievedChunk]  # retrieved candidates (best first)
    relevant: list[RetrievedChunk]  # the ones the judge kept
    answer: str
    regenerations: int
    grounded: bool | None  # True verified, False unsupported claims, None couldn't check
    unsupported_claims: list[str]
    retry_generation: bool  # set by the grounding check: write the answer once more
    steps: Annotated[list[str], add_steps]  # human-readable progress, e.g. "Searching..."
    # One record per finished turn (question, answer, sources, verification), kept for the
    # chat history view. Not part of `messages`, which are sent back to the model.
    turns: Annotated[list[dict[str, Any]], operator.add]


# --------------------------------------------- judge outputs (OpenAI structured outputs)


class RouteDecision(BaseModel):
    route: Route = Field(description="'retrieve' for information requests, 'direct' otherwise")
    standalone_question: str = Field(description="the latest message as a standalone question")


class GradeResult(BaseModel):
    relevant_passages: list[int] = Field(description="numbers of the relevant passages")


class RewrittenQuery(BaseModel):
    query: str = Field(description="a better search query")


class GroundingVerdict(BaseModel):
    grounded: bool = Field(description="true if every claim is supported by the sources")
    unsupported_claims: list[str] = Field(description="claims the sources don't support")
