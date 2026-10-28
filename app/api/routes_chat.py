"""Chat endpoints: conversations (sessions) and the streaming chat turn.

    POST   /api/sessions                  create a conversation
    GET    /api/sessions                  list conversations (most recent first)
    GET    /api/sessions/{id}/history     questions, answers and sources of one conversation
    DELETE /api/sessions/{id}             delete a conversation and its memory
    POST   /api/chat                      send a message; the answer streams back as SSE
    POST   /api/chat/simple               (Session 6 baseline, no memory, no streaming)

Streaming design: the agent is synchronous and runs in ONE worker thread for the whole turn.
It hands each event to the async response through a queue. If the browser disconnects, a
cancel flag stops the agent at its next step, so no tokens are wasted.
"""

import asyncio
import json
import threading
import uuid
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Any

import openai
import structlog
from fastapi import APIRouter, HTTPException, Query, Request, status
from sse_starlette import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from app.agent.graph import ChatEvent, RagAgent
from app.agent.llm import MissingAPIKeyError
from app.api.schemas import (
    ChatRequest,
    HistoryResponse,
    SessionResponse,
    SimpleChatRequest,
    SimpleChatResponse,
)
from app.services import Services

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])

_END = object()  # marks the end of a turn's event queue


class TurnGuard:
    """Allows only one running turn per conversation (two at once would corrupt its memory)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: set[str] = set()

    def try_start(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._active:
                return False
            self._active.add(session_id)
            return True

    def finish(self, session_id: str) -> None:
        with self._lock:
            self._active.discard(session_id)


def _services(request: Request) -> Services:
    return request.app.state.services


# ------------------------------------------------------------------------- sessions


@router.post("/sessions", status_code=status.HTTP_201_CREATED, response_model=SessionResponse)
async def create_session(request: Request) -> SessionResponse:
    record = await run_in_threadpool(_services(request).sessions().create)
    return SessionResponse(**asdict(record))


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    request: Request, limit: int = Query(50, ge=1, le=200)
) -> list[SessionResponse]:
    records = await run_in_threadpool(_services(request).sessions().list_recent, limit)
    return [SessionResponse(**asdict(r)) for r in records]


@router.get("/sessions/{session_id}/history", response_model=HistoryResponse)
async def session_history(request: Request, session_id: uuid.UUID) -> HistoryResponse:
    services = _services(request)
    record = await run_in_threadpool(services.sessions().get, session_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found")
    turns = await run_in_threadpool(_saved_turns, services, str(session_id))
    return HistoryResponse(session=SessionResponse(**asdict(record)), turns=turns)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(request: Request, session_id: uuid.UUID) -> None:
    services = _services(request)
    if not await run_in_threadpool(services.sessions().delete, session_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found")
    await run_in_threadpool(services.checkpointer().delete_thread, str(session_id))


def _saved_turns(services: Services, thread_id: str) -> list[dict[str, Any]]:
    """Read the turn records from the latest checkpoint (no models are loaded for this)."""
    saved = services.checkpointer().get_tuple({"configurable": {"thread_id": thread_id}})
    if saved is None:
        return []
    return list(saved.checkpoint.get("channel_values", {}).get("turns", []))


# ----------------------------------------------------------------------------- chat


@router.post("/chat")
async def chat(request: Request, body: ChatRequest) -> EventSourceResponse:
    """Answer a message within a conversation, streaming Server-Sent Events:
    status, token, answer_reset, sources, done (or error)."""
    services = _services(request)
    session_id = str(body.session_id)
    if await run_in_threadpool(services.sessions().get, body.session_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found")
    try:
        agent = await run_in_threadpool(services.agent)
    except MissingAPIKeyError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from None
    guard: TurnGuard = request.app.state.turn_guard
    if not guard.try_start(session_id):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "this conversation is still answering the previous message"
        )

    message = body.message.strip()

    async def sse() -> AsyncIterator[dict[str, str]]:
        async for event in _run_turn(agent, message, session_id, guard):
            if event.type == "done":
                await run_in_threadpool(services.sessions().record_turn, body.session_id, message)
            yield {"event": event.type, "data": json.dumps(event.data)}

    # X-Accel-Buffering: tells nginx (Session 10) to pass events on immediately.
    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return EventSourceResponse(sse(), headers=headers)


async def _run_turn(
    agent: RagAgent, message: str, session_id: str, guard: TurnGuard
) -> AsyncIterator[ChatEvent]:
    """Run the agent in a worker thread and relay its events as they happen."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[Any] = asyncio.Queue()
    cancel = threading.Event()

    def work() -> None:
        try:
            for event in agent.stream(message, session_id, cancel):
                loop.call_soon_threadsafe(queue.put_nowait, event)
        except Exception as exc:  # report every failure to the browser as an error event
            loop.call_soon_threadsafe(queue.put_nowait, _error_event(exc))
        finally:
            guard.finish(session_id)  # only now may the next message of this conversation start
            loop.call_soon_threadsafe(queue.put_nowait, _END)

    loop.run_in_executor(None, work)
    try:
        while (item := await queue.get()) is not _END:
            yield item
    finally:
        cancel.set()  # the browser went away (or we finished): stop the agent


def _error_event(exc: Exception) -> ChatEvent:
    if isinstance(exc, MissingAPIKeyError):
        message = "The OpenAI API key is not configured."
    elif isinstance(exc, openai.RateLimitError):
        message = "The language model is busy right now (rate limit). Please try again shortly."
    elif isinstance(exc, openai.APIError):
        message = "The language model request failed. Please try again."
    else:
        message = "Something went wrong while answering. Please try again."
    log.exception("chat_turn_failed", error=type(exc).__name__, exc_info=exc)
    return ChatEvent("error", {"message": message})


# ----------------------------------------------------------- Session 6 baseline


@router.post("/chat/simple", response_model=SimpleChatResponse)
async def chat_simple(request: Request, body: SimpleChatRequest) -> SimpleChatResponse:
    """Answer one question from the indexed documents, with numbered citations."""
    services: Services = request.app.state.services
    try:
        rag = await run_in_threadpool(services.simple_rag)
        answer = await run_in_threadpool(rag.answer, body.question.strip())
    except MissingAPIKeyError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from None
    except openai.APIError as exc:  # rate limit, outage, bad key... after the SDK's retries
        log.warning("llm_call_failed", error=type(exc).__name__)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"the language model request failed ({type(exc).__name__})"
        ) from None
    return SimpleChatResponse(
        answer=answer.text,
        sources=[asdict(source) for source in answer.sources],
        usage=answer.usage,
        cost_usd=answer.cost_usd,
        latency_ms=answer.latency_ms,
    )
