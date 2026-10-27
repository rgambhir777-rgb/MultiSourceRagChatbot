"""Conversation memory survives a restart, using the REAL Postgres checkpointer.

The judge and generator are fakes, so this costs nothing. "Restart" = a brand-new Services
and agent (new pools, new graph) pointed at the same database.
Run with:  pytest -m integration
"""

import uuid
from collections.abc import Iterator

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from psycopg import sql

from app.agent.graph import RagAgent
from app.agent.nodes import AgentDeps
from app.config import Settings
from app.services import Services
from tests.unit.test_agent import FakeRetriever, ScriptedJudge

pytestmark = pytest.mark.integration


@pytest.fixture
def settings() -> Iterator[Settings]:
    name = f"test_{uuid.uuid4().hex[:10]}"
    settings = Settings(postgres_schema=name, tracing_enabled=False)
    yield settings
    services = Services(settings)
    with services.pool().connection() as conn:
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name)))
    services.close()


def _agent(services: Services, judge: ScriptedJudge, reply: str) -> RagAgent:
    generator = GenericFakeChatModel(messages=iter([AIMessage(reply)]))
    deps = AgentDeps(services.settings, FakeRetriever(), judge, generator)  # type: ignore[arg-type]
    return RagAgent(deps, services.checkpointer())


def test_memory_survives_a_restart(settings: Settings) -> None:
    thread = str(uuid.uuid4())

    before = Services(settings)
    list(_agent(before, ScriptedJudge(), "E-114 means low power [1].").stream("E-114?", thread))
    before.close()  # the "server" stops: all pools closed

    after = Services(settings)  # the "server" starts again
    judge = ScriptedJudge()
    events = list(
        _agent(after, judge, "Install the C-wire adapter [1].").stream("How do I fix it?", thread)
    )
    assert events[-1].data["answer"] == "Install the C-wire adapter [1]."
    assert "User: E-114?" in judge.histories[0], "the router saw the earlier turn"
    assert "Assistant: E-114 means low power [1]." in judge.histories[0]

    saved = after.checkpointer().get_tuple({"configurable": {"thread_id": thread}})
    turns = saved.checkpoint["channel_values"]["turns"]
    assert [t["question"] for t in turns] == ["E-114?", "How do I fix it?"]
    after.checkpointer().delete_thread(thread)
    assert after.checkpointer().get_tuple({"configurable": {"thread_id": thread}}) is None
    after.close()


def test_session_store_titles_and_counts(settings: Settings) -> None:
    services = Services(settings)
    sessions = services.sessions()
    session = sessions.create()
    sessions.record_turn(
        session.id, "  What   does error E-114 mean on my thermostat, and why does it happen?  "
    )
    sessions.record_turn(session.id, "And how do I fix it?")
    saved = sessions.get(session.id)
    assert saved is not None and saved.turn_count == 2
    assert saved.title == "What does error E-114 mean on my thermostat, and why does it"
    assert sessions.delete(session.id) and sessions.get(session.id) is None
    services.close()
