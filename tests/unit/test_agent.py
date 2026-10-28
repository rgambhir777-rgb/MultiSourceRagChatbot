"""Tests for the LangGraph agent: every path through the graph, with a scripted judge and a
fake generator (deterministic, no network, no cost)."""

from collections.abc import Sequence

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.graph import RagAgent
from app.agent.judge import LLMJudge
from app.agent.nodes import AgentDeps, format_history
from app.agent.prompts import NOT_FOUND_ANSWER
from app.agent.state import GroundingVerdict, RouteDecision
from app.config import Settings
from app.retrieval.retriever import RetrievedChunk


def _chunk(i: int) -> RetrievedChunk:
    return RetrievedChunk(
        id=f"p{i}", doc_id="d", source="guide.md", section="Setup", page=None, chunk_index=i,
        text=f"Fact {i}.", search_score=1.0,
    )  # fmt: skip


class FakeRetriever:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def retrieve(self, question: str) -> list[RetrievedChunk]:
        self.queries.append(question)
        return [_chunk(0), _chunk(1)]


GROUNDED = GroundingVerdict(grounded=True, unsupported_claims=[])
NOT_GROUNDED = GroundingVerdict(grounded=False, unsupported_claims=["It is purple."])


class ScriptedJudge:
    """Returns pre-programmed decisions, one per call."""

    def __init__(
        self,
        route: str = "retrieve",
        grades: Sequence[list[int]] = ([1],),
        groundings: Sequence[GroundingVerdict | None] = (GROUNDED,),
    ) -> None:
        self._route, self._grades, self._groundings = route, list(grades), list(groundings)
        self.histories: list[str] = []

    def route(self, question: str, history: str) -> RouteDecision:
        self.histories.append(history)
        return RouteDecision(route=self._route, standalone_question=f"{question} (standalone)")

    def grade(self, question: str, chunks: Sequence[RetrievedChunk]) -> list[int]:
        return self._grades.pop(0) if len(self._grades) > 1 else self._grades[0]

    def rewrite(self, question: str, failed_query: str) -> str:
        return f"rewritten {failed_query}"

    def check_grounding(self, answer: str, chunks: Sequence[RetrievedChunk]):  # noqa: ANN201
        return self._groundings.pop(0) if len(self._groundings) > 1 else self._groundings[0]


class RecordingModel(GenericFakeChatModel):
    """Fake chat model that also remembers the messages it was given."""

    calls: list = []  # noqa: RUF012 - pydantic field, replaced per instance below

    def _generate(self, messages, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
        self.calls.append(messages)
        return super()._generate(messages, *args, **kwargs)


def _generator(*replies: str) -> RecordingModel:
    model = RecordingModel(messages=iter([AIMessage(r) for r in replies]))
    model.calls = []
    return model


def _agent(settings: Settings, judge: ScriptedJudge, generator, retriever=None, saver=None):  # noqa: ANN001, ANN202
    retriever = retriever or FakeRetriever()
    deps = AgentDeps(settings, retriever, judge, generator)  # type: ignore[arg-type]
    return RagAgent(deps, saver), retriever


# ------------------------------------------------------------------------- paths


def test_direct_path_skips_retrieval(settings: Settings) -> None:
    agent, retriever = _agent(settings, ScriptedJudge(route="direct"), _generator("Hello!"))
    result = agent.ask("hi")
    assert (result.route, result.answer, result.sources) == ("direct", "Hello!", [])
    assert retriever.queries == []
    assert result.grounded is None


def test_normal_rag_path_cites_and_verifies(settings: Settings) -> None:
    agent, retriever = _agent(settings, ScriptedJudge(grades=[[2]]), _generator("Answer [1]."))
    result = agent.ask("What is fact 1?")
    assert result.answer == "Answer [1]."
    assert retriever.queries == ["What is fact 1? (standalone)"]
    assert [(s.text, s.cited) for s in result.sources] == [("Fact 1.", True)]  # only graded chunk
    assert result.grounded is True
    assert result.steps[-1] == "Answer verified against the sources"


def test_rewrite_then_answer(settings: Settings) -> None:
    judge = ScriptedJudge(grades=[[], [1]])
    agent, retriever = _agent(settings, judge, _generator("Found it [1]."))
    result = agent.ask("obscure question")
    assert result.rewrites == 1
    assert retriever.queries == ["obscure question (standalone)",
                                 "rewritten obscure question (standalone)"]  # fmt: skip
    assert result.answer == "Found it [1]."


def test_gives_up_honestly_after_max_rewrites(settings: Settings) -> None:
    generator = _generator("should never be called")
    agent, retriever = _agent(settings, ScriptedJudge(grades=[[]]), generator)
    result = agent.ask("capital of France?")
    assert result.answer == NOT_FOUND_ANSWER
    assert result.rewrites == settings.max_query_rewrites
    assert len(retriever.queries) == settings.max_query_rewrites + 1
    assert generator.calls == [], "no expensive generation when nothing was found"


def test_unsupported_claims_trigger_one_regeneration(settings: Settings) -> None:
    generator = _generator("It is purple [1].", "It is fact 0 [1].")
    agent, _ = _agent(settings, ScriptedJudge(groundings=[NOT_GROUNDED, GROUNDED]), generator)
    result = agent.ask("What colour is it?")
    assert result.answer == "It is fact 0 [1]."
    assert result.regenerations == 1 and result.grounded is True
    assert "It is purple." in generator.calls[1][-1].content  # told what was unsupported


def test_regeneration_is_bounded_then_marked_unverified(settings: Settings) -> None:
    generator = _generator("Purple [1].", "Still purple [1].", "never used")
    agent, _ = _agent(settings, ScriptedJudge(groundings=[NOT_GROUNDED]), generator)
    result = agent.ask("What colour is it?")
    assert result.regenerations == settings.max_regenerations
    assert len(generator.calls) == settings.max_regenerations + 1
    assert result.grounded is False


def test_unverifiable_answer_is_not_marked_verified(settings: Settings) -> None:
    agent, _ = _agent(settings, ScriptedJudge(groundings=[None]), _generator("Answer [1]."))
    assert agent.ask("q").grounded is None


# ------------------------------------------------------------------------ memory


def test_conversation_memory_and_per_turn_reset(settings: Settings) -> None:
    judge = ScriptedJudge(grades=[[], [1]])  # first turn needs a rewrite, second doesn't
    agent, _ = _agent(
        settings, judge, _generator("First [1].", "Second [1]."), saver=InMemorySaver()
    )
    first = agent.ask("first question", thread_id="t1")
    second = agent.ask("and the price of it?", thread_id="t1")
    assert first.rewrites == 1 and second.rewrites == 0, "counters reset every turn"
    assert "User: first question" in judge.histories[1]
    assert "Assistant: First [1]." in judge.histories[1]
    assert second.steps[0] == "Searching your documents", "progress log reset every turn"
    state = agent.graph.get_state({"configurable": {"thread_id": "t1"}}).values
    assert [m.content for m in state["messages"]] == [
        "first question", "First [1].", "and the price of it?", "Second [1].",
    ]  # fmt: skip


def test_format_history_keeps_recent_turns() -> None:
    messages = [HumanMessage("q1"), AIMessage("a1"), HumanMessage("q2"), AIMessage("a2")]
    assert format_history(messages, max_turns=1) == "User: q2\nAssistant: a2"


# --------------------------------------------------------------- judge fallbacks


class BrokenModel:
    def with_structured_output(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        raise ConnectionError("openai down")


def test_judge_falls_back_safely_when_the_model_fails() -> None:
    judge = LLMJudge(BrokenModel())  # type: ignore[arg-type]
    assert judge.route("hi", "") == RouteDecision(route="retrieve", standalone_question="hi")
    assert judge.grade("q", [_chunk(0), _chunk(1)]) == [1, 2], "keep everything"
    assert judge.rewrite("question", "query") == "question"
    assert judge.check_grounding("answer", [_chunk(0)]) is None, "never claim 'verified'"


@pytest.mark.parametrize("numbers", [[0, 3, 99], [-1]])
def test_judge_ignores_out_of_range_passage_numbers(numbers: list[int]) -> None:
    from app.agent.state import GradeResult

    class Model:
        def with_structured_output(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
            return self

        def invoke(self, messages):  # noqa: ANN001, ANN201
            return GradeResult(relevant_passages=numbers)

    assert LLMJudge(Model()).grade("q", [_chunk(0), _chunk(1), _chunk(2)]) == [
        n for n in numbers if 1 <= n <= 3
    ]  # type: ignore[arg-type]
