# The Python API image: FastAPI + the LangGraph agent + the FastEmbed models.
#
# Build (from the project root):  docker compose build api
#
# What makes it "production-credible":
# - slim official base image, pinned to an exact tag (never `latest`);
# - the embedding/reranker models and the tokenizer are baked in at build time, so a new
#   container starts without downloading ~200 MB and works without internet for search;
# - it runs as an unprivileged user, not root;
# - no secrets inside: the OpenAI key and passwords are passed in at runtime (docker-compose.yml).
FROM python:3.12.14-slim-trixie

# git: GitHub repo ingestion runs the `git` command (shallow clone). Nothing else is needed,
# because every Python dependency ships ready-made wheels (no compilers in the image).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FASTEMBED_CACHE_DIR=/opt/models/fastembed \
    TIKTOKEN_CACHE_DIR=/opt/models/tiktoken

WORKDIR /app

# Dependencies first: this slow layer is rebuilt only when requirements.txt changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Bake the models in. Only config.py is copied for this step, so editing app code later doesn't
# invalidate this layer and re-download the models. Model names come from Settings (defaults).
COPY app/__init__.py app/config.py app/
RUN python -c "\
from fastembed import SparseTextEmbedding, TextEmbedding; \
from fastembed.rerank.cross_encoder import TextCrossEncoder; \
import tiktoken; \
from app.config import Settings; \
s = Settings(); c = s.fastembed_cache_dir; \
TextEmbedding(s.embed_dense_model, cache_dir=c); \
SparseTextEmbedding(s.embed_sparse_model, cache_dir=c); \
TextCrossEncoder(s.rerank_model, cache_dir=c); \
tiktoken.get_encoding(s.tokenizer_encoding)"

# The application code (tests, docs and secrets are kept out by .dockerignore).
COPY app/ app/

# An unprivileged user: if the app were ever compromised, the attacker isn't root.
# It owns nothing in /app or /opt/models, so it can't modify the code or the models either.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000
# One worker process: the models are loaded once and shared; the agent runs turns in threads.
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
