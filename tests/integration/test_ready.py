"""End-to-end readiness against the real services.

Needs `docker compose up -d` and a valid OPENAI_API_KEY in .env. Skipped by default; run with:

    pytest -m "integration"
"""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

pytestmark = [pytest.mark.integration, pytest.mark.openai]


def test_all_real_dependencies_are_ready() -> None:
    with TestClient(create_app(Settings())) as client:
        response = client.get("/ready")
    body = response.json()
    failing = {name: check["detail"] for name, check in body["checks"].items() if not check["ok"]}
    assert response.status_code == 200, f"not ready: {failing}"
