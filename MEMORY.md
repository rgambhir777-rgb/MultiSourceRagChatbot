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
