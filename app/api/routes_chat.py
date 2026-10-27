"""Chat endpoints.

`POST /api/chat/simple` is the Session 6 baseline: one question in, one complete answer out
(no streaming, no memory). Session 8 adds the streaming, memory-backed `POST /api/chat`.
"""

from dataclasses import asdict

import openai
import structlog
from fastapi import APIRouter, HTTPException, Request, status
from starlette.concurrency import run_in_threadpool

from app.agent.llm import MissingAPIKeyError
from app.api.schemas import SimpleChatRequest, SimpleChatResponse
from app.services import Services

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


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
