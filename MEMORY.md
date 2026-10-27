# MEMORY.md — Session Log

Project memory across sessions. Newest entry at the bottom. At the end of every session,
append an entry using the template. At the start of every session, read the latest entry.

**Template**

```
## Session N — <title> (YYYY-MM-DD)
**Done:** what was built / changed (files)
**Verified:** commands run + results (tests, health checks, measurements)
**Decisions:** anything decided or changed, and why (link PLAN.md decision ids)
**Learned:** concepts the owner learned / new glossary terms
**Open issues:** bugs, TODOs, questions for the owner
**Next:** first step of the next session
```

---

## Session 0 — Planning & stack selection (2026-10-20)

**Done:**
- Repo was empty. Created the planning docs only, with no application code: `CLAUDE.md`, `PLAN.md`, `MEMORY.md`, `GLOSSARY.md`, `SETUP.md`, `requirements.txt`, `.env.example`.

**Machine facts (checked):**
- Windows 11 Home, Intel Core 7 150U (12 threads), 15.7 GB RAM, no GPU.
- Python 3.14.7 is the default. **We will use a separate Python 3.12 venv** (D17).
- Git 2.55 is installed. Ollama 0.40.6 runs natively, with models `qwen3:8b` and `gemma4:31b` already pulled. gemma4:31b is too large for this RAM.
- Docker is **not installed** yet. Rancher Desktop is planned (D18).

**Verified:**
- Every pinned Python version exists on PyPI. The full `requirements.txt` set resolves for **Python 3.12 / win_amd64 using wheels only** (pip dry-run, no conflicts). The stretch `deepeval==4.3.1` also resolves alongside it.
- These Docker image tags exist: `qdrant/qdrant:v1.19.2`, `postgres:17.11`, `ollama/ollama:0.40.6`, `ghcr.io/mlflow/mlflow:v3.17.1`, `n8nio/n8n:2.45.0`.
- The Ollama library has `qwen3.5:4b` and `qwen3.5:2b`.
- The `mlflow-tracing` package includes LangChain/LangGraph autologging, so the full `mlflow` package isn't needed in the app.

**Decisions:** Stack locked in `CLAUDE.md` §3. Key calls:
- MLflow is the tracing tool instead of Langfuse, because Langfuse is too heavy for 16 GB (D11).
- Two Qwen3.5 model sizes: 2B for routing and judging, 4B for answers (D2).
- FastEmbed/ONNX instead of PyTorch (D4).
- Hybrid search with RRF inside Qdrant (D5).
- Postgres for memory (D10).
- Answers stream first and are verified afterwards (D9).

**Open issues / owner decisions pending:**
1. Before Stretch B, confirm you accept the n8n licence (fair-code, not OSI open source), or choose Node-RED instead.
2. Rancher Desktop is planned. If you'd rather use Docker Desktop (proprietary, free for personal use), say so.
3. Work through `SETUP.md` Part A before Session 1.

**Learned:** the overall architecture and the role of each component (see `PLAN.md` §2).

**Next:** Session 1, Foundations & local infrastructure. Start it with the prompt Claude gave at the end of Session 0.

---

## Session 0b — Stack change: React frontend (2026-10-20)

**Done:**
- The owner decided **the backend is Python and the frontend is React (JavaScript)**. Streamlit is removed.
- Updated `CLAUDE.md`: rule 10, the stack table, the folder layout, frontend coding standards, and the commands.
- Updated `PLAN.md`:
  - the diagram, the request flow, the components table and the folder tree;
  - Session 9 rewritten as "React chat UI", and Session 10 now uses an nginx frontend container;
  - React prep homework added to Sessions 6–8;
  - decisions D13 (revised) and D19–D21 added, plus 3 new risks and the appendix tables.
- Also updated `SETUP.md` (Node.js step A6, frontend dev Part C), `GLOSSARY.md` (a Frontend section), `requirements.txt` (streamlit removed) and `.env.example`.

**Verified:**
- Node 22.23.2 and npm 10.9.8 are installed.
- The current Node LTS is 24.22.0.
- An `npm install --dry-run` with the pinned set found **no peer-dependency conflicts**. The set is: react/react-dom 19.3.1, vite 8.3.4, @vitejs/plugin-react 6.1.2, react-markdown 10.1.0, remark-gfm 4.0.1, vitest 5.0.5, @testing-library/react 16.3.3, @testing-library/jest-dom 7.0.1, jsdom 30.1.3, eslint 10.13.0, @eslint/js 10.0.1, eslint-plugin-react-hooks 7.1.1, eslint-plugin-react-refresh 0.5.7, globals 17.13.0, prettier 3.9.10.
- Images `node:24.22.0-alpine` and `nginx:1.30.6-alpine` exist.

**Decisions:**
- Vite rather than Create React App, which is deprecated.
- JavaScript rather than TypeScript (D19).
- A hand-written SSE parser over `fetch` (D20).
- CSS Modules with no UI kit or state library (D21).
- All API routes go under `/api`. A same-origin proxy (Vite in dev, nginx in prod) means no CORS is needed.

**Open issues:** optional upgrade to Node 24 LTS (SETUP A6). The earlier open items still stand.

**Next:** unchanged. Session 1 is backend-only, and the frontend starts in Session 9.

---

## Session 0c — Connected to GitHub (2026-10-20)

**Done:**
- Ran `git init` on branch `main` and added the remote `origin` = https://github.com/rgambhir777-rgb/MultiSourceRagChatbot
- Added `.gitignore` (keeps out `.env`, `.venv`, `node_modules`, caches, `frontend/dist`) and `.gitattributes` (LF line endings so scripts work in Linux containers).
- Pushed `main` to GitHub. Before pushing, the GitHub repo was empty, so nothing was overwritten.

**Decisions:**
- Each session from now on works on its own branch (`session-N`), pushes it, and merges into `main` once its Definition of Done passes.
- `.env` is never committed.

**Next:** Session 1, as planned.

---

## Session 0d — Public README (2026-10-20)

**Done:**
- Added `README.md` for recruiters and prospective employers.
- It covers the pitch, constraints, architecture and agent-pipeline diagrams (Mermaid), the tech stack with reasons, key design decisions, engineering practices, the roadmap with status, and skills demonstrated.

**Rule:**
- The README describes the *target* system and marks each roadmap item honestly.
- At the end of every session, flip that session's roadmap row to ✅, and only claim features that are built and tested.

**Open:** consider adding a licence (e.g. MIT) and a LinkedIn link to the Author section. Both need the owner's decision.

---

## Session 0e — LLM switched to OpenAI (2026-10-20)

**Decision (owner):**
- Use the **OpenAI API** as the LLM. This is an approved exception to the "free & open source only" rule (`CLAUDE.md` rule 9).
- Ollama and the Qwen models are removed from the stack.

**Chosen models** (prices are per 1M tokens, from OpenAI's official pricing page, 2026-10-20):
- `gpt-6.1-sol` generator, reasoning effort `low`: $2 input / $10 output.
- `gpt-6-luna` router/grader/grounding judge, reasoning effort `none`: $0.10 input / $0.50 output.
- Budget dev mode: `gpt-6-luna` for everything.

**Estimated cost:** about $0.01–0.02 per question with the defaults. To be measured in Session 6.

**Unchanged:**
- Embeddings and reranking stay local (FastEmbed), so only the top chunks per question are sent to OpenAI.
- The rest of the stack is unchanged.

**Effects:**
- RAM budget drops from about 9 GB to about 4 GB, and the WSL cap goes from 10 GB to 6 GB.
- Session 1 now has 3 infra services and adds an OpenAI key check in `/ready`.
- Session 6 now covers keys, tokens, pricing, rate limits and cost tracking.
- 5 new risks: cost runaway, key leak, rate limits/outages, data privacy, model deprecation.

**Verified:**
- `langchain-openai==1.7.2`, `openai==3.35.1` and `tiktoken==0.14.0` resolve with the full pinned set for Python 3.12 / win_amd64, and with `deepeval` too.
- The model IDs, prices and reasoning-effort values were confirmed on developers.openai.com.

**Files updated:** CLAUDE.md, PLAN.md, SETUP.md (A5 is now OpenAI key + budget limit; A9 adds a free key check), .env.example, requirements.txt, GLOSSARY.md, README.md.

**Open:**
- The OpenAI docs page didn't explicitly confirm structured-output support for the GPT-6 models. Verify it in Session 6 with a real call.
- The owner needs an OpenAI API key and a project budget limit before Session 1 (SETUP A5).

---

## Session 1 / Phase 1 — Foundation (2026-10-20), IN PROGRESS: code done, waiting on Docker + OpenAI key

**Done (on branch `session-1`):**
- Project docs:
  - Divided the plan into 7 phases (`PLAN.md` §4) and grouped the README roadmap by phase.
- Environment:
  - Installed Python 3.12.10 (via `py install 3.12`) and created `.venv`. All of `requirements.txt` installed, and `pip check` is clean.
  - Created `.env` from `.env.example`. The OpenAI key is still empty, and the owner adds it.
- Tooling: `pyproject.toml` (ruff rules incl. security `S`; pytest markers; plain `pytest` skips integration/openai tests) and `.dockerignore`.
- App code:
  - `app/config.py`: typed Settings for every `.env` key. Secrets are `SecretStr`, empty values count as "not set", and invalid values fail fast.
  - `app/logging_setup.py`: structlog. Readable console logs in dev, JSON in prod, and uvicorn logs routed through it.
  - `app/agent/llm.py`: `make_openai_client()`, the only place OpenAI clients are created.
  - `app/api/schemas.py` and `app/api/routes_health.py`: `/health` (liveness) and `/ready`. `/ready` checks Qdrant, Postgres, MLflow and OpenAI in parallel, each with a 5 s timeout, and returns 503 with per-dependency details. OpenAI error text is never echoed, because it can contain part of the key.
  - `app/main.py`: `create_app()` factory plus lifespan, which opens and closes the shared httpx and OpenAI clients.
- Infrastructure: `docker-compose.yml` with Qdrant v1.19.2, Postgres 17.11 and MLflow v3.17.1 (SQLite backend).
  - Named volumes, healthchecks, and ports bound to 127.0.0.1 only.
  - MLflow uses `--allowed-hosts` (verified the flag exists in the 3.17.1 source).
- Tests:
  - 17 unit tests (config + health/ready with fake checks).
  - 1 integration test (`pytest -m integration`).

**Verified:**
- `pytest` → 17 passed (also with ResourceWarnings as errors).
- `ruff format --check` and `ruff check` → clean.
- Ran the real server with `uvicorn app.main:create_app --factory`:
  - `/health` → 200 and `/docs` → 200.
  - `/ready` → 503, correctly reporting Qdrant/MLflow "connection failed", Postgres "timed out after 5s" and OpenAI "key not set". All checks finished within one ~5 s timeout window.
- `docker-compose.yml` parses as valid YAML. **Not yet run, because Docker isn't installed.**

**Decisions:**
- The API runs via the factory (`--factory`), so tests can build apps with their own settings.
- The Postgres readiness check uses the sync driver in a worker thread, avoiding the Windows async issue until Session 8.
- `/ready` checks both configured OpenAI model IDs with a free `models.retrieve` call.
- Default `API_HOST` is now 127.0.0.1.
- Added `HEALTH_CHECK_TIMEOUT_S` to `.env.example`.

**Open — to finish the Phase 1 Definition of Done (owner):**
1. Install WSL2 (admin + reboot) and Rancher Desktop (dockerd, Kubernetes off): SETUP A3–A4.
2. Set up the OpenAI project, budget limit and key, then paste the key into `.env`: SETUP A5/A9.
3. Run `docker compose up -d` → `docker compose ps` should show 3 healthy services. The Qdrant healthcheck uses a bash `/dev/tcp` trick that has not been tested on a real container yet.
4. Run `pytest -m integration` → `/ready` returns 200 with all 4 dependencies `ok`.
5. Merge `session-1` into `main` via a pull request on GitHub.

**Learned (glossary updated):** app factory, lifespan, SecretStr, fail fast, asyncio.gather, timeouts, worker threads, fixtures, markers, TestClient, named volumes, binding to 127.0.0.1, feature branches, pull requests.

### Session 1 progress update (2026-10-26)
- **OpenAI key added** by the owner and verified without displaying it:
  - Format check passed.
  - `.env` is git-ignored and untracked.
  - A free `models.retrieve` call confirmed `gpt-6.1-sol` and `gpt-6-luna`, and `/ready` shows `openai: ok`.
- **WSL2 installed** (WSL 3.0.3, kernel 6.18) with `wsl --install --no-distribution`, run elevated after the owner approved the UAC prompt. **A Windows restart is still pending.**
- **Docker Desktop 4.97.0 installed by the owner** (Engine 29.9.2, Compose v5.6.1) instead of Rancher Desktop (D18). This is recorded in the CLAUDE.md stack table. The owner's choice is accepted; Docker Desktop is free for personal use.
- Created `C:\Users\Rakes\.wslconfig` (memory 6GB, 8 processors, 2GB swap) so Docker can't starve the laptop.
- **Blocked:** the Docker engine can't start until Windows restarts. On first launch, Docker Desktop shows its terms, which the owner must accept.

### Session 1 / Phase 1 — COMPLETE (2026-10-26)
**Done:**
- Restarted Windows to activate WSL2. Launched Docker Desktop: Engine 29.9.2, with 8 CPUs and about 6 GB RAM, which shows `.wslconfig` applied.
- `docker compose pull` and `docker compose up -d`: Qdrant, Postgres and MLflow were all **healthy** within about 9 s. The untested Qdrant `/dev/tcp` healthcheck worked the first time.
- **Bug found and fixed:** the Postgres readiness check timed out from Windows.
  - Cause: `localhost` resolves to IPv6 `::1` first. Container ports are bound to IPv4 `127.0.0.1` only, so psycopg/libpq waited for the connect timeout before falling back. Measured: `localhost` 8.02 s vs `127.0.0.1` 0.02 s.
  - Fix: the defaults in `app/config.py`, `.env.example` and the owner's `.env` now use `127.0.0.1` for Qdrant, Postgres and MLflow (the API key was untouched).
  - Added a unit test guarding these defaults.

**Verified (Definition of Done):**
- `docker compose ps`: 3 services healthy.
- `pytest`: 18 passed.
- `pytest -m integration`: 1 passed (real Qdrant, Postgres, MLflow and OpenAI).
- `ruff format --check` and `ruff check`: clean.
- Live `GET /ready` → HTTP 200 with every dependency ok: qdrant 47 ms, postgres 46 ms, mlflow 26 ms, openai 563 ms.
- Qdrant dashboard (:6333/dashboard) and MLflow UI (:5000) load.

**Learned:** loopback addresses, IPv4 vs IPv6, why `localhost` can be slow, Docker Desktop on WSL2.

**Next:** merge `session-1` → `main` via a pull request. Then Phase 2 / Session 2: document loading and chunking. Start it with a plan and wait for "go".

---

## Session 2 / Phase 2 (part 1 of 2) — Document loading & chunking (2026-10-26), COMPLETE

**Branch:** `session-2`, built on `session-1` because `session-1` was not merged yet. Merge `session-1` with a **merge commit** (not squash) first.

**Done:**
- `app/ingestion/models.py`: frozen `LoadedDocument` and `Chunk` dataclasses.
- `app/ingestion/loaders.py`: `load_document(path, settings)`.
  - MD/TXT: UTF-8 with a Windows-1252 fallback (plus a warning); BOM stripped.
  - DOCX: MarkItDown's `DocxConverter`, called directly (no auto-detect fallback).
  - PDF: pdfplumber, page by page, pages joined with `\f`.
  - Checks: type allow-list, size limit (checked before reading), magic-byte signatures, DOCX zip structure, scanned-PDF detection (per-page warnings; error if every page is empty), text normalisation.
  - Errors: specific `IngestionError` subclasses.
- `app/ingestion/chunking.py`: `chunk_document(doc, settings)`.
  - A hand-written section splitter: heading paths, code fences ignored, pages tracked, heading-only sections carried into the next section.
  - Then LangChain's `RecursiveCharacterTextSplitter.from_tiktoken_encoder` (o200k_base; special tokens treated as text).
  - Chunks carry text, source, section, chunk_index, token_count, content_hash, doc_hash and page.
- `app/ingestion/preview.py`: `python -m app.ingestion.preview <file> [--chunk-size N --overlap N --full]`.
- `data/sample_docs/`: fictional "Lumen Home / Orbit T2" handbook (.md), FAQ (.txt), troubleshooting guide (.pdf, 2 pages, error codes E-114…E-405), warranty/returns policy (.docx).
  - The PDF/DOCX come from `scripts/make_sample_docs.py` (stdlib only, byte-deterministic).
- Settings:
  - `CHUNK_SIZE_TOKENS` 500 → **400** (owner-approved: stays under bge-small's 512-token limit).
  - Added `TOKENIZER_ENCODING` and `MIN_CHARS_PER_PDF_PAGE`.
  - Validator: overlap < chunk size.

**Decisions (owner-approved):**
- **pdfplumber for PDFs** (pinned 0.11.10; it's MIT and already what MarkItDown used). MarkItDown narrowed to `[docx]`.
  - Reason: MarkItDown loses page boundaries. It trims a trailing blank page, and pages with tables/forms get joined with no page break at all, so page citations and scanned-page detection were unreliable.

**Bugs found and fixed:**
1. Files whose extension lies (text renamed to .pdf/.docx) and truncated DOCX were silently read as plain text by MarkItDown's fallback. Fixed with magic-byte checks, a DOCX zip-structure check, and calling the specific converters.
2. Heading-only sections (e.g. "## Schedules and Auto-Learn" directly followed by "###") dropped their heading words. Caught by the "no words lost" test; fixed by carrying them into the next section.
3. **Security:** MarkItDown's dependency `magika` runs `dotenv.load_dotenv(find_dotenv())` at import time. That copied the whole `.env` (OpenAI key, DB password) into `os.environ`, where child processes such as `git clone` in Session 5 would inherit it.
   - Fixed by disabling `load_dotenv` while importing MarkItDown.
   - `tests/unit/test_secrets_isolation.py` checks this in a fresh subprocess. A canary confirmed the raw import still leaks, so the test is meaningful.

**Verified (Definition of Done):**
- All 4 formats → chunks.
- Max chunk sizes: handbook 135, FAQ 352, PDF 184, DOCX 58 tokens (all ≤ 400).
- Chunking is deterministic: hashes are stable and unique.
- `pytest`: 67 passed, also stable across different test orders.
- `pytest -m integration`: 1 passed.
- `ruff format --check` and `ruff check`: clean.
- Note: tiktoken downloads its `o200k_base` file on first use (cached). The Docker image must pre-download it (Session 10).

**Learned:** chunking trade-offs, token limits per model, tokenizers, heading paths, recursive splitting, fingerprints, determinism, magic bytes, scanned PDFs, text encodings/BOM, import side effects, environment inheritance, `tmp_path`, parametrised tests.

**Next:** Session 3 (Phase 2 part 2): embeddings + Qdrant indexing + Postgres document registry + CLI. Start with a plan and wait for "go".

---

## Session 3 / Phase 2 (part 2 of 2) — Embeddings & indexing (2026-10-26), COMPLETE → PHASE 2 DONE

**Branch:** `session-3`, created from `main` after PRs #1 (session-1) and #2 (session-2) were merged.

**Done:**
- `app/retrieval/embeddings.py`: `Embedder` loads FastEmbed `bge-small-en-v1.5` (384-dim dense) and `Qdrant/bm25` (sparse) once.
  - Separate `embed_passages` (batched) and `embed_query` methods.
  - Models are cached in `.cache/fastembed` (about 65 MB). Loading from cache takes about 0.4 s.
- `app/retrieval/vectorstore.py`: `VectorStore`.
  - Collection with named vectors `dense` (cosine) and `bm25` (sparse, IDF modifier).
  - Payload indexes: doc_id, source, file_type (keyword) and chunk_index (integer).
  - Deterministic UUIDv5 point IDs (doc_id:chunk_index).
  - Batched upserts with wait=True, `delete_document`, `delete_chunks_from`, `count`.
  - Rejects a collection with a different vector size (`CollectionMismatchError`).
- `app/db/pool.py` (sync psycopg pool; fail-fast `wait`; optional `schema` for test isolation), `app/db/schema.sql` (`documents` table; idempotent), `app/db/repositories.py` (parameterised SQL functions + a `DocumentRegistry` class).
- `app/ingestion/pipeline.py`: `IngestionPipeline` and `open_pipeline()`.
  - Outcomes: indexed / reindexed / skipped (same hash) / duplicate (same hash under another name) / failed (per file; it never stops the rest).
  - Context header (`source > section`) is embedded with each chunk; the payload keeps the original text.
- `app/cli.py`: `python -m app.cli ingest <paths…>` and `python -m app.cli documents`. Exit code 1 if any file failed.
- Settings added: `EMBED_BATCH_SIZE=32`, `QDRANT_TIMEOUT_S=30`, `POSTGRES_POOL_MAX_SIZE=5`, `POSTGRES_CONNECT_TIMEOUT_S=5`.

**Decisions (owner said "go" to all recommendations):**
- Contextual header for embeddings.
- Same content under a new name counts as a duplicate and is skipped.
- Embedding tests use the real models (one-time download).
- Re-runnable `schema.sql`, with no migration tool yet.
- Design improvement over the plan: for a changed file, **upsert the new chunks first, then trim old positions ≥ new count**. The document is never missing from search, unlike delete-then-insert.
- Write order for consistency: Qdrant first, Postgres registry last. A crash in between means the next run re-indexes, and deterministic IDs prevent duplicates.

**Verified (Definition of Done):**
- `python -m app.cli ingest data/sample_docs` → 4 indexed (23 chunks); a re-run → **4 skipped**.
- Qdrant: 23 points, each with `dense` and `bm25` vectors; payload has page numbers for the PDF.
- `python -m app.cli documents` → 4 documents / 23 chunks.
- `pytest`: 82 passed. `pytest -m integration`: 2 passed (the new test covers index → skip → re-index a shortened file with stale chunks trimmed → duplicate, in a throwaway collection + schema that is cleaned up afterwards).
- ruff clean.
- Similarity demo: paraphrase 0.756 vs unrelated 0.397.

**Learned:** embeddings & cosine similarity, dense vs sparse, BM25/IDF, named vectors, payload indexes, upserts, deterministic IDs, batching, contextual headers, connection pools, SQL tables, transactions, query parameters vs SQL injection, ON CONFLICT, consistency across two stores, dependency injection with fakes.

**Next:** Phase 3 / Session 4: hybrid retrieval (dense + BM25 → RRF in Qdrant), cross-encoder reranking, and measuring retrieval with hit@k / MRR on a golden set. Start with a plan and wait for "go".

---

## Session 4 / Phase 3 (part 1) — Hybrid retrieval, reranking & metrics (2026-10-27), COMPLETE

Owner asked to run Sessions 4–9 in one go ("go" with no decision answers). Defaults taken:
- Real OpenAI calls only for manual checks (estimated under $1).
- Branches pushed, but **not merged into main by Claude**. The owner merges the PRs in order.
- Demo repo: a public one, because the owner's repo is private (GitHub API returns 404).

**Done:**
- `app/ingestion/models.py`: shared `SECTION_SEPARATOR` and `with_context(source, section, text)`, used by both ingestion and reranking.
- `VectorStore.search(dense, sparse, mode, limit, sources)`: modes dense / sparse / hybrid. Hybrid uses Qdrant prefetch + `FusionQuery(RRF)`. Optional `MatchAny` source filter.
- `app/retrieval/reranker.py`: `Reranker` (FastEmbed `TextCrossEncoder`, ms-marco-MiniLM-L-6-v2, about 80 MB; the first download took about 3 minutes because Hugging Face was slow).
- `app/retrieval/retriever.py`: `Retriever.retrieve(question, mode, rerank, top_k, sources)` returning `RetrievedChunk` items (with a `citation` property). Logs search and rerank timings.
- `evals/`: `golden.jsonl` (18 questions: keyword, direct and paraphrase kinds), `metrics.py` (hit@k, MRR, first_correct_rank), `retrieval_eval.py` (`python -m evals.retrieval_eval [--show-misses]`).

**Results (18 questions, top 5):**

| strategy | hit@1 | MRR | median ms |
|---|---|---|---|
| dense only | 0.67 | 0.76 | 42 |
| BM25 only | 0.89 | 0.90 | 55 |
| hybrid RRF | 0.94 | 0.94 | 47 |
| hybrid + rerank (20 candidates) | 1.00 | 1.00 | 1660 |
| hybrid + rerank (**10 candidates**) | **1.00** | **1.00** | **873** |

- Dense alone missed exact codes (E-402 ranked 2nd).
- BM25 alone missed paraphrases ("wipe back to how it came out of the box" → factory reset: not found).

**Decision (measured):** `RETRIEVE_CANDIDATES` 20 → **10**: same quality at half the latency. Re-check with the eval if the knowledge base grows a lot.

**Verified:** `pytest` 91 passed; `pytest -m integration` 7 passed (new: hybrid+rerank answers first, PDF page numbers, source filter, in a throwaway collection); ruff clean.

**Next:** Session 5: GitHub ingestion + ingestion API with background jobs.
