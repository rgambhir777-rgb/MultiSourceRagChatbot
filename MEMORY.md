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

---

## Session 5 / Phase 3 (part 2) — GitHub ingestion & ingestion API (2026-10-27), COMPLETE → PHASE 3 DONE

**Done:**
- `app/ingestion/github.py`:
  - `parse_repo_url` accepts only `https://github.com/<owner>/<repo>[.git]` (SSRF-safe).
  - `check_repo_size` asks the GitHub API and refuses repos over `GITHUB_MAX_REPO_MB` *before* cloning.
  - `clone_repo` runs `git` via **subprocess** (list args, no shell) with a hard timeout: `--depth=1 --single-branch --no-tags`, `GIT_ALLOW_PROTOCOL=https`, `GIT_LFS_SKIP_SMUDGE=1`, `core.symlinks=false` (set through `GIT_CONFIG_*` env vars), no prompts. Error messages never echo the URL, which could contain a token.
  - `select_repo_files` skips vendor/build/.git dirs, hidden files, lockfiles, symlinks, binaries (NUL byte), empty and oversized files, and caps the file count.
  - `remove_tree` handles Git's read-only files on Windows.
- `CODE_LANGUAGES` (models.py): code/config types accepted **only** from repos (`load_document(..., allow_code=True)`).
  - Chunking for code: one section (no Markdown heading parsing, since `#` is a comment), split by `RecursiveCharacterTextSplitter` language separators (class/def boundaries).
- Pipeline: `ingest_repo(url, progress)`; `FileResult.source/name`; progress callbacks; `ingest_file(path, source=, allow_code=)`.
- CLI: `python -m app.cli ingest-github <url>`.
- Jobs:
  - `ingest_jobs` table (`schema.sql`) and `app/db/jobs.py` `JobStore` (create, get, list_recent, mark_running, update_progress, finish, fail, fail_interrupted).
  - `app/ingestion/jobs.py` `JobRunner`: a single worker thread; records progress, summary and per-file results; RepoError → failed with a clear message; crashes are recorded; upload temp dirs are removed.
- `app/services.py` `Services`: a lazy, thread-safe container (pool, embedder, reranker, store, registry, jobs, pipeline, job_runner, retriever). Startup stays instant and tests don't need Docker. On first use, jobs left queued/running by a previous process are marked failed ("interrupted").
- API (`app/api/routes_ingest.py`, all under `/api`):
  - `POST /ingest/files` (multipart, streamed to disk, size/type/count limits, path-traversal-safe names) → 202 + job
  - `POST /ingest/github` → 202 + job (bad URL → 422)
  - `GET /jobs`, `GET /jobs/{id}`, `GET /documents`
  - Sync DB work runs via `run_in_threadpool`.
- Settings: `POSTGRES_SCHEMA` (test isolation; `create_pool` creates it), `GITHUB_MAX_REPO_MB=200`, `MAX_UPLOAD_FILES=20`.

**Problems found & fixed:**
- GitPython refuses `-c` clone options (good: config injection) → used `GIT_CONFIG_*` env vars instead.
- **GitPython's clone timeout is unsupported on Windows** → switched to subprocess. **GitPython is now unused.** Owner decision: remove it from requirements.txt / the CLAUDE.md stack.
- Deprecated Starlette status names updated (422 `UNPROCESSABLE_CONTENT`, 413 `CONTENT_TOO_LARGE`).

**Verified:**
- Live API:
  - bad URL → 422; .csv upload → 415.
  - Markdown upload job → succeeded (then removed again).
  - `pallets/itsdangerous` via the API: 28 files indexed in about 49 s, with progress counting up. Search finds `timed.py` for "expiry time" and `exc.py` for "BadSignature".
- `pytest` 121 passed. `pytest -m integration` 10 passed (real clone of `octocat/Spoon-Knife`; missing repo → clear error; job lifecycle + interrupted-job recovery). Nothing left behind.
- Knowledge base now: 4 sample docs + itsdangerous (32 documents, 112 chunks).

**Next:** Session 6: OpenAI answers with citations + token/cost logging + MLflow tracing.

---

## Session 6 / Phase 4 (part 1) — OpenAI answers, cost logging & tracing (2026-10-27), COMPLETE

**Done:**
- Verified with real calls before building:
  - `gpt-6.1-sol` with `reasoning_effort=low` + `max_tokens`: OK.
  - **`gpt-6-luna` `with_structured_output(..., strict=True)`: OK.** The Session 1 open question about structured outputs is resolved.
- `app/agent/llm.py`:
  - `make_chat_model(settings, "generator"|"judge", streaming=)`: model, reasoning effort, max_tokens, timeout, retries, base_url, all from Settings.
  - `MissingAPIKeyError`.
  - `estimate_cost_usd(settings, usage_by_model)`: handles dated model names.
- `app/agent/prompts.py`: answer system prompt. It covers sources-only answers, `[n]` citations, the exact not-found sentence, and the injection defence (`<source>` content is data). Sources are numbered and their locations escaped.
- `app/agent/rag.py`:
  - `SimpleRag.answer()`: retrieve, `fit_to_budget` (`PROMPT_MAX_TOKENS`), generate, mark cited sources. The usage callback gives tokens and cost, which are logged.
  - No chunks → not-found answer without an LLM call (no cost).
  - `@mlflow.trace` plus a `retrieve` span.
- `app/observability/tracing.py` `setup_tracing()`:
  - `set_experiment` + `mlflow.langchain.autolog`.
  - If MLflow is down, tracing is disabled with a warning (the app keeps working).
  - `TRACING_ENABLED=false` → `mlflow.tracing.disable()` (no local mlruns).
- API: temporary `POST /api/chat/simple` (503 without a key; 502 on OpenAI errors). `Services.simple_rag()`.
- Unit tests use LangChain's `GenericFakeChatModel` (no network, no cost). The test settings disable tracing.

**Bug found & fixed:** the API response mapping used the dataclass field `text` where the schema expected `answer`, causing a 500 *after* a successful LLM call. Fixed, and a route unit test was added (it would have caught this).

**Verified (real, about $0.04 total spent on manual checks):**
- E-207 → correct fix steps citing the PDF (page 1) and handbook.
- itsdangerous expiry → correct `TimestampSigner`/`max_age` code citing `docs/timed.rst` + `timed.py`.
- "Capital of France?" → "I couldn't find this in the documents."
- **Cost ≈ $0.003–0.005 per question**; typical latency **2.3–4.4 s** (retrieval 0.5–1.5 s); occasional OpenAI slowness of about 24 s, seen in traces.
- MLflow: one trace per request, spans `simple_rag → retrieve → ChatOpenAI` with token usage. OpenAI prompt caching was seen (`cache_read_input_tokens`); our cost estimate ignores the cache discount, so it is conservative.
- `pytest` 132 passed; ruff clean.

**Next:** Session 7: the LangGraph agent (route → retrieve → grade → rewrite → generate → grounding check).

---

## Session 7 / Phase 4 (part 2) — The LangGraph agent (2026-10-27), COMPLETE → PHASE 4 DONE

**Done:**
- `app/agent/state.py`:
  - `AgentState` TypedDict. `messages` uses the add_messages reducer. `steps` uses a resettable `add_steps` reducer, where `None` starts a fresh list each turn.
  - Structured outputs: `RouteDecision` (route + standalone question), `GradeResult`, `RewrittenQuery`, `GroundingVerdict`.
- `app/agent/prompts.py`: route / grade / rewrite / grounding / direct prompts, plus a regenerate instruction listing the unsupported claims.
- `app/agent/judge.py`: a `Judge` protocol and `LLMJudge` (gpt-6-luna `with_structured_output(strict=True)`). **Safe fallbacks:**
  - route → retrieve
  - grade → keep all
  - rewrite → original question
  - grounding → None (unverified, never "verified")
  - Out-of-range passage numbers are ignored.
- `app/agent/nodes.py`: nodes route, retrieve, grade, rewrite, generate (uses `fit_to_budget`; adds the regenerate instruction), check_grounding (sets an explicit `retry_generation` flag), not_found, direct_answer, finalize (appends the AIMessage). The routers are after_route, after_grade and after_grounding; loop limits come from Settings.
- `app/agent/graph.py`: `build_graph(deps, checkpointer)`, `new_turn()` (resets per-turn fields), `RagAgent.ask(question, thread_id)` → `AgentResult` (answer, sources, grounded, route, standalone question, rewrites, regenerations, steps, usage, cost, latency). `@mlflow.trace`.
- `Services.agent()` (no checkpointer yet). The Mermaid graph is exported into PLAN.md.

**Verified:**
- `pytest`: 144 passed. 12 agent tests cover the direct path, normal RAG, rewrite-then-answer, give-up-after-max-rewrites (no generator call), one regeneration, the bounded regeneration limit (marked unverified), an unverifiable answer, conversation memory with InMemorySaver (history reaches the router; counters and steps reset per turn), and judge fallbacks.
- Real run (about $0.005 total):

| question | path | result | cost |
|---|---|---|---|
| "Hi there!" | direct | friendly reply | $0.0003 |
| "What does error E-207 mean?" | graded 5→2, verified | correct, cites PDF p.1 | $0.0018 |
| "keeps rebooting at random" (reworded) | verified | C-wire / E-114, 2 sources | $0.0020 |
| "Capital of France?" | 2 rewrites → not found | no generator call | $0.0004 |

- Grading makes answers **cheaper** than the Session 6 baseline (about $0.002 vs $0.004): fewer passages reach the expensive model.
- MLflow trace per turn: agent_turn → LangGraph → route 1.7 s, retrieve 1.1 s, grade 1.4 s, generate 2.9 s, check_grounding 1.1 s.

**Known improvement (not done):** the two rewrites for an unanswerable question were identical ("France capital city Paris"). Passing earlier failed queries to the rewriter, or stopping on a repeat, would save one search.

**Next:** Session 8: Postgres checkpointer (memory survives restarts) + streaming `POST /api/chat` (SSE).

---

## Session 8 / Phase 5 (part 1) — Persistent memory & streaming chat API (2026-10-27), COMPLETE

**Design change (better than planned):**
- LangGraph's **synchronous** `PostgresSaver` is used, and each chat turn runs in **one worker thread**. Events reach the async SSE response through an asyncio queue (`loop.call_soon_threadsafe`).
- This removes the Windows psycopg-async problem entirely, so the planned `python -m app.serve` launcher is **not needed**. The plain `uvicorn ... --factory` command works.
- A cancel flag stops the agent when the browser disconnects.

**Done:**
- `app/memory/checkpointer.py` `create_checkpointer()`: its own small pool (autocommit, prepare_threshold=0, dict_row, schema search_path), `saver.setup()`, and a **deserialisation allow-list** (`JsonPlusSerializer(allowed_msgpack_modules=[RetrievedChunk])`). The allow-list removes LangGraph's "unregistered type" warning; that warning is a security feature.
- `app/db/sessions.py` `SessionStore` + `chat_sessions` table: create, get, list_recent, record_turn (the first question becomes the title, max 60 chars), delete.
- `app/db/pool.py` `ensure_schema()` is shared by both pools.
- Agent:
  - The `turns` state field (operator.add) records question, answer, sources, grounded and route per turn for the history view. It is kept OUT of `messages`, which are sent back to OpenAI.
  - `RagAgent.stream(question, thread_id, cancel)` yields `ChatEvent`s: `status`, `token` (answer nodes only), `answer_reset` (before a regeneration), `sources`, `done`.
  - "Writing the answer" is announced at the first token (LangGraph reports node steps only when a node finishes).
- `Services`: `sessions()`, `checkpointer()` (its pool is closed on shutdown), and `agent()` now has memory plus a **streaming** generator.
- API (`app/api/routes_chat.py`):
  - `POST/GET /api/sessions`, `GET /api/sessions/{id}/history` (reads the checkpoint, no models loaded), `DELETE /api/sessions/{id}` (also deletes the thread's checkpoints).
  - `POST /api/chat` → SSE with `X-Accel-Buffering: no`; 404 for an unknown session, 409 if the session is busy (`TurnGuard`), 503 without a key. Errors become a friendly `error` event.
  - `/api/chat/simple` is kept as a baseline.

**Verified (live, about $0.005):**
- `curl -N` stream: status ×3 → "Writing the answer" → 50 token events → sources → done (grounded true, $0.0017).
- Follow-up "And how do I fix it?" → standalone "How do I fix error E-114 on the Orbit T2 thermostat?" → correct and verified.
- **API restarted**, then:
  - history returned both turns with sources and grounded status,
  - the title was auto-set,
  - "What was my first question?" → direct route answered "What does error E-114 mean?".
- `pytest` 153 passed. New tests cover event order, word-by-word tokens, answer_reset, cancel, saved turns, and the session/chat endpoints (SSE parsing, errors → error event, 404, 409, 422).
- `pytest -m integration` 12 passed. **New: memory survives a restart using the real PostgresSaver** (fake LLMs, $0) and session store titles/counts. No test schemas were left behind.

**Next:** Session 9: React chat UI.

---

## Session 9 / Phase 5 (part 2) — React chat UI (2026-10-27), COMPLETE → PHASE 5 DONE

**Done (frontend/, React 19 + Vite 8, JavaScript, exact pins, committed lockfile, `.npmrc save-exact`):**
- `npm install` matched every pin; `npm audit` reported 0 vulnerabilities.
- Config: `vite.config.js` (dev proxy `/api`, `/health`, `/ready` → 127.0.0.1:8000; Vitest jsdom), `eslint.config.js` (flat config with @eslint/js, react-hooks recommended-latest, react-refresh), `.prettierrc`, `index.html` (inline SVG favicon).
- `src/api/client.js`: every JSON call, with `ApiError`, timeouts and readable FastAPI `detail` messages.
- `src/api/sse.js`: an incremental SSE parser (CRLF-safe: it holds a trailing `\r` so a `\r\n` split across chunks can't end an event early) and `streamChat` (fetch POST + ReadableStream + TextDecoder, AbortSignal).
- `src/lib/citations.js`: `linkCitations` turns `[n]` into `#cite-n` links outside code (so `items[1]` is untouched), plus `timeAgo`.
- Hooks:
  - `useSessions`: list/new/select/delete, the last open chat remembered in localStorage (try/catch).
  - `useChatStream`: a useReducer turn list; events are applied only to a still-streaming turn. Stop works through AbortController. A 90 s idle timeout gives a clear message. The stream of a just-created chat is not cancelled or wiped by that chat's history load (tracked through a `controller.sessionId` + version check).
  - `useIngestJobs`: upload, add a repo, and poll active jobs every 1.5 s.
- Components (+ CSS Modules): SessionSidebar, ChatWindow (empty state with example questions), MessageBubble (react-markdown + remark-gfm, citation chips, links `rel="noopener noreferrer"`, `aria-live`), ChatInput (Enter sends, Shift+Enter adds a new line, Stop while busy), StatusSteps, SourceList (expand + highlight on citation click), GroundingBadge, IngestPanel (drag-and-drop or choose files, GitHub URL, jobs with progress bars and failures, documents table).
- Light and dark design tokens; responsive (the sidebar slides in under 760 px).

**Bugs/issues found & fixed:**
- Adjacent citations `[1][2]` weren't both linked (a test caught it).
- React 19 lint `set-state-in-effect`: the initial loads now set state in promise callbacks.
- Impure state updaters in `useSessions` were refactored.
- **Streamed turns didn't log tokens/cost** (only `ask()` did): `_log_turn` now runs for both. A CLAUDE.md requirement.
- The mobile placeholder wrapped and was clipped, so it was shortened.

**Verified:**
- Frontend: `npm run lint` clean, Prettier clean, `npm test` 26 passed (SSE parser incl. every split position, citations, ChatInput keyboard, MessageBubble incl. **no HTML execution** and safe links, App flow with mocked API), `npm run build` OK (125 KB gzip JS).
- Backend: `pytest` 153 passed, integration 12 passed, ruff clean.
- **Real browser (headless) end-to-end:** reopened a conversation; new chat → progress → Stop button → streamed answer "two years [1]" **✓ Verified**, $0.0008; citation click opened the source; sidebar title updated; Knowledge base listed 32 docs and 2 jobs; no horizontal overflow at 390 px. 0 console errors, 0 failed requests. Screenshots reviewed.

**Observation:** `gpt-6.1-sol` sometimes takes about 24 s for a short answer (seen in several traces; other nodes take 1–2 s). This is on OpenAI's side. Options (owner decision, cost/quality trade-off): use gpt-6-luna for generation, or keep and accept.

**Open items for the owner:**
1. Merge PRs **session-4 → session-9 in order** (merge commits, not squash).
2. GitPython is unused since Session 5 (subprocess git). Remove it from requirements.txt / the stack table?
3. Decide on the generator-latency option above.
4. Confirm the OpenAI project budget limit is set.
5. Known improvement: the rewriter can repeat the same query (the Session 7 note).

**Next:** Session 10 (Phase 6): Dockerfiles, full compose (api + nginx frontend), healthchecks, smoke test, one-command deploy. Plan first, then wait for "go".

---

## E2E testing with Playwright (2026-10-28), owner-requested

**Done (branch `e2e-playwright`, built on `session-9`):**
- Owner asked to install Playwright and run detailed tests. `@playwright/test` **1.64.1** was added as an exact-pinned devDependency (Apache-2.0; released 2026-10-14) plus headless Chromium. It is recorded in the CLAUDE.md stack table.
- `frontend/playwright.config.js` (one worker, HTML + JSON reports, traces on failure, reuses or starts the Vite dev server).
- `e2e/global-setup.js` (fails clearly if the API isn't ready; snapshots existing conversations) and `e2e/global-teardown.js` (deletes conversations the tests created).
- `e2e/helpers.js`: **every test fails on any browser console error**, unless a test declares that error as expected.
- **14 E2E tests**, `npm run e2e`:
  - chat (8): empty state; cited + verified answer with citation → source; follow-up memory + survives reload; honest not-found; greeting; Stop; GitHub code answer; delete conversation
  - knowledge base (3): list; upload → indexed → answer from it ("AURORA-42"); validation errors
  - layout (3): phone menu, dark mode, keyboard
- Vitest now excludes `e2e/`, ESLint has node globals for E2E files, and outputs are git-ignored (`frontend/e2e-results/`).

**Bugs found by the E2E tests and fixed (all races where an older/slower result overwrote something newer):**
1. **Upload vanished from the job list**: the Knowledge base page's first job-list load, answering after a fast upload, replaced the list. Fix: `mergeJobs()` keeps jobs the server list doesn't know yet. Unit-tested.
2. **Error messages lost**: (a) an old client-side error hid a newer server error; (b) a late list load cleared the error. Fix: new actions clear old errors; loading lists never clears errors.
3. **"+ New chat" was overridden**: the first conversation-list load switched to the latest chat after the user clicked New chat. Fix: once the user chooses, list loads never switch conversations (`userChose` ref).
4. UX: **"+ New chat" no longer creates empty conversations** on the server; the first message creates it. Unit-tested.
5. A fast stream finishing before React switched to the new chat let the switch reload (and wipe) it. Fix: `shownSession` ref, plus a StrictMode-safe reset. A regression test was **verified to fail without the fix** (the first version passed either way, so it was corrected).

**Verified:**
- `npm run e2e`: **14/14 passed, twice in a row** (2.3 min and 2.0 min); about $0.03 of OpenAI per run.
- Vitest 30/30; ESLint and Prettier clean.
- All 17 screenshots reviewed. The phone-menu screenshot was taken mid-animation; the test now waits until the sidebar is fully on screen (measured: x = -234 px → 0 px after 400 ms).

**Notes:**
- Conversation "How long is the warranty?" contains 4 of the **owner's own** questions (12:45–12:48, incl. one in Hindi). An earlier claim that tests wrote them was wrong.
- The cleanup before E2E run 2 deleted exactly the 8 conversations E2E run 1 created.
- The uploaded test document `e2e-upload-test.md` stays in the knowledge base (re-runs skip it).
- A first message that is *stopped* leaves a conversation titled "New chat", because the title is set when a turn completes.

---

## CI pipeline with GitHub Actions (2026-10-28), owner-approved ("go" with defaults)

**Done (branch `ci-pipeline`, built on `e2e-playwright`):**
- `.github/workflows/ci.yml`: push to `main`, pull requests into `main` (free suites only), and manual runs. **No deployment.**
  - Jobs: `backend-unit` (ruff format/lint + pytest), `frontend-unit` (ESLint, Prettier, Vitest, build), `integration` (our docker-compose.yml + `pytest -m integration`; on PRs `integration and not openai`), `e2e` (pushes/manual only: compose, ingest sample docs + pallets/itsdangerous, uvicorn, Playwright), and `report`.
  - `permissions: contents: read`. Concurrency cancels superseded runs. Official actions only, **pinned to commit SHAs**: checkout v7.0.1, setup-python v7.0.0 (v7.1.0 was <2 weeks old), setup-node v7.1.0, upload-artifact v7.0.2, download-artifact v8.0.2, cache v6.1.0.
  - Caches pip, npm, models (.cache) and the Playwright browser.
  - The OpenAI key comes from the repo secret `OPENAI_API_KEY`; the E2E job fails early with instructions if it is missing. `GITHUB_TOKEN` is passed to avoid GitHub API rate limits in repo ingestion.
- `scripts/ci_summary.py` (stdlib only): JUnit XML → Markdown summary (verdict, per-suite table, failures, suites that didn't run) for `$GITHUB_STEP_SUMMARY`, plus a `test-report` artifact. 4 unit tests.
- Playwright in CI mode (`CI=true`): adds JUnit (`e2e-results/e2e.xml`) and GitHub annotations reporters, plus `forbidOnly`.
- `.gitignore`: `reports/`, `frontend/reports/`.

**Bug found while verifying (fixed):** after the Postgres container was recreated, the running API kept using dead pooled connections and answered **500** on every database call until it was restarted (`/ready` looked healthy because it opens fresh connections).
- Fix: `check=ConnectionPool.check_connection` on both pools (app + checkpointer).
- New `tests/integration/test_db_recovery.py` (drops the pool's connections via `pg_terminate_backend`). **Verified to fail without the fix and pass with it.**

**Verified locally (GitHub can only run the workflow once it's on GitHub):**
- YAML structure: 3 triggers, 5 jobs, every `uses:` pinned to a 40-character SHA.
- Every job's commands run locally and produce JUnit files: backend 157 passed; frontend 30 passed; integration 11 (PR mode) / 12 (main mode), then 14 with the recovery tests; E2E in CI mode 14/14 (1.5 min).
- `docker compose up -d --wait` works.
- `ci_summary.py` on the real files: "✅ All tests passed (213 tests in 4 suites)".

**Owner next steps:** add the `OPENAI_API_KEY` repository secret; merge the open branches in order (session-4 … session-9, e2e-playwright, ci-pipeline). The first CI run will happen on the pull request (free suites) and then on `main` (all suites).

---

## UI tweak: input box at the top + first CI run on `main` (2026-10-28), owner-approved ("go")

**Context:** the owner merged PR #4 (`ci-pipeline`, which includes everything since Session 4) into `main`. The first CI run on `main` passed 4 of 5 jobs. The E2E job failed **1 of 14** tests: the keyboard test was *flaky*.

**Flaky test, root cause:** when the page opens, it loads the latest saved conversation, and the input is disabled while that happens. The test typed immediately; the Shift+Enter and "second line" keys hit the disabled box and were dropped. CI had 7 saved chats, so loading was slower and the race showed up there.
- Fix: the test first runs `newChat(page)` and waits for the box to be enabled. Verified with 10 repeats in a row.

**Done (branch `ui-input-top`):**
- `ChatWindow.jsx` / `.module.css`: the order is now title → input (+ hint) → conversation (scrolls). The empty-state gap was reduced (8vh → 4vh). Messages stay in chronological order (owner's choice: "Input box at the top", not newest-first).
- New `ChatWindow.test.jsx`: 2 tests that the input comes before the welcome text and before the conversation.

**Verified locally:** ESLint, Prettier, Vitest 32/32, build OK; Playwright CI mode 14/14 (2.4 min); keyboard test 10/10 repeats.

**Gotcha:** switching git branches can touch `vite.config.js`. Vite then restarts itself in place, and after that restart its `/api` proxy stopped working (the page got HTML instead of JSON, so 12 E2E tests failed). Fix: stop and restart `npm run dev`.

**How CI results are read:** through the GitHub REST API, using the GitHub login saved by Git Credential Manager (owner-approved; read-only, token never printed). The GitHub CLI is not installed.

**Result on GitHub:**
- PR #5 CI run: backend, frontend, integration and report green; E2E skipped (by design for PRs).
- Merged into `main` (`c954092`). The full run on `main` (run 40735493031) was green in **all 5 jobs**, E2E included (~$0.03).

**Next step:** Session 10 in `PLAN.md` (Docker images + nginx, one-command deploy). Open owner decisions are unchanged:
- generator latency option;
- removing the unused GitPython;
- confirming the OpenAI budget limit.

---

## Code guide PDF (2026-10-29), owner-requested

- New `docs/` folder:
  - `code-guide.html` is the source; `code-guide.pdf` is the 13-page A4 version.
  - It covers the system schematic, the journey of one question, UI, API, ingestion + embeddings, Qdrant/hybrid search/RRF, the retrieval funnel, the agent graph, the LLM calls, and a "where do I look" cheat sheet.
  - 4 inline SVG schematics. All `file:line` pointers were checked against commit `dcf1597`.
- `scripts/make_code_guide_pdf.cjs` rebuilds the PDF with the Playwright Chromium already in `frontend/` (no new dependency): `node scripts/make_code_guide_pdf.cjs`.
- README "Documentation" table links the guide.
- **Keep in mind:** line numbers drift when code changes. Update the HTML and rerun the script after big refactors.

---

## Session 10: one-command deployment & hardening (2026-11-03), owner said "go" (all 6 recommendations)

**Approved decisions:**
1. API base image `python:3.12.14-slim-trixie` (the 3.12.15/16 tags were < 2 weeks old).
2. Plain `docker compose up -d` = the whole system. Development uses `docker compose up -d qdrant postgres mlflow`.
3. MLflow limited to 1 worker.
4. No `docker/postgres-init.sql`: the API creates its tables on startup.
5. New CI `docker` job.
6. GitPython removed: unused, because `app/ingestion/github.py` runs `git` via subprocess. `CLAUDE.md`, `PLAN.md` and the README stack rows were updated.

**Built (branch `session-10`):**
- `docker/api.Dockerfile`:
  - slim Python + `git`;
  - dependencies layer first, then models baked in (FastEmbed dense/sparse/reranker + tiktoken, 163 MB) using only `config.py`, so code edits don't re-download them;
  - non-root `appuser`; 1 uvicorn worker.
  - Image size 1.38 GB (574 MB is Python libraries).
- `docker/frontend.Dockerfile`: multi-stage (node 24.22.0 builds, nginx 1.30.6 serves). 93 MB, no Node inside.
- `frontend/nginx.conf`:
  - single-page-app fallback;
  - `/api` proxy with `proxy_buffering off` and 300 s timeouts;
  - API looked up via Docker DNS on every request (survives API restarts);
  - `client_max_body_size 500m` (= 20 files × 25 MB);
  - CSP / nosniff / DENY frames / no-referrer / Permissions-Policy headers;
  - hashed assets cached for 1 year, `index.html` never cached.
- `docker-compose.yml`:
  - adds `api` (`env_file: .env`, optional; in-network URLs; healthcheck on `/health`; depends on qdrant/postgres/mlflow healthy) and `frontend` (:8080, depends on api healthy);
  - `mem_limit` on every service;
  - MLflow `--workers=1` and `MLFLOW_SERVER_ENABLE_JOB_EXECUTION=false`.
- `tests/integration/test_smoke.py` (`pytest -m smoke`, new marker, excluded by default): through nginx it uploads the sample docs → waits for the job → asks about E-207 → checks ≥ 5 token events spread over time (no buffering), a cited answer and grounded = true. It deletes its own conversation.
- CI: the integration and e2e jobs start only the 3 infrastructure services. The new `docker` job builds the images, runs `up --wait`, checks UI / SPA fallback / `/api` / CSP / `/health` through nginx, and prints `docker stats`. No OpenAI calls.

**Bugs found and fixed while verifying:**
- **MLflow used 2.2 GB:** 4 web workers by default plus 8 "job runner" processes (~220 MB each). With 1 worker and the job runner off it runs at **~350 MB**. With only workers=1 it was OOM-killed twice at a 768 MB limit.
- **Docker Compose reads `KEY=   # comment` (empty value) as the value "# comment".** `OPENAI_BASE_URL`, `QDRANT_API_KEY` and `GITHUB_TOKEN` arrived as comment text in the container. Fixes:
  - `Settings` treats values starting with `#` as unset;
  - `openai_base_url` now defaults to `https://api.openai.com/v1` and is always passed explicitly, because the OpenAI SDK otherwise reads the `OPENAI_BASE_URL` env var itself;
  - `.env.example` puts comments for empty values on their own line;
  - 2 new unit tests.

**Verified (2026-11-03):**
- Clean-machine test as a separate compose project (`-p ragbot-dod`, fresh volumes; **the owner's volumes were never deleted**): all 5 services healthy in ~2 min from scratch, ~30–40 s afterwards.
- Through nginx: upload of the 4 sample docs, and GitHub ingest of pallets/itsdangerous (28 files) inside the container. The UI loads with no console errors or CSP violations.
- Recreating all containers (`down` + `up`): documents, vectors (112) and conversations kept.
- RAM with the embedding models loaded: about **1 GB in total** after the MLflow fix (2.3 GB before it).
- ruff OK; 159 unit + 13 free integration tests pass; ESLint / Prettier / Vitest (32) / build OK.
- `npm audit --omit=dev`: 0 vulnerabilities. Dev tools: 6 moderate findings, all ESLint → minimatch (pattern denial-of-service); dev-only and not in any image; the "fix" is a breaking ESLint downgrade, so it's accepted.

**BLOCKED:** the OpenAI key in `.env` returns **401** (it fails from the laptop too, not just the container), so these are not run yet:
- the smoke test (streaming through nginx);
- the OpenAI integration tests;
- E2E;
- the `main` CI run (if the GitHub secret is the same key).

**Next:** the owner fixes the key (and the GitHub secret if needed). Then run `pytest -m smoke` and the OpenAI integration tests, measure RAM with the reranker loaded, merge PR → `main`, and set the README roadmap row 10 to ✅.

**Owner's stack now:** `docker compose up -d` (full system) runs on the owner's data: 33 documents, 3 conversations. App at http://localhost:8080.

