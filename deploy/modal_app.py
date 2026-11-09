"""Modal deployment of the chatbot: one public, password-protected web address.

What runs where:
- Modal runs ONE container from our Docker Hub image `ragbot-modal` (docker/modal.Dockerfile):
  nginx (the React app + password check) in front of the API (FastAPI + agent + embedding models).
- Qdrant and Postgres are hosted services (Qdrant Cloud, Neon), reached over the internet.
- Every secret (OpenAI key, database passwords, the site password) comes from the Modal Secret
  `ragbot-env`, created from your local, git-ignored `.env.modal` (see deploy/README.md).

Deploy (from the project root, with the venv active):

    modal deploy deploy/modal_app.py

Cost: Modal bills per second while the container runs. It starts on the first visit (about a
minute: image start + model loading) and stops after SCALEDOWN_S seconds without traffic.
"""

import subprocess

import modal

# The image to run: tagged with the app version + git commit, never `latest`, so git shows
# exactly which build is deployed. Change it when you publish a new image (deploy/README.md).
IMAGE = "docker.io/nusoftinc/ragbot-modal:0.1.0-f04bf30"

PORT = 8080  # nginx inside the container (deploy/nginx-modal.conf)
CPU_CORES = 2.0  # embedding + reranking run on the CPU
MEMORY_MB = 3072  # the API uses ~1.1 GB with all three models loaded; headroom for big uploads
SCALEDOWN_S = 300  # stop (and stop billing) after 5 minutes without requests
STARTUP_TIMEOUT_S = 240  # first start pulls the image and loads the models
MAX_CONTAINERS = 1  # one copy: background ingest jobs and their progress live in one process

image = modal.Image.from_registry(IMAGE).env(
    {
        "APP_ENV": "prod",
        "TRACING_ENABLED": "false",  # there is no MLflow server on Modal
        "PGSSLMODE": "require",  # Neon only accepts encrypted connections
    }
)

app = modal.App("ragbot")


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("ragbot-env")],
    cpu=CPU_CORES,
    memory=MEMORY_MB,
    max_containers=MAX_CONTAINERS,
    scaledown_window=SCALEDOWN_S,
    timeout=600,
)
@modal.concurrent(max_inputs=50)  # one container serves many browser requests at once
@modal.web_server(port=PORT, startup_timeout=STARTUP_TIMEOUT_S, label="ragbot")
def web() -> None:
    """Start nginx + the API; Modal sends traffic once port 8080 accepts connections."""
    subprocess.Popen(["/usr/local/bin/python", "/opt/ragbot/start_web.py"])
