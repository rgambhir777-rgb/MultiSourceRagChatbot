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

import time
from dataclasses import dataclass, field
from typing import Any

import mlflow
import structlog
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.llm import estimate_cost_usd
from app.agent.nodes import AgentDeps, AgentNodes
from app.agent.rag import Source, to_sources
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
        log.info(
            "agent_turn_done",
            route=result.route,
            rewrites=result.rewrites,
            regenerations=result.regenerations,
            grounded=result.grounded,
            cost_usd=round(result.cost_usd, 6),
            latency_ms=result.latency_ms,
        )
        return result


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
