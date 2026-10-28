"""Tests for streamed chat turns: RagAgent.stream events, and the /api/chat + /api/sessions
endpoints (fake judge, fake streaming model, in-memory checkpointer: no network, no cost)."""

import json
import threading
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.graph import ChatEvent, RagAgent
from app.agent.nodes import WRITING_STEP, AgentDeps
from app.config import Settings
from app.db.sessions import SessionRecord
from app.main import create_app
from tests.unit.test_agent import GROUNDED, NOT_GROUNDED, FakeRetriever, ScriptedJudge


def _agent(settings: Settings, judge: ScriptedJudge, *replies: str) -> RagAgent:
    generator = GenericFakeChatModel(messages=iter([AIMessage(r) for r in replies]))
    deps = AgentDeps(settings, FakeRetriever(), judge, generator)  # type: ignore[arg-type]
    return RagAgent(deps, InMemorySaver())


def _types(events: list[ChatEvent]) -> list[str]:
    return [e.type for e in events]


# ----------------------------------------------------------------- RagAgent.stream


def test_stream_sends_status_then_tokens_then_sources_and_done(settings: Settings) -> None:
    agent = _agent(settings, ScriptedJudge(), "Error E-207 means Wi-Fi failed [1].")
    events = list(agent.stream("What is E-207?", "t1"))
    tokens = [e.data["text"] for e in events if e.type == "token"]
    assert len(tokens) > 3, "the answer arrives word by word"
    assert "".join(tokens) == "Error E-207 means Wi-Fi failed [1]."
    first_token = _types(events).index("token")
    assert events[first_token - 1].data["step"] == WRITING_STEP, "announced before the words"
    assert [e.data["step"] for e in events if e.type == "status"].count(WRITING_STEP) == 1
    assert _types(events)[-2:] == ["sources", "done"]
    done = events[-1].data
    assert done["answer"] == "Error E-207 means Wi-Fi failed [1]." and done["grounded"] is True
    assert events[-2].data["sources"][0]["cited"] is True


def test_regeneration_tells_the_client_to_reset_the_answer(settings: Settings) -> None:
    judge = ScriptedJudge(groundings=[NOT_GROUNDED, GROUNDED])
    agent = _agent(settings, judge, "It is purple [1].", "It is fact 0 [1].")
    events = list(agent.stream("What colour?", "t1"))
    reset = _types(events).index("answer_reset")
    after = "".join(e.data["text"] for e in events[reset:] if e.type == "token")
    assert after == "It is fact 0 [1]."
    assert events[-1].data["answer"] == "It is fact 0 [1]."


def test_cancel_stops_the_turn(settings: Settings) -> None:
    agent = _agent(settings, ScriptedJudge(), "never fully streamed")
    cancel = threading.Event()
    events = []
    for event in agent.stream("q", "t1", cancel):
        events.append(event)
        cancel.set()  # e.g. the browser disconnected after the first event
    assert len(events) == 1 and "done" not in _types(events)


def test_turns_are_saved_for_the_history_view(settings: Settings) -> None:
    agent = _agent(settings, ScriptedJudge(), "First [1].", "Second [1].")
    list(agent.stream("q1", "t1"))
    list(agent.stream("q2", "t1"))
    turns = agent.graph.get_state({"configurable": {"thread_id": "t1"}}).values["turns"]
    assert [(t["question"], t["answer"]) for t in turns] == [("q1", "First [1]."),
                                                              ("q2", "Second [1].")]  # fmt: skip
    assert turns[0]["sources"][0]["cited"] is True and turns[0]["grounded"] is True


# ------------------------------------------------------------------------ API


def _session(title: str = "New chat") -> SessionRecord:
    now = datetime.now(UTC)
    return SessionRecord(uuid.uuid4(), title, 0, now, now)


class FakeSessions:
    def __init__(self) -> None:
        self.records: dict[uuid.UUID, SessionRecord] = {}
        self.turns: list[tuple[uuid.UUID, str]] = []

    def create(self) -> SessionRecord:
        record = _session()
        self.records[record.id] = record
        return record

    def get(self, session_id: uuid.UUID) -> SessionRecord | None:
        return self.records.get(session_id)

    def list_recent(self, limit: int) -> list[SessionRecord]:
        return list(self.records.values())[:limit]

    def record_turn(self, session_id: uuid.UUID, question: str) -> None:
        self.turns.append((session_id, question))

    def delete(self, session_id: uuid.UUID) -> bool:
        return self.records.pop(session_id, None) is not None


class FakeCheckpointer:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def get_tuple(self, config: dict) -> None:
        return None

    def delete_thread(self, thread_id: str) -> None:
        self.deleted.append(thread_id)


class StreamingAgent:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def stream(self, message: str, thread_id: str, cancel: threading.Event) -> Iterator[ChatEvent]:
        yield ChatEvent("status", {"step": "Searching your documents"})
        if self.fail:
            raise ConnectionError("qdrant down")
        yield ChatEvent("token", {"text": "Hi "})
        yield ChatEvent("token", {"text": "there"})
        yield ChatEvent("sources", {"sources": []})
        yield ChatEvent("done", {"answer": "Hi there"})


class FakeServices:
    def __init__(self, settings: Settings, agent: StreamingAgent) -> None:
        self.settings, self._agent = settings, agent
        self.session_store, self.saver = FakeSessions(), FakeCheckpointer()

    def sessions(self) -> FakeSessions:
        return self.session_store

    def checkpointer(self) -> FakeCheckpointer:
        return self.saver

    def agent(self) -> StreamingAgent:
        return self._agent

    def close(self) -> None:
        pass


@pytest.fixture
def api(settings: Settings) -> Iterator[tuple[TestClient, FakeServices]]:
    with TestClient(create_app(settings)) as client:
        fake = FakeServices(settings, StreamingAgent())
        client.app.state.services = fake
        yield client, fake


def _sse_events(body: str) -> list[tuple[str, dict]]:
    events, current = [], None
    for line in body.splitlines():
        if line.startswith("event:"):
            current = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and current:
            events.append((current, json.loads(line.split(":", 1)[1])))
    return events


def test_session_crud(api) -> None:
    client, fake = api
    created = client.post("/api/sessions")
    assert created.status_code == 201
    session_id = created.json()["id"]
    assert [s["id"] for s in client.get("/api/sessions").json()] == [session_id]
    history = client.get(f"/api/sessions/{session_id}/history").json()
    assert history["turns"] == [] and history["session"]["title"] == "New chat"
    assert client.delete(f"/api/sessions/{session_id}").status_code == 204
    assert fake.saver.deleted == [session_id], "the conversation memory is deleted too"
    assert client.get(f"/api/sessions/{session_id}/history").status_code == 404


def test_chat_streams_server_sent_events(api) -> None:
    client, fake = api
    session_id = client.post("/api/sessions").json()["id"]
    response = client.post("/api/chat", json={"session_id": session_id, "message": " Hello "})
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    events = _sse_events(response.text)
    assert [t for t, _ in events] == ["status", "token", "token", "sources", "done"]
    assert fake.session_store.turns == [(uuid.UUID(session_id), "Hello")]


def test_chat_errors_become_an_error_event(api) -> None:
    client, fake = api
    fake._agent = StreamingAgent(fail=True)
    session_id = client.post("/api/sessions").json()["id"]
    events = _sse_events(
        client.post("/api/chat", json={"session_id": session_id, "message": "hi"}).text
    )
    assert events[-1][0] == "error" and "went wrong" in events[-1][1]["message"]
    assert fake.session_store.turns == [], "a failed turn isn't counted"


def test_chat_rejects_unknown_session_and_busy_session(api) -> None:
    client, _ = api
    unknown = client.post("/api/chat", json={"session_id": str(uuid.uuid4()), "message": "hi"})
    assert unknown.status_code == 404
    session_id = client.post("/api/sessions").json()["id"]
    client.app.state.turn_guard.try_start(session_id)  # pretend a turn is still running
    busy = client.post("/api/chat", json={"session_id": session_id, "message": "hi"})
    assert busy.status_code == 409


def test_chat_validates_the_message(api) -> None:
    client, _ = api
    session_id = client.post("/api/sessions").json()["id"]
    assert (
        client.post("/api/chat", json={"session_id": session_id, "message": ""}).status_code == 422
    )
