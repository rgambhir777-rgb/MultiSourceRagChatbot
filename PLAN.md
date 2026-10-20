# PLAN.md — Agentic RAG Chatbot: Architecture & Build Plan

> Status: **planning complete, no application code yet.** Next: Session 1.
> Stack is locked in `CLAUDE.md` §3. Comparison tables that justify each pick are in the Appendix.

---

## 1. Architecture at a glance

```
                               ┌─────────────────────────────────────────────────────┐
  Browser                      │                 docker compose network               │
 ┌────────────┐  HTTP          │                                                      │
 │ React SPA  │──────────────► │  ┌───────────────────────── api (FastAPI) ────────┐  │
 │ UI (nginx) │ ◄── SSE stream │  │                                                 │  │
 │  :8080     │                │  │  /ingest/files  /ingest/github   /chat (SSE)    │  │
 └────────────┘                │  │        │               │             │          │  │
                               │  │        ▼               ▼             ▼          │  │
 ┌────────────┐  webhooks      │  │  ┌──────────── Ingestion ───┐  ┌─ Agent (LangGraph) ──────────┐
 │ n8n (opt.) │──────────────► │  │  │ load → markdown          │  │                               │
 │  :5678     │                │  │  │ (MarkItDown / git clone) │  │  route ─┬─► direct answer      │
 └────────────┘                │  │  │ chunk (header/code aware)│  │         └─► retrieve ◄──┐      │
                               │  │  │ dedup (sha256)           │  │              │          │      │
                               │  │  │ embed dense + sparse     │  │              ▼          │      │
                               │  │  └──────────┬───────────────┘  │            grade        │      │
                               │  │             │ upsert           │      relevant? │ no ──► rewrite │
                               │  │             ▼                  │            yes ▼   (max 2)     │
                               │  │  ┌──────── Retrieval ───────────────┐      generate             │
                               │  │  │ dense (bge-small) ─┐             │◄──────── │                │
                               │  │  │ sparse (BM25) ─────┼─ RRF (Qdrant)│          ▼                │
                               │  │  │ top-20 ──► cross-encoder rerank  │   grounding check         │
                               │  │  │            ──► top-5             │   ok ─► done │ no ─► regen │
                               │  │  └──────────────────────────────────┘          (max 1)          │
                               │  └────────┬──────────────┬───────────────┬──────────────┬─────────┘
                               │           ▼              ▼               ▼              ▼
                               │   ┌────────────┐ ┌──────────────┐ ┌────────────┐ ┌────────────┐
                               │   │  Qdrant    │ │  PostgreSQL  │ │  Ollama    │ │  MLflow    │
                               │   │  :6333     │ │  :5432       │ │  :11434    │ │  :5000     │
                               │   │ vectors +  │ │ docs, jobs,  │ │ qwen3.5:4b │ │ traces of  │
                               │   │ payloads   │ │ sessions,    │ │ qwen3.5:2b │ │ every node,│
                               │   │            │ │ checkpoints  │ │            │ │ LLM call   │
                               │   └────────────┘ └──────────────┘ └────────────┘ └────────────┘
                               │        all data on named Docker volumes (survive restarts)    │
                               └─────────────────────────────────────────────────────────────────┘
```

**Two languages, one HTTP contract.** The backend is **Python** (FastAPI + LangGraph). The frontend is
**React (JavaScript)**, built by Vite into static files that nginx serves. Every backend route sits under `/api`
(the diagram omits the prefix). In the browser, the React app calls the relative path `/api/...`. In development
the Vite dev server (:5173) forwards these calls to the backend, and in production nginx (:8080) does. Because
the browser only ever talks to one origin, no CORS setup is needed.

**Request flow for a chat message**

1. The React UI sends `POST /api/chat` with `session_id` + `message`. nginx (or the Vite proxy) forwards it to the API, which opens an SSE stream. React reads the stream with `fetch`, because `EventSource` can't send POST requests.
2. LangGraph loads that session's previous state from Postgres (the *checkpointer*).
3. **route** (small model) decides: does this need the knowledge base, or can it be answered directly (greeting, follow-up about the conversation itself)?
4. **retrieve**: hybrid search in Qdrant (dense + BM25 → RRF) gets 20 candidates; the cross-encoder **reranks** to the best 5.
5. **grade** (small model, one batched call) keeps only chunks that actually help answer the question.
6. If nothing relevant → **rewrite** the query (max 2 times) and retrieve again; if still nothing → honest "I couldn't find this in your documents."
7. **generate** (4B model) writes the answer with `[1]`-style citations; tokens stream to the UI live.
8. **grounding check** verifies every claim is supported by the chunks. Fail → regenerate once with a stricter prompt; still failing → answer is marked *unverified* in the UI.
9. The final state is checkpointed to Postgres; the whole run is one trace in MLflow.

---

## 2. Every component, in plain language

| Component | What it is | Why it exists here |
|---|---|---|
| **Ollama** | A local server that runs open LLMs on your CPU and exposes a simple HTTP API. | Free, private, no API keys. Our "brain". |
| **qwen3.5:4b** | A 4-billion-parameter instruction model (~3.4 GB RAM at Q4). | Big enough to write good grounded answers; small enough for a laptop CPU. |
| **qwen3.5:2b** | A 2B sibling (~1.9 GB). | Routing/grading are simple yes/no decisions: a smaller model is ~2× faster and good enough. Saves seconds per message. |
| **LangGraph** | A library for building agents as a *graph*: nodes (steps) + edges (what runs next, including loops). | Our loop has branches and retries; a graph makes that explicit, testable, traceable, and gives us persistent memory for free via checkpointers. |
| **FastEmbed** | Runs embedding / reranking models with ONNX Runtime (no PyTorch). | CPU-fast, ~200 MB instead of multi-GB torch installs; painless on Windows. |
| **Dense embeddings** (bge-small, 384-dim) | Turn text into vectors where similar *meaning* ⇒ nearby vectors. | Finds paraphrases ("car" ≈ "vehicle"). |
| **Sparse embeddings** (BM25) | Keyword-weighting vectors. | Finds exact terms dense models miss: error codes, function names, acronyms. |
| **RRF (Reciprocal Rank Fusion)** | Merges two ranked lists by rank position, not raw scores. | Dense and BM25 scores aren't comparable; RRF fuses them robustly with no tuning. Qdrant does it server-side. |
| **Cross-encoder reranker** | Reads (question, chunk) *together* and scores relevance. | Much more accurate than vector similarity, but slow — so only applied to the top-20 candidates. |
| **Qdrant** | A vector database. Stores chunks + vectors + metadata ("payload"). | Native hybrid (dense+sparse) queries with RRF in one call; single small container; filters by source/session. |
| **PostgreSQL** | Relational database. | Stores the document registry, ingestion jobs, sessions, and LangGraph checkpoints (= memory that survives restarts). One reliable DB instead of several. |
| **MarkItDown** | Converts PDF/DOCX/etc. into Markdown. | One library for all document types; Markdown headings let us chunk by section. |
| **Text splitters** | Cut documents into overlapping chunks (by Markdown headers, or by code structure). | LLMs need small, focused pieces; good chunking is the #1 driver of RAG quality. |
| **GitPython** | Clones git repositories. | Shallow-clone GitHub repos, then reuse the same ingest pipeline on their files. |
| **FastAPI + Uvicorn** | Python web framework + server. | Typed endpoints, automatic OpenAPI docs at `/docs`, first-class async for streaming. |
| **SSE (sse-starlette)** | Server-Sent Events: a one-way HTTP stream from server to browser. | Lets tokens and progress ("retrieving…", "checking grounding…") appear live. Simpler than WebSockets. |
| **pydantic-settings** | Loads config from env vars / `.env` into a typed object. | One validated source of truth for every setting. |
| **React** | A JavaScript library for building UIs from *components*, which are reusable pieces of UI that re-render when their *state* changes. | The industry-standard frontend. It gives full control over the chat UX: streaming text, citations, status steps, a stop button. |
| **Vite** | A frontend build tool and dev server. | Instant reloads while coding. `npm run build` turns React code into small static files. Its dev proxy forwards `/api` to the Python backend. |
| **react-markdown** | Renders Markdown as React elements. | LLM answers are Markdown (lists, code, bold). This renders them **safely**, with no raw HTML injection. |
| **Vitest + React Testing Library** | Test runner and helpers that render components the way a user sees them. | Lets us test the SSE parser and UI behaviour without a browser. |
| **nginx** | A small, fast web server and reverse proxy. | In production it serves the built React files and forwards `/api` to the backend with buffering off, so tokens still stream. |
| **MLflow Tracing** | Records each request as a tree of spans (node → LLM call → retrieval) with inputs, outputs, timings, tokens. | You cannot debug an agent you cannot see. Autologging for LangChain/LangGraph = near-zero code. |
| **structlog** | Structured (JSON) logging. | Logs that machines can search; every line carries `request_id` / `session_id`. |
| **Docker Compose** (via Rancher Desktop) | Runs all services together from one YAML file. | `docker compose up -d` = whole system, same on any machine. |
| **DeepEval** (stretch) | Evaluation framework with LLM-judge metrics (faithfulness, hallucination, answer relevancy, bias). | Measure quality with numbers, catch regressions. |
| **n8n** (stretch, optional) | Visual workflow automation. | e.g., "new file in folder → call /ingest", "nightly eval → notify". |

---

## 3. Folder structure (final)

```
.
├── CLAUDE.md  PLAN.md  MEMORY.md  GLOSSARY.md  SETUP.md
├── requirements.txt  .env.example  pyproject.toml  .gitignore  .dockerignore
├── docker-compose.yml
├── docker/
│   ├── api.Dockerfile
│   ├── frontend.Dockerfile        # stage 1: node builds React; stage 2: nginx serves it
│   └── postgres-init.sql          # creates app DB objects on first start
├── app/
│   ├── __init__.py
│   ├── config.py                  # Settings
│   ├── logging_setup.py
│   ├── main.py                    # create_app(), lifespan: pools, models, graph
│   ├── cli.py                     # `python -m app.cli ingest <path|repo-url>`
│   ├── api/
│   │   ├── schemas.py             # Pydantic request/response models
│   │   ├── routes_health.py       # /health (liveness), /ready (dependencies)
│   │   ├── routes_ingest.py       # /api/ingest/files, /api/ingest/github, /api/jobs/{id}, /api/documents
│   │   └── routes_chat.py         # /api/chat (SSE), /api/sessions, /api/sessions/{id}/history
│   ├── db/
│   │   ├── pool.py                # psycopg async connection pool
│   │   ├── schema.sql             # documents, ingest_jobs, sessions
│   │   └── repositories.py        # small SQL functions per table
│   ├── ingestion/
│   │   ├── models.py              # Document, Chunk dataclasses
│   │   ├── loaders.py             # file → markdown text + metadata
│   │   ├── github.py              # shallow clone, file filters, size limits
│   │   ├── chunking.py            # markdown-header + recursive + code-aware splitting
│   │   └── pipeline.py            # load → chunk → dedup → embed → upsert → registry
│   ├── retrieval/
│   │   ├── embeddings.py          # dense + sparse FastEmbed wrappers (loaded once)
│   │   ├── vectorstore.py         # Qdrant collection setup, upsert, hybrid query
│   │   ├── reranker.py            # cross-encoder rerank
│   │   └── retriever.py           # retrieve(query) → reranked chunks
│   ├── agent/
│   │   ├── llm.py                 # ChatOllama factories (generator / judge)
│   │   ├── prompts.py             # every prompt template
│   │   ├── state.py               # AgentState TypedDict + structured-output schemas
│   │   ├── nodes.py               # route, retrieve, grade, rewrite, generate, grounding
│   │   └── graph.py               # builds + compiles the StateGraph with checkpointer
│   ├── memory/
│   │   └── checkpointer.py        # AsyncPostgresSaver setup, history trimming
│   └── observability/
│       └── tracing.py             # mlflow autolog, request-id middleware
├── frontend/                      # React (JavaScript) + Vite
│   ├── package.json  package-lock.json
│   ├── vite.config.js             # React plugin, dev proxy /api → localhost:8000, Vitest config
│   ├── eslint.config.js  .prettierrc  index.html
│   ├── nginx.conf                 # prod: static files + /api reverse proxy (proxy_buffering off)
│   └── src/
│       ├── main.jsx               # entry point: mounts <App/>
│       ├── App.jsx                # layout: sidebar + chat / ingest views
│       ├── api/
│       │   ├── client.js          # fetch wrappers: sessions, history, ingest, jobs, documents
│       │   └── sse.js             # parses an SSE stream from a fetch() body into events
│       ├── hooks/
│       │   ├── useChatStream.js   # send message, consume stream, stop, errors
│       │   ├── useSessions.js     # list / create / switch sessions
│       │   └── useIngestJobs.js   # upload, add repo, poll job status
│       ├── components/
│       │   ├── SessionSidebar.jsx  ChatWindow.jsx  MessageBubble.jsx  ChatInput.jsx
│       │   ├── StatusSteps.jsx  SourceList.jsx  GroundingBadge.jsx  IngestPanel.jsx
│       │   └── *.module.css       # one CSS Module per component
│       └── test/setup.js          # jest-dom matchers for Vitest
├── evals/
│   ├── datasets/golden.jsonl      # question, expected answer, expected source
│   ├── retrieval_eval.py          # hit@k, MRR (no LLM needed)
│   └── llm_eval.py                # DeepEval: faithfulness, hallucination, relevancy, bias
├── n8n/workflows/                 # exported workflow JSON
├── data/sample_docs/              # tiny PDF, DOCX, MD, TXT for tests/demos
└── tests/
    ├── conftest.py
    ├── unit/
    └── integration/
```

---

## 4. Build sessions

Each session ≈ 2–4 hours. Every session starts with the mentor's plan and waits for **"go"**
(see `CLAUDE.md` §6).

### Session 1 — Foundations & local infrastructure
- **Goal:** A clean project skeleton: venv, config, logging, a FastAPI app with `/health` and `/ready`, and Qdrant + Postgres + Ollama + MLflow running in Docker. `/ready` proves the API can reach each one.
- **Files:** `pyproject.toml` (ruff/pytest config), `.gitignore`, `.dockerignore`, `docker-compose.yml` (infra services only: qdrant, postgres, ollama, mlflow + volumes + healthchecks), `app/__init__.py`, `app/config.py`, `app/logging_setup.py`, `app/main.py`, `app/api/routes_health.py`, `tests/conftest.py`, `tests/unit/test_config.py`, `tests/integration/test_ready.py`.
- **Concepts:** virtual environments; env vars & 12-factor config; Docker images/containers/volumes/ports; healthchecks; FastAPI app factory & lifespan; structured logging; liveness vs readiness; `git init` + first commit.
- **Definition of done:** `docker compose ps` shows 4 healthy services; `ollama pull` of both models done inside the container; `uvicorn app.main:app` runs; `GET /health` → 200; `GET /ready` → 200 with each dependency `ok`; `pytest` and `ruff check` pass; first git commit made.
- **Homework:** Stop Postgres (`docker compose stop postgres`) and call `/ready` — explain what you see. Read FastAPI "First Steps" + "Settings and Environment Variables".

### Session 2 — Document loading & chunking
- **Goal:** Turn any PDF/MD/TXT/DOCX into clean, metadata-rich chunks.
- **Files:** `app/ingestion/models.py`, `app/ingestion/loaders.py`, `app/ingestion/chunking.py`, `data/sample_docs/*`, `tests/unit/test_loaders.py`, `tests/unit/test_chunking.py`.
- **Concepts:** why chunking matters; chunk size & overlap trade-offs; Markdown-header splitting (keeps section titles as context); metadata (source, page/section, chunk index); content hashing for dedup; handling bad/empty/scanned files.
- **Definition of done:** each sample file → list of `Chunk`s with `text`, `source`, `section`, `chunk_index`, `content_hash`; chunk sizes within limits; unit tests cover all 4 formats + an empty file + an unsupported type.
- **Homework:** Change chunk size (e.g., 300 vs 1200 tokens) on one doc and write down how chunks differ. Which would you rather read to answer a question?

### Session 3 — Embeddings & indexing in Qdrant
- **Goal:** Embed chunks (dense + sparse) and store them in Qdrant; keep a document registry in Postgres so re-ingesting the same file is skipped.
- **Files:** `app/retrieval/embeddings.py`, `app/retrieval/vectorstore.py`, `app/db/pool.py`, `app/db/schema.sql`, `app/db/repositories.py`, `app/ingestion/pipeline.py`, `app/cli.py`, `tests/unit/test_embeddings.py`, `tests/integration/test_indexing.py`.
- **Concepts:** embeddings & cosine similarity; dense vs sparse vectors; Qdrant collections, named vectors, payloads, payload indexes; idempotent upserts (deterministic point IDs); batching; loading models once at startup; connection pools.
- **Definition of done:** `python -m app.cli ingest data/sample_docs` indexes all docs; re-running reports "skipped (unchanged)"; Qdrant dashboard (`localhost:6333/dashboard`) shows points with both vectors; `documents` table lists each file; tests pass.
- **Homework:** In the Qdrant dashboard, find one chunk and look at its payload. Embed two sentences that mean the same thing and two that don't; compare cosine similarities in a Python shell.

### Session 4 — Hybrid retrieval, reranking & measuring retrieval
- **Goal:** `retrieve(query)` returns the best 5 chunks using dense+BM25 → RRF → cross-encoder rerank, and we can *measure* it.
- **Files:** `app/retrieval/reranker.py`, `app/retrieval/retriever.py`, `evals/datasets/golden.jsonl` (≈15 Q→source pairs on sample docs), `evals/retrieval_eval.py`, `tests/unit/test_retriever.py`.
- **Concepts:** BM25 intuition; why hybrid beats either alone; RRF formula; bi-encoder vs cross-encoder; top-k funnels (20 → 5); hit@k and MRR; metadata filters.
- **Definition of done:** `python -m evals.retrieval_eval` prints hit@5 and MRR for dense-only, sparse-only, hybrid, hybrid+rerank; hybrid+rerank is best or equal; rerank latency logged (< ~1 s for 20 chunks on your CPU).
- **Homework:** Add 5 of your own questions to `golden.jsonl` — include one with an exact keyword (e.g., an error code) and see which method finds it.

### Session 5 — GitHub repo ingestion & the ingestion API
- **Goal:** Ingest a public GitHub repo, and expose ingestion over HTTP with background jobs.
- **Files:** `app/ingestion/github.py`, updates to `chunking.py` (code-aware splitting) and `pipeline.py`, `app/api/schemas.py`, `app/api/routes_ingest.py`, `tests/unit/test_github_filters.py`, `tests/integration/test_ingest_api.py`.
- **Concepts:** shallow clones; allow-lists (extensions) and deny-lists (`node_modules`, binaries, lockfiles); file size limits; language-aware splitting; background tasks & job status polling; file uploads (multipart); input validation; untrusted content.
- **Definition of done:** `POST /ingest/github {"url": "https://github.com/<small-public-repo>"}` returns a `job_id`; `GET /jobs/{id}` goes `queued → running → succeeded` with counts; `POST /ingest/files` accepts an upload; `GET /documents` lists everything; Swagger UI at `/docs` works.
- **Homework:** Ingest a small repo you know. Ask yourself 3 questions about it and check (via the retrieval CLI) whether the right files come back.

### Session 6 — LLM, baseline RAG & tracing
- **Goal:** Connect Ollama; build a simple *non-agentic* RAG answer (retrieve → generate with citations) as a baseline; trace everything in MLflow.
- **Files:** `app/agent/llm.py`, `app/agent/prompts.py`, `app/observability/tracing.py`, a temporary `/chat/simple` route, `tests/unit/test_prompts.py`.
- **Concepts:** chat messages & roles; system prompts; context window & `num_ctx`; temperature; citations; "answer only from context" + prompt-injection defence; disabling "thinking" for speed; traces & spans; latency budgets on CPU.
- **Definition of done:** `/chat/simple` answers a sample-doc question with correct `[n]` citations; the MLflow UI (`localhost:5000`) shows one trace per request with retrieval and LLM spans, inputs, outputs and timings; measured tokens/sec recorded in `MEMORY.md`.
- **Homework:** Ask a question your docs *can't* answer. Does it refuse or make something up? Save the trace link. Session 7 fixes this problem. **React prep (30–45 min):** react.dev → "Quick Start" and "Tutorial: Tic-Tac-Toe".

### Session 7 — The agentic loop (LangGraph)
- **Goal:** Replace the baseline with the full graph: route → retrieve → grade → rewrite → generate → grounding check, with bounded retries.
- **Files:** `app/agent/state.py`, `app/agent/nodes.py`, `app/agent/graph.py`, prompt additions, `tests/unit/test_nodes.py` (LLM mocked), `tests/unit/test_graph_paths.py`.
- **Concepts:** state machines; LangGraph `StateGraph`, nodes, conditional edges, reducers; structured outputs with Pydantic + Ollama JSON schema; LLM-as-judge; loop guards; fallbacks when the model returns junk; testing agents with fake LLMs.
- **Definition of done:** unit tests cover all 4 paths (direct, normal RAG, rewrite-then-answer, give-up-honestly) with a fake LLM; the Session 6 "unanswerable" question now gets an honest refusal; MLflow trace shows each node; graph diagram exported (`graph.get_graph().draw_mermaid()`) into `PLAN.md`.
- **Homework:** Draw the graph on paper from memory. Then find in the trace where the grader removed an irrelevant chunk. **React prep:** react.dev → "Thinking in React" and "Describing the UI".

### Session 8 — Persistent memory & the streaming chat API
- **Goal:** Per-session conversation memory in Postgres that survives restarts; a streaming `/chat` endpoint.
- **Files:** `app/memory/checkpointer.py`, `app/api/routes_chat.py`, schema additions (`sessions` table), `tests/integration/test_chat_stream.py`, `tests/integration/test_memory_persistence.py`.
- **Concepts:** threads & checkpoints; why memory ≠ the vector store; trimming history to fit the context window; follow-up question condensing ("what about its price?"); SSE event types (`status`, `token`, `sources`, `grounding`, `done`, `error`); async generators; client disconnects; Windows event-loop gotcha for psycopg async.
- **Definition of done:** `curl -N` to `/api/chat` shows streamed events. A follow-up that needs the previous turn is answered correctly. **Restart the API container/process → the same session still remembers.** `GET /api/sessions/{id}/history` returns the transcript. Tests pass. The SSE event format is written down in `PLAN.md` as the contract the React app will rely on.
- **Homework:** Inspect the `checkpoints` tables in Postgres (`docker compose exec postgres psql ...`). What exactly gets stored per turn? **React prep:** react.dev → "Managing State" and "Synchronizing with Effects".

### Session 9 — React chat UI (may span two sittings)
- **Goal:** A React single-page app built with Vite. It has a session sidebar (new chat, switch chats), live streaming tokens, step-by-step status ("retrieving…", "checking grounding…"), Markdown answers with clickable `[n]` citations and expandable source snippets, a verified/unverified badge, a Stop button, and an Ingest view (upload files, add a GitHub repo, watch job progress).
- **Files:**
  - Project setup: `frontend/package.json` + `package-lock.json`, `frontend/vite.config.js`, `frontend/eslint.config.js`, `frontend/.prettierrc`, `frontend/index.html`.
  - App code: `frontend/src/main.jsx`, `frontend/src/App.jsx`, `frontend/src/api/client.js`, `frontend/src/api/sse.js`, `frontend/src/hooks/*.js`, `frontend/src/components/*.jsx` with matching `.module.css`.
  - Tests: `frontend/src/test/setup.js`, `frontend/src/api/sse.test.js`, `frontend/src/components/*.test.jsx`.
- **Concepts:**
  - Tooling: Node, npm, `package.json` vs lockfile; the Vite dev server and proxy; same-origin vs CORS.
  - React basics: components, JSX, props; `useState` / `useReducer`; effects and cleanup; custom hooks; lifting state up; keys in lists.
  - Streaming: `fetch` + `ReadableStream` + `TextDecoder`; why `EventSource` can't POST; `AbortController` for the Stop button.
  - Safety and quality: rendering untrusted Markdown safely; CSS Modules; testing behaviour with Vitest + Testing Library.
- **Definition of done:**
  - `npm run dev` serves the app at `localhost:5173`, talking to the local API.
  - In the browser you can: upload a PDF; ingest a repo and watch its job status; ask questions and see tokens stream with status steps; expand sources; see verified/unverified; stop a generation mid-stream; switch sessions; reload the page and still see the history (loaded from the API).
  - `npm run lint`, `npm test` and `npm run build` pass.
  - The SSE parser has unit tests, including events split across network chunks.
- **Homework:** Open browser DevTools → Network, ask one question, and identify each SSE event in the stream. Show the app to someone non-technical and write down the first 3 things that confused them.

### Session 10 — One-command deployment & hardening
- **Goal:** `docker compose up -d` starts the *entire* system (api, frontend, qdrant, postgres, ollama, mlflow) from a clean machine, with production basics in place.
- **Files:** `docker/api.Dockerfile`, `docker/frontend.Dockerfile` (stage 1 `node:24.22.0-alpine` runs `npm ci && npm run build`; stage 2 `nginx:1.30.6-alpine` serves `dist/`), `frontend/nginx.conf` (SPA fallback, `/api` proxy with `proxy_buffering off`, long read timeout, security headers), `docker/postgres-init.sql`, final `docker-compose.yml` (healthchecks, `depends_on: condition: service_healthy`, restart policies, memory limits, model-pull init job), `README.md` (owner-approved), `tests/integration/test_smoke.py`.
- **Concepts:** multi-stage builds & slim images; serving a React build behind a reverse proxy; non-root containers; `npm audit`; baking embedding models into the image; service dependency ordering; resource limits on a 16 GB laptop; secrets via env; backups of volumes; what "production-credible" means (and what's still missing: auth, TLS, scaling).
- **Definition of done:** `docker compose down -v` then `docker compose up -d` → all services healthy. The app at `localhost:8080` works end-to-end, and tokens arrive progressively through nginx rather than all at once. The smoke test (ingest sample docs → ask → streamed, cited, grounded answer) passes against the containers; restart survives with memory + index intact; total RAM within budget (≈ ≤ 9 GB).
- **Homework:** Write in your own words, in `MEMORY.md`, how a message travels from the browser to Ollama and back.

### Stretch A — Evaluation: hallucination, accuracy, bias
- **Goal:** Automated quality report. Retrieval metrics (from Session 4) + DeepEval LLM-judge metrics (faithfulness, hallucination, answer relevancy, bias) on the golden set; results logged to MLflow as an experiment run so changes can be compared.
- **Files:** `evals/llm_eval.py`, expanded `evals/datasets/golden.jsonl` (≥30 items incl. unanswerable + bias-probe questions), uncomment `deepeval` in `requirements.txt`.
- **Concepts:** golden datasets; LLM-as-judge and its limits (small local judges are noisy); faithfulness vs correctness; bias probes; regression testing.
- **DoD:** one command produces a table of scores and an MLflow run; a deliberate regression (e.g., disabling the reranker) shows a measurable drop.

### Stretch B — n8n workflows (owner must accept n8n's licence first)
- **Goal:** n8n as an optional compose profile (`docker compose --profile n8n up -d`) with 2 workflows: (1) watch a folder / form upload → call `/ingest/files`; (2) nightly schedule → run eval → write summary.
- **Files:** compose profile, `n8n/workflows/*.json`, small `/hooks/*` endpoints if needed (API-key protected).
- **Concepts:** webhooks; event-driven automation; API keys; idempotency.
- **DoD:** both workflows import cleanly from the JSON files and run end-to-end.
- **OSI-licensed alternative if preferred:** Node-RED (Apache-2.0) — ask before switching.

---

## 5. Key design decisions

| # | Decision | Why | Trade-off accepted |
|---|---|---|---|
| D1 | **Fully local LLM via Ollama**, no API keys | Free, private, meets the rules | Slower & less capable than hosted frontier models (expect ~5–15 s/answer on CPU) |
| D2 | **Two model sizes** (2B judge/router, 4B generator) | Most agent steps are classification; small model halves their latency | Two models in RAM (~5.5 GB); configurable to use one |
| D3 | **Disable "thinking" mode** on Qwen | Thinking tokens on CPU can add 30+ s | Slightly weaker reasoning on hard questions |
| D4 | **FastEmbed/ONNX instead of PyTorch** | Small install, fast on CPU, no Windows torch pain | Fewer model choices than sentence-transformers |
| D5 | **Hybrid search + RRF inside Qdrant** | One query, no score normalisation code, robust | Need two vectors per chunk (more storage — trivial here) |
| D6 | **Rerank top-20 → top-5** | Precision where it matters, bounded CPU cost | +0.3–1 s per query |
| D7 | **Batched grading** (one LLM call grades all 5 chunks) | 1 call instead of 5 on CPU | Slightly less reliable than per-chunk grading |
| D8 | **Bounded loops** (max 2 rewrites, 1 regeneration) | Prevents runaway latency and infinite loops | Some hard questions end in "not found" |
| D9 | **Stream first, verify after**: tokens stream live; grounding verdict arrives as a final event; UI shows *verified/unverified* badge | Good UX on slow hardware; honest | User may briefly read text that later gets an *unverified* badge |
| D10 | **Postgres for memory (LangGraph checkpointer)** + app tables | One durable DB; survives restarts; standard | One more container than SQLite would need |
| D11 | **MLflow Tracing instead of Langfuse** | Langfuse v3 self-host needs Postgres+ClickHouse+Redis+MinIO (~16 GB recommended) — too heavy beside a local LLM on 16 GB. MLflow: one container, Apache-2.0, LangGraph autolog | Less polished LLM-specific UI than Langfuse; upgrade path exists via OpenTelemetry |
| D12 | **MLflow server uses SQLite on a volume** (not Postgres) | Stock image, no extra DB driver or second database to manage; SQLite is fine for one user | Not for multi-user scale |
| D13 | **React SPA (built by Vite, served by nginx) that only talks HTTP under `/api`** (owner decision, replaces Streamlit) | Industry-standard frontend with full UX control. Vite is the current standard React build tool (Create React App is deprecated). The same-origin `/api` proxy means no CORS setup and no hard-coded hosts. The backend stays reusable by n8n and curl | A second language and toolchain (Node/npm) to learn; more code than Streamlit |
| D14 | **MarkItDown → Markdown → header-aware chunks** | One parser for all formats, structure preserved | No OCR: scanned PDFs yield little text (flagged per document) |
| D15 | **Background ingestion jobs in the API process** (FastAPI background tasks + `ingest_jobs` table) | No extra queue service (Celery/Redis) to learn/run | Jobs lost if API dies mid-ingest (status shows `failed`; re-run is idempotent) |
| D16 | **Deterministic chunk IDs + content hashes** | Re-ingesting is safe and cheap | Changing chunking settings requires a re-index |
| D17 | **pip + venv, Python 3.12** (not 3.14) | Every dependency ships Windows wheels for 3.12 (verified) | Need a second Python install alongside your 3.14 |
| D18 | **Rancher Desktop** for Docker on Windows | Apache-2.0, includes `docker` + `docker compose` with the moby engine | Docker Desktop is easier for some but is proprietary (free only for personal/small business) — ask before switching |
| D19 | **JavaScript, not TypeScript**, for the frontend | Owner asked for React JS; fewer new concepts at once | Fewer compile-time checks; JSDoc + tests compensate; TS migration possible later (ask) |
| D20 | **Hand-written SSE parser over `fetch`** (no helper library) | Browser `EventSource` can't send POST bodies; the popular helper library is no longer maintained; ~40 lines and educational | We own edge cases (split chunks, multi-line `data:`) — covered by unit tests |
| D21 | **Plain CSS Modules, no UI kit; React state + custom hooks, no state library** | Fewer dependencies and concepts; enough for one chat app | More hand-written CSS; revisit only if the UI grows |

---

## 6. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **CPU latency** (agent = 3–5 LLM calls) | Slow answers (10–30 s) | Small judge model, thinking off, batched grading, `num_ctx` 8192, bounded loops, streaming + progress events, keep models loaded (`OLLAMA_KEEP_ALIVE`) |
| **RAM pressure** (16 GB total) | Swapping, crashes | Budget: Ollama ~5.5 GB, API ~1 GB, others ~1.5 GB; WSL memory cap via `.wslconfig`; compose memory limits; never run native Ollama *and* container Ollama at the same time with models loaded |
| **Small models return invalid JSON** | Router/grader/grounding crash | Ollama `format=<JSON schema>`, Pydantic validation, 1 retry, safe default (e.g., treat as "relevant" / "unverified") |
| **psycopg async on Windows** (needs selector event loop; Uvicorn on Windows uses Proactor) | Memory/DB errors in local dev | Set `WindowsSelectorEventLoopPolicy` in the dev entrypoint; containers (Linux) are unaffected — addressed in Session 8 |
| **Python 3.14 is your default** | Some wheels missing/behaviour changes | Use a dedicated Python 3.12 venv (SETUP.md) |
| **Prompt injection** from ingested docs/repos | Model follows malicious instructions in content | Context wrapped in delimiters + "content is data, not instructions" system prompt; never execute repo code; grounding check |
| **Scanned PDFs / images** | Empty or tiny text | Detect low text-per-page, mark document `needs_ocr` (OCR out of scope; ask before adding) |
| **Large GitHub repos** | Slow ingest, disk/RAM blow-up | Shallow clone, extension allow-list, max file size, max files, timeout |
| **First-run downloads** (models ~4.5 GB LLM + ~200 MB embedding) | Long first start | Documented in SETUP; model-pull init step; embedding models baked into API image in Session 10 |
| **Grounding judge is itself an LLM** | False passes/fails | Treat as signal, not proof; show *unverified* honestly; measure in Stretch A |
| **Fast-moving libraries** (LangGraph, React tooling: Vite, ESLint) | Breaking changes | Exact pins; upgrade deliberately, one at a time, with tests |
| **n8n licence** (fair-code, not OSI) | Conflicts with "open source only" rule | Optional profile; owner decision before Stretch B; Node-RED alternative |
| **nginx buffers the SSE stream** | Tokens appear all at once at the end | `proxy_buffering off`, `X-Accel-Buffering: no` header from the API, long `proxy_read_timeout`; verified in Session 10 DoD |
| **Two languages for a beginner** (Python + JavaScript) | Session 9 is the steepest | React prep homework in Sessions 6–8; Session 9 may take two sittings; strict folder rules keep the UI simple |
| **npm supply-chain risk** | Compromised package | Few dependencies, exact pins, committed lockfile, `npm ci`, `npm audit` in Session 10 |
| **No auth / TLS** | Not safe on a public network | Explicitly local-only in this plan; API key + reverse proxy listed as future work |

---

## Appendix — Stack comparison tables

Rules applied: free & OSS · pip or docker compose · Windows laptop, no GPU · simplest production-credible · actively maintained.

**LLM runtime**

| Option | CPU-friendly | Setup on Windows | API | Notes |
|---|---|---|---|---|
| **Ollama** ✅ | Yes (llama.cpp inside) | Installer or one container | REST + OpenAI-compatible | Biggest model library, JSON-schema outputs |
| llama.cpp server | Yes | Manual builds/flags | OpenAI-compatible | More knobs, more friction |
| LocalAI | Yes | Container | OpenAI-compatible | Heavier, more moving parts |
| vLLM | Poor without GPU | Linux-centric | OpenAI-compatible | Built for GPUs |

**LLM model (CPU, ≤ ~4 GB RAM)**

| Option | Size | Strength | Notes |
|---|---|---|---|
| **qwen3.5:4b** ✅ (generator) | ~3.4 GB | Strong instruction following/JSON for size | Current-gen; thinking can be disabled |
| **qwen3.5:2b** ✅ (judge) | ~1.9 GB | Fast classification | Good enough for route/grade |
| qwen3:8b (you have it) | 5.2 GB | Better answers | ~2× slower on your CPU; can swap in via `.env` |
| llama3.2:3b | 2.0 GB | Solid, older | Weaker structured output than Qwen3.5 |
| gemma4:31b (you have it) | 20 GB | Strong | Won't fit in 16 GB RAM — do not use |

**Agent orchestration**

| Option | Loops/branches | Persistence | Learning curve | Notes |
|---|---|---|---|---|
| **LangGraph** ✅ | Native graph, cycles | Built-in checkpointers (Postgres) | Medium | De-facto standard for agentic RAG |
| LlamaIndex Workflows | Yes (events) | Manual | Medium | Great for RAG, memory persistence less turnkey |
| Haystack 2 | Pipelines + loops | Manual | Medium | Solid, smaller agent ecosystem |
| Plain Python | Anything | DIY | Low at first | You'd re-invent state, retries, tracing hooks |
| CrewAI | Role-based agents | Limited | Low | Multi-agent focus; overkill/less control |

**Vector database**

| Option | Hybrid (dense+sparse) | Ops | Notes |
|---|---|---|---|
| **Qdrant** ✅ | Native, RRF/DBSF fusion server-side | 1 small container | Payload filters, great dashboard |
| pgvector | Dense only (BM25 via extra ext/DIY) | Reuse Postgres | Fewer containers, but hybrid is DIY |
| Chroma | Limited sparse support | Embedded/server | Simple, weaker for production hybrid |
| Weaviate | Native hybrid | Heavier | More features than needed |
| Milvus | Native hybrid | Several containers | Built for very large scale |

**Embeddings & reranking runtime**

| Option | Runtime | Install size | Notes |
|---|---|---|---|
| **FastEmbed** ✅ | ONNX (CPU) | ~200 MB | Dense, sparse (BM25/SPLADE) and cross-encoders in one lib; by Qdrant |
| sentence-transformers | PyTorch | 1–2 GB | Most models, heavy on Windows CPU |
| Ollama embeddings | llama.cpp | none extra | Competes with the LLM for CPU; no sparse/rerank |

**Document parsing**

| Option | Formats | Weight | Licence | Notes |
|---|---|---|---|---|
| **MarkItDown** ✅ | PDF, DOCX, PPTX, XLSX, HTML… → Markdown | Light | MIT | One API, structure kept |
| Docling | Excellent layout/tables | Heavy (torch models) | MIT | Slow on CPU; future upgrade for complex PDFs |
| Unstructured | Many | Heavy | Apache-2.0 | Many system deps |
| PyMuPDF | PDF only | Light | **AGPL** | Licence obligations — avoided |
| pypdf + python-docx | PDF / DOCX | Light | BSD/MIT | More glue code |

**Memory / persistence**

| Option | Survives restart | Ops | Notes |
|---|---|---|---|
| **LangGraph PostgresSaver** ✅ | Yes | Postgres container (also used for app tables) | Production-standard |
| LangGraph SqliteSaver | Yes | None | Simple, but single-writer file; less "production" |
| Redis | Yes (with AOF) | Extra container | Another system to learn |
| In-memory | No | None | Fails the requirement |

**API & streaming**

| Option | Async/streaming | Docs | Notes |
|---|---|---|---|
| **FastAPI + SSE** ✅ | Yes | Auto OpenAPI | Industry standard for Python ML APIs |
| Flask | Bolt-on | Manual | Sync-first |
| Django + DRF | Heavier | Good | Too much framework for this |
| LangServe | Yes | Auto | Maintenance mode — avoid |

**Web UI** (owner decision: React)

| Option | Effort | Streaming | Notes |
|---|---|---|---|
| **React (JS) + Vite** ✅ | Medium–high | `fetch` + ReadableStream | Industry standard, full UX control; owner's choice |
| Streamlit | Low (pure Python) | `st.write_stream` | Original pick; replaced at owner's request |
| Gradio | Low | Yes | Frequent breaking changes |
| Chainlit | Low | Yes | Original team stepped back in 2025; community-maintained |
| Open WebUI | None (ready-made) | Yes | Heavy; built for its own backend; licence has branding clause |

**React build tooling**

| Option | Status | Notes |
|---|---|---|
| **Vite** ✅ | Actively maintained, React docs' recommended build tool for client-side apps | Fast dev server, built-in proxy, simple config |
| Create React App | Deprecated (2025) | Do not use |
| Next.js | Active | A full server framework; we already have a Python backend, so it's overkill and blurs the boundary |
| Parcel / Rsbuild | Active | Fine, smaller ecosystems |

**Frontend serving in production**

| Option | Notes |
|---|---|
| **nginx** ✅ | Tiny image, serves static files, reverse-proxies `/api` with streaming support |
| Caddy | Also great (automatic HTTPS); slightly less common in tutorials |
| FastAPI `StaticFiles` | Fewer containers, but mixes frontend and backend deploys |

**Tracing / observability**

| Option | Self-host footprint | Licence | Notes |
|---|---|---|---|
| **MLflow Tracing** ✅ | 1 container (SQLite) | Apache-2.0 | LangGraph autolog, also does eval runs |
| Langfuse v3 | Postgres + ClickHouse + Redis + MinIO + 2 app containers (~16 GB recommended) | MIT (core) | Best LLM UX; too heavy for this laptop |
| Arize Phoenix | 1 container | **Elastic License 2.0** (source-available, not OSI) | Fails "open source" rule |
| OpenTelemetry + Jaeger | 1–2 containers | Apache-2.0 | Generic; no LLM-aware views |
| Opik | Several containers | Apache-2.0 | Similar weight to Langfuse |

**Containers on Windows**

| Option | Licence | Notes |
|---|---|---|
| **Rancher Desktop (dockerd/moby)** ✅ | Apache-2.0 | GUI + `docker`/`docker compose` CLI |
| Docker Engine inside WSL2 | Apache-2.0 | OSS, but manual Linux setup |
| Podman Desktop | Apache-2.0 | `podman compose` quirks with some compose features |
| Docker Desktop | Proprietary (free for personal/small biz) | Easiest, but not open source |

**Evaluation (stretch)**

| Option | Hallucination/faithfulness | Bias | Local judge (Ollama) | Licence |
|---|---|---|---|---|
| **DeepEval** ✅ | Yes | Yes (BiasMetric) | Yes | Apache-2.0 |
| Ragas | Yes | No built-in | Yes (via wrappers) | Apache-2.0 |
| MLflow GenAI eval | Yes | Custom judges | Via LiteLLM | Apache-2.0 |

**Workflow automation (stretch)**

| Option | Licence | Notes |
|---|---|---|
| **n8n** (requested) | Sustainable Use (fair-code, not OSI) | Best UX, huge node library — owner to confirm |
| Node-RED | Apache-2.0 | OSI alternative, IoT-flavoured but capable |
| Activepieces | MIT (community edition) | Newer, Zapier-like |
