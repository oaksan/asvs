"""Tests for DAST Authorization Guardrail (US1).

Ensures that any attempt to start an assessment run with a target_url without explicit
consent (zap_authorized=True) is strictly rejected with HTTP 403 Forbidden on the backend.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.database import init_db
from app.main import app


@pytest.fixture(autouse=True)
def setup_database():
    init_db()


def test_create_run_with_target_url_and_unauthorized_dast_returns_403():
    """FR-001 / SC-001: Backend strictly blocks runs with target_url when zap_authorized is False."""
    client = TestClient(app)
    payload = {
        "source_type": "workspace_path",
        "workspace_subpath": "app",
        "target_url": "http://localhost:8000",
        "zap_authorized": False,
        "zap_mode": "baseline",
    }
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 403
    data = response.json()
    assert "Guardrail DAST acionado" in data["detail"]
    assert "É obrigatório declarar autorização explícita" in data["detail"]


def test_create_run_without_target_url_and_unauthorized_dast_returns_403():
    """US1 / SC-001: Backend strictly blocks SAST-only runs without DAST consent."""
    client = TestClient(app)
    payload = {
        "source_type": "workspace_path",
        "workspace_subpath": "tests/vulnerable_app",
        "target_url": None,
        "zap_authorized": False,
        "zap_mode": "baseline",
    }
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 403
    data = response.json()
    assert "Guardrail DAST acionado" in data["detail"]
    assert "É obrigatório declarar autorização explícita" in data["detail"]


def test_create_run_with_authorized_dast_and_ai_configured_is_accepted():
    """Given zap_authorized=True and AI configured, the run must be accepted."""
    from app.core.ai_secrets import AISecretStore
    AISecretStore.get_instance().set_credentials("gemini-2.0-flash", "test-valid-key")

    client = TestClient(app)
    payload = {
        "source_type": "workspace_path",
        "workspace_subpath": "tests/vulnerable_app",
        "target_url": "http://localhost:8000",
        "zap_authorized": True,
        "zap_mode": "baseline",
    }
    response = client.post("/api/runs", json=payload)
    assert response.status_code in (200, 201, 202)
    data = response.json()
    assert "run_id" in data

