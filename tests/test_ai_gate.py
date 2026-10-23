"""Tests for AI Configuration Prerequisite Gate (US2).

Ensures that any attempt to start an assessment run (POST /api/runs) or rerun (POST /api/runs/{id}/rerun)
without active AI provider credentials in volatile memory is strictly rejected with HTTP 412 Precondition Failed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.agents.orchestrator import OrchestratorAgent
from app.core.ai_secrets import AISecretStore
from app.database import init_db
from app.main import app, get_orchestrator


@pytest.fixture(autouse=True)
def setup_test_env():
    import sqlite3
    init_db()
    store = AISecretStore.get_instance()
    store.clear_credentials()
    try:
        con = sqlite3.connect("asvs.db")
        con.execute("DELETE FROM useraiconfig;")
        con.commit()
        con.close()
    except Exception:
        pass
    yield
    store.clear_credentials()
    try:
        con = sqlite3.connect("asvs.db")
        con.execute("DELETE FROM useraiconfig;")
        con.commit()
        con.close()
    except Exception:
        pass


def _mock_orchestrator() -> OrchestratorAgent:
    mock_orch = AsyncMock(spec=OrchestratorAgent)
    mock_orch.execute = AsyncMock(return_value=None)
    return mock_orch


def test_create_run_without_ai_configured_returns_412():
    """US2 / SC-002: Backend strictly returns HTTP 412 if AI is not configured."""
    client = TestClient(app)
    payload = {
        "source_type": "workspace_path",
        "workspace_subpath": "tests/vulnerable_app",
        "target_url": None,
        "zap_authorized": True,
        "zap_mode": "baseline",
    }
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 412
    data = response.json()
    assert "Pré-requisito de IA não atendido" in data["detail"]
    assert "provedor de IA generativa deve ser configurado" in data["detail"]


def test_create_run_accepted_after_configuring_ai_via_api():
    """US2: Run is accepted (HTTP 202) when AI is configured via POST /api/ai/config and zap_authorized=True."""
    app.dependency_overrides[get_orchestrator] = _mock_orchestrator
    try:
        client = TestClient(app)

        # 1. Configure AI credentials
        cfg_resp = client.post(
            "/api/ai/config",
            json={"model_name": "gemini-2.0-flash", "api_key": "dummy-valid-key"},
        )
        assert cfg_resp.status_code == 200
        assert cfg_resp.json()["configured"] is True

        # 2. Submit run
        payload = {
            "source_type": "workspace_path",
            "workspace_subpath": "tests/vulnerable_app",
            "target_url": None,
            "zap_authorized": True,
            "zap_mode": "baseline",
        }
        response = client.post("/api/runs", json=payload)
        assert response.status_code == 202
        data = response.json()
        assert "run_id" in data
        assert data["status"] == "PENDING"
    finally:
        app.dependency_overrides.pop(get_orchestrator, None)


def test_rerun_returns_412_if_ai_is_cleared():
    """US2: Rerun endpoint POST /api/runs/{id}/rerun returns HTTP 412 if credentials were cleared."""
    app.dependency_overrides[get_orchestrator] = _mock_orchestrator
    try:
        client = TestClient(app)
        store = AISecretStore.get_instance()
        store.set_credentials("gemini-2.0-flash", "initial-key")

        # Create valid run
        payload = {
            "source_type": "workspace_path",
            "workspace_subpath": "tests/vulnerable_app",
            "target_url": None,
            "zap_authorized": True,
            "zap_mode": "baseline",
        }
        res_create = client.post("/api/runs", json=payload)
        assert res_create.status_code == 202
        run_id = res_create.json()["run_id"]

        # Clear AI credentials
        store.clear_credentials()
        assert store.is_configured() is False

        # Attempt rerun
        res_rerun = client.post(f"/api/runs/{run_id}/rerun")
        assert res_rerun.status_code == 412
        data = res_rerun.json()
        assert "Pré-requisito de IA não atendido" in data["detail"]
    finally:
        app.dependency_overrides.pop(get_orchestrator, None)
