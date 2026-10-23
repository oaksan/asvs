"""Contract and integration tests for AI REST Endpoints (US2).

Tests /api/ai/status, /api/ai/config, and /api/ai/test-connection ensuring:
- Safe masked responses (Zero-Leakage).
- Sanitized error handling.
- Hermetic mock HTTP transport for test-connection.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.ai_secrets import AISecretStore
from app.main import app


@pytest.fixture(autouse=True)
def clean_ai_store(monkeypatch):
    import sqlite3
    monkeypatch.delenv("AI_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("AI_MODEL_NAME", raising=False)
    AISecretStore.reset_instance()
    try:
        con = sqlite3.connect("asvs.db")
        con.execute("DELETE FROM useraiconfig;")
        con.commit()
        con.close()
    except Exception:
        pass
    yield
    AISecretStore.reset_instance()
    try:
        con = sqlite3.connect("asvs.db")
        con.execute("DELETE FROM useraiconfig;")
        con.commit()
        con.close()
    except Exception:
        pass


def test_ai_status_endpoint_unconfigured():
    client = TestClient(app)
    resp = client.get("/api/ai/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is False
    assert data["model_name"] is None
    assert data["key_masked"] is None


def test_ai_config_endpoint_saves_in_memory_and_masks_key():
    client = TestClient(app)
    raw_key = "AIzaSy_TEST_KEY_NOT_LEAKED_12345"
    payload = {"model_name": "gemini-2.0-flash", "api_key": raw_key}

    resp = client.post("/api/ai/config", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True
    assert data["model_name"] == "gemini-2.0-flash"
    assert data["key_masked"] == "••••••••"
    # Ensure real key is NOT in response JSON text
    assert raw_key not in resp.text

    # GET /api/ai/status should now reflect configured status without key
    status_resp = client.get("/api/ai/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["configured"] is True
    assert status_data["key_masked"] == "••••••••"
    assert raw_key not in status_resp.text


def test_ai_test_connection_endpoint_success(monkeypatch):
    # Mock httpx response for Gemini API
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "OK"}]}}
                ]
            },
        )

    mock_transport = httpx.MockTransport(mock_handler)
    mock_client = httpx.AsyncClient(transport=mock_transport)

    # Patch check_ai_connectivity in app.main
    from app import main
    original_check = main.check_ai_connectivity

    async def patched_check(model_name, api_key, **kwargs):
        return await original_check(model_name, api_key, http_client=mock_client)

    monkeypatch.setattr(main, "check_ai_connectivity", patched_check)

    client = TestClient(app)
    payload = {"model_name": "gemini-2.0-flash", "api_key": "AIzaSy_SAMPLE_KEY"}
    resp = client.post("/api/ai/test-connection", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["model_name"] == "gemini-2.0-flash"
    assert data["latency_ms"] >= 0
    assert "estabelecida com sucesso" in data["message"]
    assert "AIzaSy_SAMPLE_KEY" not in resp.text


def test_ai_test_connection_endpoint_auth_failure(monkeypatch):
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "Invalid API Key"}})

    mock_transport = httpx.MockTransport(mock_handler)
    mock_client = httpx.AsyncClient(transport=mock_transport)

    from app import main
    original_check = main.check_ai_connectivity

    async def patched_check(model_name, api_key, **kwargs):
        return await original_check(model_name, api_key, http_client=mock_client)

    monkeypatch.setattr(main, "check_ai_connectivity", patched_check)

    client = TestClient(app)
    payload = {"model_name": "gemini-2.0-flash", "api_key": "AIzaSy_INVALID_KEY"}
    resp = client.post("/api/ai/test-connection", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert "Falha de autenticação" in data["message"]
    assert "AIzaSy_INVALID_KEY" not in resp.text
