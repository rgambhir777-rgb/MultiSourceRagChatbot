# Deploying to Modal

The local setup (`docker compose up -d`) stays the main way to run the chatbot. This folder adds
a **public copy on [Modal](https://modal.com)**, a serverless cloud that starts
a container when someone visits and stops it (and the bill) when nobody does.

## How it fits together

```
browser ──https──▶ Modal: one container (image nusoftinc/ragbot-modal on Docker Hub)
                     ├─ nginx :8080   React app, forwards /api (+ password check if enabled)
                     └─ API   :8000   FastAPI + agent + embedding models (CPU)
                             │
                             ├──▶ Qdrant Cloud   (vectors; free 1 GB cluster)
                             ├──▶ Neon Postgres  (documents, chats, memory; free tier)
                             └──▶ OpenAI API     (answers; billed per question as before)
```

- Modal can't run `docker compose`, so the API and nginx share one container
  (`docker/modal.Dockerfile`, started by `deploy/start_web.py`).
- Databases don't belong in a container that stops when idle, so Qdrant and Postgres are hosted.
- MLflow tracing is off on Modal (`TRACING_ENABLED=false`); it stays a local tool.
- The cloud copy starts **empty**: upload documents through its UI. Your local data stays local.

| File | Role |
|---|---|
| `modal_app.py` | the Modal app: which image, CPU/RAM, scale-to-zero, secrets |
| `start_web.py` | container start-up: access rules (public / password) → API → wait for `/health` → nginx |
| `nginx-modal.conf` | nginx for the single container (HTTP basic auth unless public) |
| `env.modal.example` | template for `.env.modal` (your secrets; git-ignored) |
| `requirements-modal.txt` | the `modal` command-line tool (not part of the app image) |

## One-time setup

1. **Modal login**: `pip install -r deploy/requirements-modal.txt`, then `modal token new`
   (opens the browser).
2. **Qdrant Cloud** ([cloud.qdrant.io](https://cloud.qdrant.io)): create a free cluster, then an
   API key for it. Copy the cluster URL (ends in `:6333`) and the key.
3. **Neon** ([neon.tech](https://neon.tech)): create a project. On "Connect", turn
   **connection pooling off** and copy the connection string
   `postgresql://USER:PASSWORD@HOST/DB`. HOST is the part between `@` and `/`, including the
   region (e.g. `ep-xxx.c-16.us-east-1.aws.neon.tech`).
4. **Secrets**: copy `deploy/env.modal.example` to `.env.modal` in the project root, fill it in, and
   upload it to Modal:

   ```powershell
   modal secret create ragbot-env --from-dotenv .env.modal --force
   ```

## Deploy / update

```powershell
# 1. build the images and test them locally (see "Test locally" below)
docker compose build
docker build -f docker/modal.Dockerfile -t ragbot-modal:local .

# 2. publish, tagged with version + commit (never "latest")
$tag = "0.1.0-$(git rev-parse --short HEAD)"
foreach ($n in "api", "frontend", "modal") {
  docker tag "ragbot-${n}:local" "nusoftinc/ragbot-${n}:$tag"
  docker push "nusoftinc/ragbot-${n}:$tag"
}

# 3. put the new tag in IMAGE in deploy/modal_app.py, then
#    (the workspace defaults to image builder 2026.10, which modal 1.6.2 doesn't know yet;
#     2025.06 is the newest one it supports)
$env:MODAL_IMAGE_BUILDER_VERSION = "2025.06"
modal deploy deploy/modal_app.py
```

The site is at **https://rgambhir777--ragbot.us-east.modal.run**.

## Public or password-protected

`PUBLIC_ACCESS` in `modal_app.py` decides who may visit:

- `"true"` (**current setting**, owner decision 2026-11-09): anyone with the link, no login.
- `"false"`: the browser asks for `APP_USERNAME` / `APP_PASSWORD` from `.env.modal`. Without a
  password (12+ characters) the container refuses to start, so it can't go online unprotected by
  accident.

Changing it: edit the line, rebuild + push the `ragbot-modal` image with a new tag, put the tag in
`IMAGE`, and run `modal deploy` again (the steps above).

**Risks of public mode.** The app was built for one trusted user, so every visitor gets every feature:

| Risk | Why | Mitigation in place |
|---|---|---|
| OpenAI bill | each question is a paid call (~1 cent); scripts could ask thousands | **hard spending caps on the OpenAI key** (set by the owner) |
| Chats are shared | the sidebar lists *all* conversations; anyone can open or delete them | none: don't type anything private |
| Anyone can add content | file uploads and GitHub indexing are open; spam or prompt-injection text then shapes everyone's answers | few visitors; check *Knowledge base* now and then |
| Free storage fills up | Qdrant Cloud 1 GB, Neon 0.5 GB | — |
| Modal compute | steady traffic keeps the container awake | `max_containers=1` caps it at about $85/month worst case |
| Slow for everyone | one container | — |

If the link spreads further than planned, set `PUBLIC_ACCESS` back to `"false"`, or stop the site
at once with `modal app stop ragbot`.

## Test locally (before publishing)

Run the Modal image against the local compose databases, then the smoke test through the password:

```powershell
docker run --rm -d --name ragbot-modal-test --network ragbot_default -p 127.0.0.1:8090:8080 `
  -e OPENAI_API_KEY=... -e POSTGRES_PASSWORD=... -e QDRANT_URL=http://qdrant:6333 `
  -e POSTGRES_HOST=postgres -e TRACING_ENABLED=false -e APP_PASSWORD=<12+ characters> ragbot-modal:local
$env:SMOKE_BASE_URL = "http://127.0.0.1:8090"; $env:SMOKE_PASSWORD = "<same password>"
pytest -m smoke
docker rm -f ragbot-modal-test
```

## Checking the live site

```powershell
$env:SMOKE_BASE_URL = "https://rgambhir777--ragbot.us-east.modal.run"
$env:SMOKE_PASSWORD = "<APP_PASSWORD>"   # only when the site is password-protected
pytest -m smoke          # upload → ask → streamed, cited answer (≈ $0.005 of OpenAI)
modal app logs ragbot    # the container's logs
modal app stop ragbot    # take the site offline
```

## Costs and limits

- **Modal**: billed per second while the container runs (2 CPU cores, 3 GB). The Starter plan
  includes $30/month of free compute. The container stops after 5 minutes without requests, so
  occasional use stays within that.
- **Cold start**: the first visit after a pause takes about 15–20 s (measured 16 s on 2026-11-09);
  the first question after that also loads the reranker.
- **Requests** are cut off by Modal after 150 seconds. Answers take ~30 s; a very large upload or
  GitHub repo may need to be split.
- **One container at most** (`max_containers=1`): background ingest jobs run inside it. A job is
  lost if the container stops mid-way, which only happens after 5 idle minutes (the UI polls the job,
  which counts as activity while the page is open).
