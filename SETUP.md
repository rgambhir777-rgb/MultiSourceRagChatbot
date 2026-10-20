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
memory=10GB
processors=10
swap=4GB
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

### A5. Ollama (already installed natively) and the models

The full system (from Session 1) runs Ollama **inside Docker**, so everything starts with one command. Your native Ollama is still handy for quick experiments. **Don't keep models loaded in both at once**, because RAM is limited. Quit the Ollama tray app before `docker compose up`.

Optional quick test with native Ollama (it pulls about 5 GB):
```powershell
ollama pull qwen3.5:4b
ollama pull qwen3.5:2b
ollama run qwen3.5:2b "Say hello in five words." --think=false
```

**Verify**
```powershell
ollama list                   # shows qwen3.5:4b and qwen3.5:2b
```

> Disk space: plan for about 15 GB free, covering models, Docker images and volumes.
> `gemma4:31b` (20 GB) cannot run in 16 GB RAM. You can remove it with `ollama rm gemma4:31b` to free disk space. That's your call.

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
```
Leave the defaults for now. `.env` is never committed to git.

---

## Part B — Start infrastructure (available after Session 1)

```powershell
docker compose up -d
docker compose ps                              # all services "healthy"
docker compose exec ollama ollama pull qwen3.5:4b
docker compose exec ollama ollama pull qwen3.5:2b
```

**Verify**

| Check | Command / URL | Expected |
|---|---|---|
| Qdrant | http://localhost:6333/dashboard | Qdrant web UI |
| Postgres | `docker compose exec postgres pg_isready` | `accepting connections` |
| Ollama | `curl.exe http://localhost:11434/api/tags` | JSON listing both models |
| MLflow | http://localhost:5000 | MLflow UI |
| API (dev) | `uvicorn app.main:app --reload`, then http://localhost:8000/ready | all deps `ok` |

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
| Containers exit / laptop freezes | Out of RAM | Lower `memory` in `.wslconfig`; close browser tabs; make sure native Ollama isn't also holding models |
| Very slow answers (> 60 s) | Thinking mode on, or a model too big | Check `.env` model names; `OLLAMA_THINK=false` |
| Port already in use (`11434`) | Native Ollama is running | Quit the Ollama tray app, or change the host port in compose |
| `pip install` builds from source / fails | Wrong Python (3.14) | Activate `.venv` made with 3.12 |
| psycopg errors about `ProactorEventLoop` (local dev) | Windows async quirk | Handled in Session 8; containers are unaffected |
| `npm ci` fails: "lockfile out of sync" | `package.json` edited without updating the lockfile | Run `npm install` once (with approval for any new package), then commit both files |
| React app shows "Failed to fetch" / 502 on `/api` | API isn't running, or the wrong port | Start `uvicorn` (dev) or check `docker compose ps` (prod) |
| Answer appears all at once instead of streaming | A proxy is buffering the stream | Dev: check the Vite proxy config. Prod: `proxy_buffering off` in `frontend/nginx.conf` |
| Port 5173 or 8080 in use | Another dev server is running | Stop it, or change the port in `vite.config.js` / `.env` |
