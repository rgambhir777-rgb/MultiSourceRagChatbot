"""Application settings: the ONLY place environment variables are read.

Values come from real environment variables first, then from the `.env` file, then from the
defaults below. Each field is type-checked at startup, so a typo in `.env` fails fast with a
clear error instead of surfacing later as a confusing bug.
"""

from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import quote

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh", "max"]


class Settings(BaseSettings):
    """Typed view of every setting in `.env.example`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # `KEY=` (empty) in .env means "not set", so the default below applies.
        env_ignore_empty=True,
    )

    # ---------- App ----------
    app_env: Literal["dev", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    api_host: str = "127.0.0.1"  # docker compose sets 0.0.0.0 inside the container
    api_port: int = Field(default=8000, ge=1, le=65535)
    frontend_port: int = Field(default=8080, ge=1, le=65535)
    health_check_timeout_s: float = Field(default=5.0, gt=0)

    # ---------- LLM (OpenAI) ----------
    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = None
    llm_generator_model: str = "gpt-6.1-sol"
    llm_generator_reasoning_effort: ReasoningEffort = "low"
    llm_judge_model: str = "gpt-6-luna"
    llm_judge_reasoning_effort: ReasoningEffort = "none"
    llm_max_output_tokens: int = Field(default=1024, gt=0)
    prompt_max_tokens: int = Field(default=8000, gt=0)
    llm_request_timeout_s: float = Field(default=60.0, gt=0)
    llm_max_retries: int = Field(default=2, ge=0)
    llm_generator_price_in: float = Field(default=2.00, ge=0)
    llm_generator_price_out: float = Field(default=10.00, ge=0)
    llm_judge_price_in: float = Field(default=0.10, ge=0)
    llm_judge_price_out: float = Field(default=0.50, ge=0)

    # ---------- Embeddings & reranking ----------
    embed_dense_model: str = "BAAI/bge-small-en-v1.5"
    embed_sparse_model: str = "Qdrant/bm25"
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    fastembed_cache_dir: str = "./.cache/fastembed"

    # ---------- Retrieval ----------
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str = "knowledge_base"
    retrieve_candidates: int = Field(default=20, gt=0)
    rerank_top_k: int = Field(default=5, gt=0)

    # ---------- Chunking ----------
    chunk_size_tokens: int = Field(default=500, gt=0)
    chunk_overlap_tokens: int = Field(default=75, ge=0)

    # ---------- Agent loop guards ----------
    max_query_rewrites: int = Field(default=2, ge=0)
    max_regenerations: int = Field(default=1, ge=0)
    history_max_turns: int = Field(default=10, gt=0)

    # ---------- PostgreSQL ----------
    postgres_host: str = "localhost"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = "ragbot"
    postgres_user: str = "ragbot"
    postgres_password: SecretStr = SecretStr("change-me-local-only")

    # ---------- Ingestion limits ----------
    max_upload_mb: int = Field(default=25, gt=0)
    # NoDecode: read ".pdf,.md" as plain text; the validator below splits it into a list.
    allowed_file_types: Annotated[list[str], NoDecode] = [".pdf", ".md", ".txt", ".docx"]
    github_max_files: int = Field(default=2000, gt=0)
    github_max_file_kb: int = Field(default=500, gt=0)
    github_clone_timeout_s: float = Field(default=120.0, gt=0)
    github_token: SecretStr | None = None

    # ---------- Observability ----------
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment_name: str = "agentic-rag"
    tracing_enabled: bool = True

    @field_validator("allowed_file_types", mode="before")
    @classmethod
    def _split_file_types(cls, value: object) -> object:
        """Accept a comma-separated string and normalise to lowercase extensions."""
        if isinstance(value, str):
            value = [part for part in value.split(",") if part.strip()]
        if isinstance(value, list):
            return [str(ext).strip().lower() for ext in value]
        return value

    @property
    def postgres_conninfo(self) -> str:
        """Connection URL for psycopg. Contains the password, so never log it."""
        password = quote(self.postgres_password.get_secret_value(), safe="")
        user = quote(self.postgres_user, safe="")
        return (
            f"postgresql://{user}:{password}@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process and reuse them everywhere."""
    return Settings()
