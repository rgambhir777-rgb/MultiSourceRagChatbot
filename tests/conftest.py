"""Shared pytest fixtures.

Unit tests build Settings with `_env_file=None`, so they never read your real `.env` or API key.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    """Settings independent of the developer's .env, with a fake OpenAI key."""
    return Settings(
        _env_file=None,
        openai_api_key="sk-test-not-a-real-key",
        log_level="WARNING",
        tracing_enabled=False,  # unit tests never talk to MLflow
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """A test client; entering the `with` block runs the app's startup (lifespan)."""
    with TestClient(create_app(settings)) as test_client:
        yield test_client
