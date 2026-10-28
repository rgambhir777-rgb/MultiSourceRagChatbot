# SETUP.md — Windows Setup & Verification

Target machine: Windows 11, no GPU, 16 GB RAM. All commands are for **PowerShell** unless
marked otherwise. Do **Part A** before Session 1. Parts B–D become usable as the sessions build them.
Backend = Python (installed with pip). Frontend = React (installed with npm).

> Tip: run each **Verify** block and compare with the expected output before moving on.
> If something doesn't match, stop and ask in the session instead of guessing.

---

## Part A — Install the tools (before Session 1)

### A1. Python 3.12 (alongside your existing 3.14)

Why 3.12: every library we use ships ready-made Windows packages ("wheels") for 3.12. That was checked on 2026-10-20. 3.14 is too new for some of them.

Your machine already has the Python install manager (`py`). Install 3.12 with it:

```powershell
py install 3.12
```

If `py install` is not recognised, install "Python 3.12" from https://www.python.org/downloads/windows/ instead. Untick "Add to PATH" so your default stays 3.14.

**Verify**
```powershell
py -V:3.12 --version          # expected: Python 3.12.x
py list                       # should list both 3.12 and 3.14
```

### A2. Git (already installed)

**Verify**
```powershell
git --version                 # expected: git version 2.x
git config --global user.name # should print your name; if empty:
# git config --global user.name "Your Name"
# git config --global user.email "you@example.com"
```

### A3. WSL2 (Linux inside Windows, which Docker needs)

Open PowerShell **as Administrator**:
```powershell
wsl --install --no-distribution
```
Reboot if asked.

Next, cap how much RAM Linux/Docker may use, so Windows stays responsive. Create the file `C:\Users\<you>\.wslconfig` with:
```ini
[wsl2]
memory=6GB
processors=8
swap=2GB
```
Then run `wsl --shutdown` so the setting applies.

**Verify**
```powershell
wsl --status                  # expected: Default Version: 2
```

### A4. Rancher Desktop (free, open-source Docker for Windows)

```powershell
winget install --id SUSE.RancherDesktop -e
```

Then open Rancher Desktop:
1. On first start, choose container engine **dockerd (moby)**. This is the setting that gives you `docker` and `docker compose`.
2. Turn **Kubernetes off**. We don't need it, and it saves RAM.
3. Wait until the status bar says it's running.

Open a **new** PowerShell window, then run the checks below.

**Verify**
```powershell
docker --version              # expected: Docker version 2x.x
docker compose version        # expected: Docker Compose version v2.x
docker run --rm hello-world   # expected: "Hello from Docker!"
```

> Prefer Docker Desktop? It also works, but it is proprietary software (free only for personal or small-business use). Per `CLAUDE.md`, raise it before switching.

### A5. OpenAI API key and spending limit

The project uses OpenAI's API for the LLM. It's **paid per token**: expect roughly $0.01–0.02 per question with the default models, and far less in budget mode (`gpt-6-luna` for everything).

1. Sign in at https://platform.openai.com and add billing (a small prepaid credit, e.g. $5–10, is plenty for development).
2. **Create a project** just for this app (Settings → Projects), e.g. `multisource-rag`.
3. **Set a monthly budget limit** on that project (e.g. $10). This is your safety net against bugs and loops.
4. In that project, create an **API key**. Copy it once. You can't see it again.
5. You'll paste it into `.env` in step A9. **Never** paste it into code, commit it, or share it in a screenshot.

> Ollama is no longer part of this project. Your native install can stay for your own experiments but isn't used. You can free disk space with `ollama rm gemma4:31b` (20 GB), if you like. That's your call.
> Disk space: plan for about 6 GB free for Docker images and volumes.

### A6. Node.js (for the React frontend)

You already have **Node 22.23.2** and **npm 10.9.8**, which Vite 8 supports. The recommended version is the current LTS, **Node 24**, because it matches the Docker build image (`node:24.22.0-alpine`). Upgrading is optional but avoids "works on my machine" differences:

```powershell
winget install --id OpenJS.NodeJS.LTS -e
```

**Verify** (open a new terminal first)
```powershell
node --version                # expected: v24.x (v22.12+ also works)
npm --version                 # expected: 10.x or 11.x
```

You install frontend packages in Session 9 (`npm ci` inside `frontend/`). There is nothing to install for it yet.

### A7. Editor (recommended)

VS Code extensions: **Python** (Microsoft), **Ruff** (Astral), **Docker** (Microsoft), **ESLint** (Microsoft), **Prettier** (Prettier).
In VS Code, choose the interpreter `.venv\Scripts\python.exe` after A8.

### A8. Project virtual environment + backend dependencies

From the project folder (`C:\Users\Rakes\Downloads\ClaudeCode1020`):
```powershell
py -V:3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If activation is blocked with "running scripts is disabled", run this once, then activate again:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**Verify**
```powershell
python --version              # expected: Python 3.12.x  (inside the venv)
pip check                     # expected: No broken requirements found.
python -c "import fastapi, langgraph, qdrant_client, fastembed, markitdown, mlflow; print('imports ok')"
```

### A9. Environment file

```powershell
Copy-Item .env.example .env
notepad .env                  # paste your key after OPENAI_API_KEY=   (no quotes, no spaces)
```
Leave the other defaults for now. `.env` is git-ignored and never committed.

**Verify** (with the venv active). This makes a *free* model-lookup call, not a paid completion:
```powershell
python -c "from dotenv import dotenv_values; from openai import OpenAI; c = dotenv_values('.env'); print(OpenAI(api_key=c['OPENAI_API_KEY']).models.retrieve(c['LLM_JUDGE_MODEL']).id)"
# expected: gpt-6-luna
```

---

## Part B — Start infrastructure (available after Session 1)

```powershell
docker compose up -d
docker compose ps                              # qdrant, postgres, mlflow all "healthy"
```

**Verify**

| Check | Command / URL | Expected |
|---|---|---|
| Qdrant | http://localhost:6333/dashboard | Qdrant web UI |
| Postgres | `docker compose exec postgres pg_isready` | `accepting connections` |
| MLflow | http://localhost:5000 | MLflow UI |
| API (dev) | `uvicorn app.main:create_app --factory --reload`, then http://localhost:8000/ready | all deps `ok`, including `openai` |

## Part C — Frontend development (available after Session 9)

Run the API (Part B) in one terminal, then in a second terminal:
```powershell
cd frontend
npm ci                            # installs exact versions from package-lock.json
npm run dev                       # http://localhost:5173 — /api calls are proxied to localhost:8000
```

**Verify**
```powershell
npm run lint                      # no errors
npm test                          # all tests pass
npm run build                     # creates frontend\dist
```

## Part D — Full system (available after Session 10)

```powershell
docker compose up -d --build      # the one command
```
App: http://localhost:8080 · API docs: http://localhost:8000/docs · Traces: http://localhost:5000

## Part E — Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `docker: command not found` | Rancher Desktop not running, or old terminal | Start Rancher Desktop; open a new terminal |
| Containers exit / laptop freezes | Out of RAM | Lower `memory` in `.wslconfig`; close browser tabs |
| `401 Unauthorized` from OpenAI | Wrong or missing key | Check `OPENAI_API_KEY` in `.env` (no quotes or spaces); create a new key in the project |
| `429` with `insufficient_quota` | No credit left, or the budget limit was reached | Add credit or raise the project budget (deliberately) |
| `429` rate limit | Too many requests per minute | The app retries with backoff; wait a moment; avoid hammering it with test loops |
| `404 model not found` | Model ID typo or not available to your project | Check `LLM_*_MODEL` in `.env` against the OpenAI models page |
| Slow answers (> 15 s) | High reasoning effort or a big model | Check `LLM_*_REASONING_EFFORT` and model names in `.env` |
| `pip install` builds from source / fails | Wrong Python (3.14) | Activate `.venv` made with 3.12 |
| psycopg errors about `ProactorEventLoop` (local dev) | Windows async quirk | Handled in Session 8; containers are unaffected |
| `npm ci` fails: "lockfile out of sync" | `package.json` edited without updating the lockfile | Run `npm install` once (with approval for any new package), then commit both files |
| React app shows "Failed to fetch" / 502 on `/api` | API isn't running, or the wrong port | Start `uvicorn` (dev) or check `docker compose ps` (prod) |
| Answer appears all at once instead of streaming | A proxy is buffering the stream | Dev: check the Vite proxy config. Prod: `proxy_buffering off` in `frontend/nginx.conf` |
| Port 5173 or 8080 in use | Another dev server is running | Stop it, or change the port in `vite.config.js` / `.env` |

---

## Quick start: play with the app (after Session 9)

Each time you want to use the app (after a restart, start Docker Desktop first and wait for "Engine running"):

```powershell
# terminal 1: databases + tracing
docker compose up -d

# terminal 2: the API
.\.venv\Scripts\Activate.ps1
uvicorn app.main:create_app --factory --reload

# terminal 3: the chat UI
cd frontend
npm run dev
```

Open **http://localhost:5173**. Try:
- "What does error E-207 mean?", then the follow-up "And how do I fix it?" (memory)
- "How do I make a signed token expire with itsdangerous?" (code from a GitHub repo)
- "What is the capital of France?" (honest "not found")
- **Knowledge base** tab: upload your own PDF/DOCX/MD/TXT, or add a public GitHub repo URL.

Each answer shows its cost; a typical one is $0.001–0.005.

---

## CI on GitHub (tests + report on every push to `main`)

The workflow is `.github/workflows/ci.yml`. It runs automatically; nothing is deployed.

**One-time setup: add your OpenAI key as a secret** (needed for the end-to-end tests on `main`):
1. Open the repo on GitHub → **Settings** → **Secrets and variables** → **Actions**.
2. **New repository secret** → Name: `OPENAI_API_KEY` → Value: your key → **Add secret**.

Use a key from a project with a monthly budget limit. Each `main` run costs about $0.03.

**Where to see results:** the repo's **Actions** tab → open a run.
- **Summary:** a table with every suite (passed, failed, skipped, time) and the failures.
- **Artifacts** (bottom of the run page, kept 14 days): `e2e-report` has the Playwright HTML report with screenshots and the API log; `test-report` has all JUnit files and `summary.md`.

**When it runs:**

| Event | Suites |
|---|---|
| Push to `main` | All four (incl. OpenAI-backed E2E and `/ready`) |
| Pull request into `main` | The free suites only (no OpenAI calls) |
| Manual (Actions → CI → Run workflow) | All four |
