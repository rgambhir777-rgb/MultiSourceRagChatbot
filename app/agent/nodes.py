"""The agent's nodes (steps) and the routing functions between them.

Each node is a plain function: it reads the state and returns ONLY the fields it changes.
Routing functions look at the state and return the name of the next node. Loop limits come
from Settings (MAX_QUERY_REWRITES, MAX_REGENERATIONS), so the agent can never loop forever.
"""

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.agent.judge import Judge
from app.agent.prompts import DIRECT_SYSTEM_PROMPT, NOT_FOUND_ANSWER, REGENERATE_INSTRUCTION
from app.agent.rag import build_messages, fit_to_budget, message_text, to_sources
from app.agent.state import AgentState
from app.config import Settings
from app.retrieval.retriever import Retriever

log = structlog.get_logger(__name__)

WRITING_STEP = "Writing the answer"


@dataclass(frozen=True)
class AgentDeps:
    """Everything the nodes need; built once and shared by every conversation."""

    settings: Settings
    retriever: Retriever
    judge: Judge
    generator: BaseChatModel


class AgentNodes:
    def __init__(self, deps: AgentDeps) -> None:
        self.d = deps

    # ------------------------------------------------------------------------ nodes

    def route(self, state: AgentState) -> dict[str, Any]:
        history = format_history(state.get("messages", [])[:-1], self.d.settings.history_max_turns)
        decision = self.d.judge.route(state["question"], history)
        standalone = decision.standalone_question.strip() or state["question"]
        step = "Answering directly" if decision.route == "direct" else "Searching your documents"
        return {
            "route": decision.route,
            "standalone_question": standalone,
            "search_query": standalone,
            "steps": [step],
        }

    def retrieve(self, state: AgentState) -> dict[str, Any]:
        chunks = self.d.retriever.retrieve(state["search_query"])
        return {"chunks": chunks, "steps": [f"Found {len(chunks)} candidate passages"]}

    def grade(self, state: AgentState) -> dict[str, Any]:
        chunks = state.get("chunks", [])
        keep = self.d.judge.grade(state["standalone_question"], chunks)
        relevant = [chunks[n - 1] for n in keep]
        return {"relevant": relevant, "steps": [f"{len(relevant)} passages are relevant"]}

    def rewrite(self, state: AgentState) -> dict[str, Any]:
        query = self.d.judge.rewrite(state["standalone_question"], state["search_query"])
        return {
            "search_query": query,
            "rewrites": state.get("rewrites", 0) + 1,
            "steps": [f"Nothing relevant; searching again for: {query}"],
        }

    def generate(self, state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        question = state["standalone_question"]
        chunks = fit_to_budget(question, state["relevant"], self.d.settings)
        messages: list[BaseMessage] = build_messages(question, chunks)
        if state.get("unsupported_claims"):  # second attempt after a failed grounding check
            claims = "\n".join(f"- {c}" for c in state["unsupported_claims"])
            messages.append(HumanMessage(REGENERATE_INSTRUCTION.format(claims=claims)))
        reply = self.d.generator.invoke(messages, config)
        return {"answer": message_text(reply.content).strip(), "relevant": chunks,
                "steps": [WRITING_STEP]}  # fmt: skip

    def check_grounding(self, state: AgentState) -> dict[str, Any]:
        verdict = self.d.judge.check_grounding(state["answer"], state["relevant"])
        if verdict is None:
            return {"grounded": None, "unsupported_claims": [], "retry_generation": False,
                    "steps": ["Could not verify the answer"]}  # fmt: skip
        if verdict.grounded:
            return {"grounded": True, "unsupported_claims": [], "retry_generation": False,
                    "steps": ["Answer verified against the sources"]}  # fmt: skip
        used = state.get("regenerations", 0)
        retry = used < self.d.settings.max_regenerations
        return {
            "grounded": False,
            "unsupported_claims": verdict.unsupported_claims,
            "retry_generation": retry,
            "regenerations": used + 1 if retry else used,
            "steps": ["Some claims are unsupported; rewriting the answer" if retry
                      else "Some claims could not be verified"],
        }  # fmt: skip

    def not_found(self, state: AgentState) -> dict[str, Any]:
        return {"answer": NOT_FOUND_ANSWER, "relevant": [], "grounded": True,
                "steps": ["No relevant information found"]}  # fmt: skip

    def direct_answer(self, state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        history = state.get("messages", [])[-2 * self.d.settings.history_max_turns :]
        reply = self.d.generator.invoke([SystemMessage(DIRECT_SYSTEM_PROMPT), *history], config)
        return {"answer": message_text(reply.content).strip(), "relevant": [], "grounded": None}

    def finalize(self, state: AgentState) -> dict[str, Any]:
        """Add the answer to the conversation and record the turn for the history view."""
        answer = state["answer"]
        turn = {
            "question": state["question"],
            "answer": answer,
            "sources": [asdict(s) for s in to_sources(state.get("relevant", []), answer)],
            "grounded": state.get("grounded"),
            "route": state.get("route", "retrieve"),
        }
        return {"messages": [AIMessage(answer)], "turns": [turn]}

    # --------------------------------------------------------------------- routing

    def after_route(self, state: AgentState) -> str:
        return "direct_answer" if state["route"] == "direct" else "retrieve"

    def after_grade(self, state: AgentState) -> str:
        if state.get("relevant"):
            return "generate"
        if state.get("rewrites", 0) < self.d.settings.max_query_rewrites:
            return "rewrite"
        return "not_found"

    def after_grounding(self, state: AgentState) -> str:
        return "generate" if state.get("retry_generation") else "finalize"


def format_history(messages: Sequence[AnyMessage], max_turns: int) -> str:
    """The last few turns as plain text, for the router to resolve "it"/"that"."""
    lines = []
    for message in list(messages)[-2 * max_turns :]:
        speaker = "User" if isinstance(message, HumanMessage) else "Assistant"
        lines.append(f"{speaker}: {message_text(message.content)[:500]}")
    return "\n".join(lines)
