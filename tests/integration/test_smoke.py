"""Smoke test of the deployed system: the containers, exactly as a user reaches them.

It goes through nginx (http://localhost:8080), like the browser does:
upload the sample docs → wait for the ingest job → ask a question → read the streamed answer.

It proves the parts that only exist in the deployed setup: nginx forwards /api, uploads pass
through it, and the answer arrives word by word (nginx is not buffering the stream).

Needs the full stack (`docker compose up -d`) and a valid OPENAI_API_KEY (one answer, ≈ $0.005).
Skipped by default; run with:

    pytest -m smoke
"""

import json
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from app.config import Settings

pytestmark = [pytest.mark.smoke, pytest.mark.openai]

SAMPLE_DOCS = Path(__file__).resolve().parents[2] / "data" / "sample_docs"
QUESTION = "What does error E-207 mean?"
JOB_TIMEOUT_S = 180
ANSWER_TIMEOUT_S = 120


@pytest.fixture(scope="module")
def http() -> Iterator[httpx.Client]:
    base_url = f"http://127.0.0.1:{Settings().frontend_port}"
    with httpx.Client(base_url=base_url, timeout=30) as client:
        try:
            client.get("/").raise_for_status()
        except httpx.HTTPError as exc:
            pytest.fail(
                f"the app isn't reachable at {base_url} — run `docker compose up -d` ({exc})"
            )
        yield client


def _upload_sample_docs(http: httpx.Client) -> str:
    files = [("files", (p.name, p.read_bytes())) for p in sorted(SAMPLE_DOCS.iterdir())]
    response = http.post("/api/ingest/files", files=files)
    assert response.status_code == 202, response.text
    return response.json()["id"]


def _wait_for_job(http: httpx.Client, job_id: str) -> dict:
    deadline = time.monotonic() + JOB_TIMEOUT_S
    while time.monotonic() < deadline:
        job = http.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("succeeded", "failed"):
            return job
        time.sleep(1)
    pytest.fail(f"ingest job {job_id} didn't finish within {JOB_TIMEOUT_S} s")


def _stream_answer(http: httpx.Client, session_id: str) -> list[tuple[float, str, dict]]:
    """POST a question and collect (arrival time, event name, data) for every SSE event."""
    events: list[tuple[float, str, dict]] = []
    name = "message"
    body = {"session_id": session_id, "message": QUESTION}
    with http.stream("POST", "/api/chat", json=body, timeout=ANSWER_TIMEOUT_S) as response:
        assert response.status_code == 200, response.read().decode()
        for line in response.iter_lines():
            if line.startswith("event:"):
                name = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data = json.loads(line.removeprefix("data:").strip())
                events.append((time.monotonic(), name, data))
    return events


def test_upload_ask_and_stream_through_nginx(http: httpx.Client) -> None:
    job = _wait_for_job(http, _upload_sample_docs(http))
    assert job["status"] == "succeeded", job
    # Already-indexed files are skipped, so a re-run against the same data also passes.
    assert all(r["outcome"] in ("indexed", "reindexed", "skipped") for r in job["results"]), job

    session_id = http.post("/api/sessions").json()["id"]
    try:
        events = _stream_answer(http, session_id)
    finally:
        http.delete(f"/api/sessions/{session_id}")

    names = [name for _, name, _ in events]
    assert "error" not in names, events
    tokens = [(t, data["text"]) for t, name, data in events if name == "token"]
    done = next(data for _, name, data in events if name == "done")
    sources = next(data["sources"] for _, name, data in events if name == "sources")

    # Streamed, not buffered: many token events, arriving over a period of time.
    assert len(tokens) >= 5, f"only {len(tokens)} token events: is nginx buffering?"
    assert tokens[-1][0] - tokens[0][0] > 0.2, "all tokens arrived at once: nginx is buffering"

    # A real, cited, verified answer from the sample docs.
    answer = done["answer"]
    assert "wi-fi" in answer.lower(), answer
    assert any(s["cited"] for s in sources), sources
    assert "[1]" in answer or "[2]" in answer, answer
    assert done["grounded"] is True, done
