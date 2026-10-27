"""Build the agent graph, and `RagAgent`, the object the API talks to.

The flow for one user message:
1. route: greeting/chit-chat → direct_answer → finalize. Otherwise → retrieve.
2. retrieve → grade (the judge keeps only relevant passages).
3. After grading:
   - relevant passages → generate → check_grounding
   - nothing relevant, rewrites left → rewrite the query → retrieve again
   - nothing relevant, no rewrites left → not_found → finalize
4. After check_grounding: unsupported claims and a retry left → generate again;
   otherwise → finalize (the answer is marked verified / unverified).
"""

import threading
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from typing import Any

import mlflow
import structlog
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.llm import estimate_cost_usd
from app.agent.nodes import WRITING_STEP, AgentDeps, AgentNodes
from app.agent.rag import Source, message_text, to_sources
from app.agent.state import AgentState

log = structlog.get_logger(__name__)


def build_graph(
    deps: AgentDeps, checkpointer: BaseCheckpointSaver | None = None
) -> CompiledStateGraph:
    nodes = AgentNodes(deps)
    graph = StateGraph(AgentState)
    for name in ("route", "retrieve", "grade", "rewrite", "generate", "check_grounding",
                 "not_found", "direct_answer", "finalize"):  # fmt: skip
        graph.add_node(name, getattr(nodes, name))

    graph.add_edge(START, "route")
    graph.add_conditional_edges("route", nodes.after_route, ["direct_answer", "retrieve"])
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges("grade", nodes.after_grade, ["generate", "rewrite", "not_found"])
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("generate", "check_grounding")
    graph.add_conditional_edges("check_grounding", nodes.after_grounding, ["generate", "finalize"])
    graph.add_edge("direct_answer", "finalize")
    graph.add_edge("not_found", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)


def new_turn(question: str) -> dict[str, Any]:
    """Input for one user message: append it to the conversation and reset per-turn fields
    (with memory, the previous turn's values would otherwise carry over)."""
    return {
        "question": question,
        "messages": [HumanMessage(question)],
        "rewrites": 0,
        "regenerations": 0,
        "chunks": [],
        "relevant": [],
        "unsupported_claims": [],
        "retry_generation": False,
        "grounded": None,
        "steps": None,  # reset the progress log
    }


# Nodes whose LLM output is the user-visible answer (their tokens are streamed).
ANSWER_NODES = {"generate", "direct_answer"}
_WRITING_ANNOUNCED = "_writing_announced"


@dataclass(frozen=True)
class ChatEvent:
    """One event of a streamed chat turn (sent to the browser as a Server-Sent Event).

    type: "status" | "token" | "answer_reset" | "sources" | "done"
    """

    type: str
    data: dict[str, Any]


@dataclass(frozen=True)
class AgentResult:
    answer: str
    sources: list[Source]
    grounded: bool | None
    route: str
    standalone_question: str
    rewrites: int
    regenerations: int
    steps: list[str]
    usage: dict[str, dict[str, Any]] = field(default_factory=dict)
    cost_usd: float = 0.0
    latency_ms: float = 0.0


class RagAgent:
    """Runs one conversation turn through the graph and summarises the outcome."""

    def __init__(self, deps: AgentDeps, checkpointer: BaseCheckpointSaver | None = None) -> None:
        self._settings = deps.settings
        self.graph = build_graph(deps, checkpointer)

    @mlflow.trace(name="agent_turn", span_type="AGENT")
    def ask(self, question: str, thread_id: str = "default") -> AgentResult:
        started = time.perf_counter()
        usage = UsageMetadataCallbackHandler()
        config = {"configurable": {"thread_id": thread_id}, "callbacks": [usage]}
        state = self.graph.invoke(new_turn(question.strip()), config)
        result = summarize(state, usage.usage_metadata, self._settings, started)
        _log_turn(result, streamed=False)
        return result

    def stream(
        self, question: str, thread_id: str, cancel: threading.Event | None = None
    ) -> Iterator[ChatEvent]:
        """Run one turn, yielding progress, answer tokens and finally sources + summary.

        Setting `cancel` (e.g. the browser disconnected) stops the agent at the next event,
        so no more tokens are spent on an answer nobody will read.
        """
        started = time.perf_counter()
        usage = UsageMetadataCallbackHandler()
        config = {"configurable": {"thread_id": thread_id}, "callbacks": [usage]}
        final: dict[str, Any] = {"question": question}
        with mlflow.start_span(name="agent_turn", span_type="AGENT") as span:
            span.set_inputs({"question": question, "thread_id": thread_id})
            stream = self.graph.stream(
                new_turn(question.strip()), config, stream_mode=["updates", "messages"]
            )
            for mode, payload in stream:
                if cancel is not None and cancel.is_set():
                    log.info("agent_turn_cancelled", thread_id=thread_id)
                    return
                yield from _events_for(mode, payload, final)
            result = summarize(final, usage.usage_metadata, self._settings, started)
            span.set_outputs({"answer": result.answer, "grounded": result.grounded})
        _log_turn(result, streamed=True)
        yield ChatEvent("sources", {"sources": [asdict(s) for s in result.sources]})
        yield ChatEvent("done", _done_data(result))


def _log_turn(result: "AgentResult", streamed: bool) -> None:
    """Log every turn's path, token usage and estimated cost (CLAUDE.md: never the API key)."""
    log.info(
        "agent_turn_done",
        streamed=streamed,
        route=result.route,
        rewrites=result.rewrites,
        regenerations=result.regenerations,
        grounded=result.grounded,
        tokens={model: u.get("total_tokens") for model, u in result.usage.items()},
        cost_usd=round(result.cost_usd, 6),
        latency_ms=result.latency_ms,
    )


def _events_for(mode: str, payload: Any, final: dict[str, Any]) -> Iterator[ChatEvent]:
    """Translate one LangGraph stream item into chat events, collecting the final state."""
    if mode == "messages":
        chunk, metadata = payload
        text = message_text(chunk.content) if hasattr(chunk, "content") else ""
        if text and metadata.get("langgraph_node") in ANSWER_NODES:
            # LangGraph reports a node's steps when it *finishes*; announce writing as soon
            # as the first word arrives instead, so the status matches what the user sees.
            if not final.get(_WRITING_ANNOUNCED):
                final[_WRITING_ANNOUNCED] = True
                yield ChatEvent("status", {"step": WRITING_STEP, "node": "generate"})
            yield ChatEvent("token", {"text": text})
        return
    for node, update in (payload or {}).items():
        if not update:
            continue
        final.update({k: v for k, v in update.items() if k not in ("steps", "messages", "turns")})
        for step in update.get("steps") or []:
            if step == WRITING_STEP and final.pop(_WRITING_ANNOUNCED, False):
                continue  # already announced when the first token arrived
            yield ChatEvent("status", {"step": step, "node": node})
        if node == "check_grounding" and update.get("retry_generation"):
            yield ChatEvent("answer_reset", {})


def _done_data(result: "AgentResult") -> dict[str, Any]:
    return {
        "answer": result.answer,
        "grounded": result.grounded,
        "route": result.route,
        "standalone_question": result.standalone_question,
        "rewrites": result.rewrites,
        "regenerations": result.regenerations,
        "cost_usd": round(result.cost_usd, 6),
        "latency_ms": result.latency_ms,
    }


def summarize(
    state: AgentState, usage: dict[str, dict[str, Any]], settings: Any, started: float
) -> AgentResult:
    answer = state.get("answer", "")
    return AgentResult(
        answer=answer,
        sources=to_sources(state.get("relevant", []), answer),
        grounded=state.get("grounded"),
        route=state.get("route", "retrieve"),
        standalone_question=state.get("standalone_question", state.get("question", "")),
        rewrites=state.get("rewrites", 0),
        regenerations=state.get("regenerations", 0),
        steps=state.get("steps", []),
        usage=usage,
        cost_usd=estimate_cost_usd(settings, usage),
        latency_ms=round((time.perf_counter() - started) * 1000, 1),
    )
