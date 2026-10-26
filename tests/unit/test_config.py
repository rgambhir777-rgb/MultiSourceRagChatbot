"""Tests for app.config: defaults, env parsing, validation and secret handling."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_defaults_match_the_locked_stack() -> None:
    settings = Settings(_env_file=None)
    assert settings.llm_generator_model == "gpt-6.1-sol"
    assert settings.llm_judge_model == "gpt-6-luna"
    assert settings.llm_judge_reasoning_effort == "none"
    assert settings.api_host == "127.0.0.1"
    assert settings.openai_api_key is None


def test_local_service_defaults_use_ipv4_loopback() -> None:
    # "localhost" can resolve to IPv6 ::1 first; our container ports listen on IPv4 only,
    # so some drivers (psycopg) hang until timeout before falling back. Use 127.0.0.1.
    settings = Settings(_env_file=None)
    assert settings.postgres_host == "127.0.0.1"
    assert settings.qdrant_url.startswith("http://127.0.0.1:")
    assert settings.mlflow_tracking_uri.startswith("http://127.0.0.1:")


def test_secrets_are_masked_when_printed() -> None:
    settings = Settings(_env_file=None, openai_api_key="sk-secret-123", postgres_password="pw")
    text = repr(settings) + str(settings.model_dump())
    assert "sk-secret-123" not in text
    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "sk-secret-123"


def test_environment_variables_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_GENERATOR_MODEL", "gpt-6-luna")
    monkeypatch.setenv("API_PORT", "9000")
    settings = Settings(_env_file=None)
    assert settings.llm_generator_model == "gpt-6-luna"
    assert settings.api_port == 9000


def test_empty_env_value_means_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("QDRANT_API_KEY", "")
    settings = Settings(_env_file=None)
    assert settings.openai_api_key is None
    assert settings.qdrant_api_key is None


def test_allowed_file_types_parsed_from_comma_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_FILE_TYPES", ".PDF, .md,,.txt")
    assert Settings(_env_file=None).allowed_file_types == [".pdf", ".md", ".txt"]


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("llm_judge_reasoning_effort", "turbo"),
        ("api_port", "70000"),
        ("app_env", "staging"),
        ("llm_max_output_tokens", "0"),
    ],
)
def test_invalid_values_fail_fast(
    monkeypatch: pytest.MonkeyPatch, field: str, bad_value: str
) -> None:
    monkeypatch.setenv(field.upper(), bad_value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_chunk_overlap_must_be_smaller_than_chunk_size() -> None:
    with pytest.raises(ValidationError, match="must be smaller than CHUNK_SIZE_TOKENS"):
        Settings(_env_file=None, chunk_size_tokens=100, chunk_overlap_tokens=100)


def test_postgres_conninfo_escapes_special_characters() -> None:
    settings = Settings(_env_file=None, postgres_password="p@ss:w/rd", postgres_host="db")
    assert settings.postgres_conninfo == "postgresql://ragbot:p%40ss%3Aw%2Frd@db:5432/ragbot"
