# CLAUDE.md — Project Rules for the Agentic RAG Chatbot

This file is read by Claude Code at the start of every session. It is the contract
between the learner (project owner) and the AI mentor. Read it fully before doing anything.

## 1. What we are building

A production-grade **agentic RAG chatbot** that:

- ingests documents (PDF / MD / TXT / DOCX) and GitHub repositories,
- retrieves with **hybrid search** (dense + BM25 sparse, fused with RRF) and **cross-encoder reranking**,
- answers through an **agentic loop**: route → retrieve → grade → rewrite → generate → grounding check,
- keeps **per-session memory that survives restarts**,
- exposes a **streaming API** (Server-Sent Events) from a **Python backend** and a **React (JavaScript) web chat UI**,
- is fully **traced / observable**,
- deploys with **one command** (`docker compose up -d`).

Stretch: n8n workflows; hallucination / accuracy / bias evaluation.

The owner is a **beginner**. The mentor teaches while building: explain the *why*, keep
code readable, and never skip the concept behind a change.

## 2. Working rules (non-negotiable)

1. **Plan first, then wait for "go".** At the start of every session (and before any
   non-trivial change), post a short plan: goal, files to create/change, steps, how we will
   verify. **Do not write or change code until the owner replies "go".**
2. **Never change the stack, add a dependency, or add any paid / non-open-source tool
   without asking first.** This includes new pip packages, Docker images, SaaS APIs, and
   cloud services. Propose → explain → wait for approval.
3. **One session at a time.** Follow the session order in `PLAN.md`. Do not build features
   from future sessions "while we're here".
4. **Update `MEMORY.md` at the end of every session** (what was done, decisions, open
   issues, next step). Update `PLAN.md` if the plan changed (with owner approval).
5. **Do not touch files outside the session's scope.** Never delete or overwrite the
   owner's files without asking.
6. **Verify before declaring done.** Run tests / the app / the verify commands from the
   session's Definition of Done and show the output. If something fails, say so plainly.
7. **Explain as you go.** Brief, beginner-level explanations of new concepts; add new terms
   to `GLOSSARY.md`.
8. **No secrets in code or git.** Config comes from environment variables (`.env`, never
   committed). Only `.env.example` is committed.
9. **Free and open source only**, installable via `pip` (backend), `npm` (frontend) or
   `docker compose`, runnable on a Windows laptop with **no GPU** (16 GB RAM, Intel Core 7 150U).
   **One approved exception (owner decision, 2026-10-20): the LLM is OpenAI's paid API.** Do not add any
   other paid service, and do not switch OpenAI models or raise reasoning effort / token limits without asking,
   because those change the bill.
10. **Backend is Python, frontend is React (JavaScript).** Do not propose other languages or
    frameworks for either side.

## 3. Chosen stack (locked — change only with owner approval)

| Layer | Choice | Version | Licence |
|---|---|---|---|
| Backend language | Python | 3.12 (venv) | PSF |
| Frontend language / runtime | JavaScript (ES modules + JSX) on Node.js LTS | Node 24 LTS (22 also works) | MIT |
| LLM provider | **OpenAI API** (paid, owner-approved) via `openai` SDK + `langchain-openai` | 3.35.1 / 1.7.2 | Proprietary service; SDKs Apache-2.0 / MIT |
| Generator model | `gpt-6.1-sol`, reasoning effort `low` ($2 / $10 per 1M tokens in/out) | — | — |
| Router / grader / grounding model | `gpt-6-luna`, reasoning effort `none` ($0.10 / $0.50 per 1M tokens) | — | — |
| Token counting | tiktoken (history trimming, cost estimates) | 0.14.0 | MIT |
| Agent orchestration | LangGraph (+ langchain-core, langchain-openai) | 1.2.16 | MIT |
| Embeddings (dense) | FastEmbed `BAAI/bge-small-en-v1.5` (ONNX, CPU) | fastembed 0.9.0 | Apache-2.0 / MIT |
| Embeddings (sparse) | FastEmbed `Qdrant/bm25` | fastembed 0.9.0 | Apache-2.0 |
| Reranker | FastEmbed cross-encoder `Xenova/ms-marco-MiniLM-L-6-v2` | fastembed 0.9.0 | Apache-2.0 |
| Vector database | Qdrant (hybrid query + RRF fusion server-side) | image `qdrant/qdrant:v1.19.2` | Apache-2.0 |
| Relational DB / memory | PostgreSQL (app tables + LangGraph checkpoints) | image `postgres:17.11` | PostgreSQL |
| Document parsing | MarkItDown (`[docx]`) for DOCX; **pdfplumber** for PDFs, page by page (owner-approved 2026-10-26: exact page numbers + scanned-page detection) | 0.1.8 / 0.11.10 | MIT / MIT |
| Chunking | langchain-text-splitters | 1.1.3 | MIT |
| GitHub ingestion | GitPython (shallow clone) | 3.2.1 | BSD-3 |
| API | FastAPI + Uvicorn + sse-starlette | 0.152.0 / 0.54.0 / 3.5.0 | MIT / BSD |
| Config | pydantic-settings | 2.16.1 | MIT |
| Frontend framework | React + React DOM | 19.3.1 | MIT |
| Frontend build / dev server | Vite + @vitejs/plugin-react | 8.3.4 / 6.1.2 | MIT |
| Markdown rendering (answers) | react-markdown + remark-gfm | 10.1.0 / 4.0.1 | MIT |
| Frontend tests | Vitest + React Testing Library + jest-dom + jsdom | 5.0.5 / 16.3.3 / 7.0.1 / 30.1.3 | MIT |
| Frontend lint / format | ESLint (+ react-hooks, react-refresh plugins) + Prettier | 10.13.0 / 3.9.10 | MIT |
| Frontend serving (prod) | nginx: serves the built files and proxies `/api` to the backend | image `nginx:1.30.6-alpine` (build stage `node:24.22.0-alpine`) | BSD-2 |
| Tracing | MLflow Tracing (app: `mlflow-tracing`; server: `ghcr.io/mlflow/mlflow:v3.17.1`) | 3.17.1 | Apache-2.0 |
| Logging | structlog (JSON logs) | 26.1.0 | MIT / Apache-2.0 |
| Backend tests / lint | pytest, pytest-asyncio, ruff | 9.1.1 / 1.4.0 / 0.17.1 | MIT |
| Containers | Docker Engine + Compose via **Docker Desktop** (owner installed it, 2026-10-26; replaces the planned Rancher Desktop) | 4.97.0 (Engine 29.9.2, Compose v5.6.1) | Proprietary app, free for personal use / small business; engine Apache-2.0 |
| Evaluation (stretch) | DeepEval + own retrieval metrics | 4.3.1 | Apache-2.0 |
| Workflows (stretch) | n8n (optional compose profile) | image `n8nio/n8n:2.45.0` | **Sustainable Use License — fair-code, NOT OSI open source.** Free to self-host for internal use. Owner must confirm before Stretch B. |

Pinned Python versions live in `requirements.txt`. JavaScript versions are pinned exactly (no `^` or `~`)
in `frontend/package.json`, and `frontend/package-lock.json` is committed. Pin Docker images to exact tags (never `latest`).

## 4. Folder layout (target)

Folders are created in the session that needs them (see `PLAN.md`), not up front.

```
.
├── CLAUDE.md  PLAN.md  MEMORY.md  GLOSSARY.md  SETUP.md   # project docs
├── requirements.txt  .env.example  pyproject.toml          # deps + tool config
├── docker-compose.yml                                      # all services, one command
├── docker/                    # Dockerfiles + DB init scripts
├── app/                       # the backend (FastAPI + agent)
│   ├── config.py              # Settings (pydantic-settings) — the ONLY place env vars are read
│   ├── logging_setup.py       # structlog JSON logging
│   ├── main.py                # FastAPI app factory + lifespan (startup/shutdown)
│   ├── api/                   # HTTP routes + request/response schemas
│   ├── ingestion/             # loaders, github, chunking, ingest pipeline
│   ├── retrieval/             # embeddings, qdrant store, reranker, hybrid retriever
│   ├── agent/                 # LangGraph state, prompts, nodes, graph, llm factory
│   ├── memory/                # Postgres checkpointer + session helpers
│   ├── db/                    # Postgres connection pool, schema.sql, repositories
│   └── observability/         # MLflow tracing setup, request IDs
├── frontend/                  # React + Vite chat app (talks to the API over HTTP only)
│   ├── package.json  package-lock.json  vite.config.js  eslint.config.js  index.html
│   ├── nginx.conf             # prod: serve built files, proxy /api → api:8000 (streaming-safe)
│   └── src/
│       ├── main.jsx  App.jsx
│       ├── api/               # ALL HTTP calls: client.js (fetch wrappers), sse.js (stream parser)
│       ├── hooks/             # useChatStream.js, useSessions.js, useIngestJobs.js
│       ├── components/        # ChatWindow, MessageBubble, SourceList, GroundingBadge, ... (+ .module.css)
│       └── test/setup.js      # Vitest + Testing Library setup
├── evals/                     # golden datasets + evaluation scripts (stretch)
├── n8n/                       # exported n8n workflow JSON (stretch)
├── data/sample_docs/          # small sample documents for demos/tests (fictional "Lumen Home" product docs)
├── scripts/                   # one-off helper scripts (e.g. make_sample_docs.py generates the sample PDF/DOCX)
└── tests/                     # unit/ and integration/ tests mirroring app/
```

Dependency direction: `api → agent → (retrieval → (qdrant, embeddings), llm → OpenAI)`; `api → ingestion → retrieval`.
`frontend` never imports `app`; it only calls the HTTP API.
All backend routes live under the `/api` prefix (health checks `/health`, `/ready` excepted). The frontend uses the
relative path `/api`: the Vite dev proxy forwards it in development and nginx forwards it in production, so
no CORS configuration and no hard-coded hostnames are needed.

## 5. Coding standards

### Backend (Python)

- **Python 3.12**, type hints on every function signature; `from __future__ import annotations` not needed.
- **Pydantic models at every boundary** (API requests/responses, LLM structured outputs, config).
- **Config only through `app/config.py`** (`Settings`). No `os.getenv` elsewhere. No hard-coded URLs, model names, or magic numbers in logic — put them in Settings.
- **Logging, not print.** Use `structlog.get_logger(__name__)`; log events as `snake_case` with key/value context (`log.info("chunks_upserted", count=n, doc_id=...)`). Never log secrets or full document text.
- **Small, single-purpose functions** (aim < 40 lines). Module docstring at top of every file explaining its role in plain English. Docstrings on public functions. Comments explain *why*, not *what*.
- **Async in the API layer** (FastAPI routes, streaming). CPU-bound work (embedding, reranking, parsing) runs in a thread (`anyio.to_thread.run_sync` / `run_in_threadpool`) so it doesn't block the event loop.
- **Every network call has a timeout**; retries (tenacity) only for idempotent calls, with backoff.
- **LLM calls return structured output** (Pydantic schema via OpenAI structured outputs, `with_structured_output(..., strict=True)`) wherever the result drives control flow (route, grade, grounding). Always have a safe fallback if parsing fails.
- **OpenAI usage rules:**
  - Only `app/agent/llm.py` creates model clients. Model IDs, reasoning effort, max output tokens, timeout and retries all come from Settings.
  - Every call sets a timeout and a max output token cap.
  - Log token usage and estimated cost per request, never the API key.
  - Unit tests use a fake LLM and must never call the real API. Real-API tests are marked `@pytest.mark.openai` and run only on demand.
- **Bounded loops.** Every agent loop has a max-iterations setting (rewrites, regenerations).
- **Prompts live in `app/agent/prompts.py`**, never inline in node code.
- **Naming:** `snake_case` functions/vars/modules, `PascalCase` classes, `UPPER_SNAKE` constants. Files named for what they contain (`reranker.py`, not `utils2.py`).
- **Errors:** raise specific exceptions; convert to clear HTTP errors at the API edge; never swallow exceptions silently.
- **Tests:** `pytest`. Unit tests for pure logic (chunking, fusion, routing parsers) with no network; integration tests marked `@pytest.mark.integration` that need Docker services. Each session adds tests for what it built.
- **Formatting / lint:** `ruff format` and `ruff check` must pass before a session is "done".
- **Security:** treat ingested documents and repos as untrusted text (prompt-injection aware prompts; never execute code from ingested repos); validate upload size/type; clone repos shallow, read-only, with size limits.

### Frontend (React, JavaScript)

- **JavaScript (ES modules) + JSX. Function components and hooks only**, with no class components. TypeScript only with owner approval.
- **One component per file**, named `PascalCase.jsx`, with styles in a matching `PascalCase.module.css` (CSS Modules). No UI kit or CSS framework without approval.
- **All HTTP calls live in `src/api/`.** Components never call `fetch` directly. Components use hooks (`src/hooks/useXxx.js`), and hooks call `src/api/`.
- **Relative `/api` base path only.** Never hard-code `localhost` or ports in frontend code.
- **No secrets in the frontend.** Everything shipped to the browser is public. `import.meta.env.VITE_*` is only for non-secret settings.
- **State:** `useState` / `useReducer` plus small custom hooks. No Redux, Zustand, React Query, etc. without approval.
- **Model output is untrusted.** Render answers with `react-markdown` and never use `dangerouslySetInnerHTML`. Links open with `rel="noopener noreferrer"`.
- **Streaming:** parse SSE from the `fetch` response body (POST requests). Every stream can be cancelled with an `AbortController`. Always show a visible message for `error` events, network failures and timeouts. The UI must never freeze silently.
- **Effects clean up after themselves** (abort requests, clear timers) so nothing leaks when a component unmounts.
- **Accessibility basics:** semantic HTML, labelled inputs, Enter submits and Shift+Enter adds a newline, `aria-live="polite"` on the streaming answer.
- **Comments and docs:** JSDoc on every function in `src/api/` and `src/hooks/`. Comments explain *why*.
- **Tests:** Vitest + React Testing Library test what the user sees (text, buttons), not internals. Pure logic such as the SSE parser gets unit tests, including partial and split chunks.
- **Before a session is "done":** `npm run lint`, `npm test` and `npm run build` must pass, and Prettier formatting is applied.
- **Dependencies:** exact pins, committed lockfile, `npm ci` in Docker. Adding any npm package needs owner approval (rule 2).

## 6. Session protocol

1. Read `CLAUDE.md`, `MEMORY.md` (latest entry), and the current session in `PLAN.md`.
2. Post the plan (goal, files, steps, verification) and the new concepts that will be taught. **Wait for "go".**
3. Build in small steps; run/verify after each step; explain briefly.
4. Run the Definition-of-Done checks; show results.
5. Append the session entry to `MEMORY.md`; add new terms to `GLOSSARY.md`; give the homework.

## 7. Common commands (once created)

```powershell
.\.venv\Scripts\Activate.ps1            # activate virtual environment
pip install -r requirements.txt          # install pinned deps
docker compose up -d                     # start all services
docker compose ps                        # check service health
uvicorn app.main:create_app --factory --reload   # run API locally (dev) at http://127.0.0.1:8000
pytest                                   # fast, free unit tests (default excludes integration/openai)
pytest -m integration                    # tests against real services (needs docker + OpenAI key)
ruff format . ; ruff check .             # backend format + lint

cd frontend
npm ci                                   # install exact frontend deps from the lockfile
npm run dev                              # React dev server at http://localhost:5173 (proxies /api)
npm test                                 # Vitest
npm run lint ; npm run format            # ESLint + Prettier
npm run build                            # production build into frontend/dist
```
