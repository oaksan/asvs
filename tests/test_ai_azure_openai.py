"""Tests for Azure OpenAI integration and dedicated AI Playground (spec 006)."""

import pytest
from fastapi.testclient import TestClient

from app.core.ai_secrets import AISecretStore
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_secrets():
    AISecretStore.reset_instance()
    yield
    AISecretStore.reset_instance()


def test_ai_secrets_azure_openai_configuration():
    """Verify AISecretStore stores Azure OpenAI credentials with Zero-Leakage masking."""
    store = AISecretStore.get_instance()
    assert not store.is_configured()

    store.set_credentials(
        model_name="azure-gpt5",
        api_key="sk-test-azure-secret-key-12345",
        provider="azureopenai",
        resource_name="my-resource",
        deployment_id="azure-gpt5",
        api_version="2024-06-01",
    )

    assert store.is_configured()
    assert store.get_provider() == "azureopenai"
    assert store.get_resource_name() == "my-resource"
    assert store.get_deployment_id() == "azure-gpt5"
    assert store.get_api_version() == "2024-06-01"

    status = store.get_masked_status()
    assert status["configured"] is True
    assert status["provider"] == "azureopenai"
    assert status["resource_name"] == "my-resource"
    assert status["deployment_id"] == "azure-gpt5"
    assert status["key_masked"] == "••••••••"
    assert "sk-test-azure-secret-key-12345" not in str(status)


def test_post_ai_config_azure_openai_endpoint():
    """Verify POST /api/ai/config accepts Azure OpenAI payload."""
    payload = {
        "service": "azureopenai",
        "service_settings": {
            "resource_name": "corp-openai",
            "deployment_id": "azure-gpt5",
            "api_version": "2024-06-01",
            "api_key": "sk-secret-corporate-key",
        },
    }
    resp = client.post("/api/ai/config", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True
    assert data["provider"] == "azureopenai"
    assert data["key_masked"] == "••••••••"
    assert "sk-secret-corporate-key" not in resp.text


def test_post_ai_chat_test_endpoint_mock(monkeypatch):
    """Verify POST /api/ai/chat-test routes message to model and returns response."""
    from app.aci import ai_aci

    async def fake_chat(*args, **kwargs):
        return {
            "ok": True,
            "response_text": "Olá! Conexão com Azure OpenAI bem sucedida.",
            "latency_ms": 142,
            "model_used": "azure-gpt5",
            "provider": "azureopenai",
        }

    monkeypatch.setattr(ai_aci, "chat_with_ai", fake_chat)

    resp = client.post(
        "/api/ai/chat-test",
        json={"message": "Olá, teste de conexão"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "Azure OpenAI" in data["response_text"]
    assert data["latency_ms"] == 142


def test_ui_contains_dedicated_ai_tab():
    """Verify that GET / contains the dedicated 5th tab and panel."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert 'id="tab-ai-config"' in html
    assert 'id="panel-ai-config"' in html
    assert 'id="azure-resource-name"' in html
    assert 'id="azure-deployment-id"' in html
    assert 'id="ai-chat-input"' in html


@pytest.mark.asyncio
async def test_azure_openai_gpt54_uses_max_completion_tokens_in_connectivity_chat_and_eval():
    """Feature 011 (US1): Verify Azure OpenAI requests use max_completion_tokens and succeed on gpt-5.4."""
    import json
    import httpx
    from sqlmodel import Session
    from app.aci.ai_aci import check_ai_connectivity, chat_with_ai, run_ai_evaluation
    from app.database import engine, init_db
    from app.models import Run, RunStatus

    init_db()
    captured_payloads = []

    def strict_gpt54_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        captured_payloads.append(body)
        if "max_tokens" in body:
            return httpx.Response(
                400,
                json={
                    "error": {
                        "message": "Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.",
                        "type": "invalid_request_error",
                        "param": "max_tokens",
                        "code": "unsupported_parameter",
                    }
                },
            )
        assert "max_completion_tokens" in body
        return httpx.Response(
            200,
            json={
                "model": "gpt-5.4-2026-03-05",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "verdict": "PASS",
                                    "confidence": "HIGH",
                                    "rationale": "Autoescape ativo validado pelo GPT-5.4.",
                                    "evidence_snippets": ["app/main.py"],
                                }
                            ),
                        }
                    }
                ],
            },
        )

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(strict_gpt54_handler))

    # 1. check_ai_connectivity
    conn_res = await check_ai_connectivity(
        model_name="gpt-5.4",
        api_key="azure-secret-key-gpt54",
        provider="azureopenai",
        resource_name="cog-fcb-generai-poc01",
        deployment_id="gpt-5.4",
        api_version="2024-12-01-preview",
        http_client=mock_client,
    )
    assert conn_res["ok"] is True
    assert conn_res["model_name"] == "gpt-5.4"

    # 2. chat_with_ai
    store = AISecretStore.get_instance()
    store.set_credentials(
        model_name="gpt-5.4",
        api_key="azure-secret-key-gpt54",
        provider="azureopenai",
        resource_name="cog-fcb-generai-poc01",
        deployment_id="gpt-5.4",
        api_version="2024-12-01-preview",
    )
    chat_res = await chat_with_ai("Teste GPT-5.4", http_client=mock_client)
    assert chat_res["ok"] is True

    # 3. run_ai_evaluation
    with Session(engine) as session:
        run = Run(
            source_type="workspace_path",
            source_path="app",
            status=RunStatus.RUNNING.value,
            current_stage="AI_EVALUATION",
        )
        session.add(run)
        session.commit()
        session.refresh(run)

        eval_res = await run_ai_evaluation(
            session,
            run_id=run.id,
            req_id="V1.3.1",
            source_path="app",
            http_client=mock_client,
        )
        assert eval_res.ok is True
        assert eval_res.data["verdict"] == "PASS"

    assert len(captured_payloads) == 3
    await mock_client.aclose()


@pytest.mark.asyncio
async def test_azure_openai_auto_fallback_on_unsupported_temperature_or_max_tokens():
    """Feature 011 (US1): Verify automatic retry if a model rejects temperature or max_completion_tokens."""
    import json
    import httpx
    from app.aci.ai_aci import chat_with_ai

    calls = []

    def fallback_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        calls.append(body)
        if "temperature" in body and body["temperature"] != 1:
            return httpx.Response(
                400,
                json={
                    "error": {
                        "message": "Unsupported value: 'temperature' does not support 0.3 with this model. Only the default (1) value is supported.",
                        "param": "temperature",
                        "code": "unsupported_value",
                    }
                },
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Resposta após fallback automático de temperature."}}]},
        )

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(fallback_handler))
    res = await chat_with_ai(
        "Olá",
        provider="azureopenai",
        resource_name="cog-fcb-generai-poc01",
        deployment_id="gpt-5.4",
        api_version="2024-12-01-preview",
        api_key="secret-key-xyz",
        http_client=mock_client,
    )
    assert res["ok"] is True
    assert "fallback" in res["response_text"]
    assert len(calls) >= 1
    await mock_client.aclose()


def test_normalize_azure_settings_extracts_from_full_endpoint_url():
    """Feature 011 (US2): Verify full Azure OpenAI URL in resource_name is decomposed into resource, deployment, and api_version."""
    from app.aci.ai_aci import normalize_azure_settings

    full_url = "https://cog-fcb-generai-poc01.openai.azure.com/openai/deployments/gpt-5.4/chat/completions?api-version=2024-12-01-preview"
    res, dep, ver = normalize_azure_settings(full_url, "azure-gpt5", "2024-06-01")
    assert res == "cog-fcb-generai-poc01"
    assert dep == "gpt-5.4"
    assert ver == "2024-12-01-preview"

    # Also test via POST /api/ai/config
    payload = {
        "service": "azureopenai",
        "service_settings": {
            "resource_name": full_url,
            "deployment_id": "azure-gpt5",
            "api_version": "2024-06-01",
            "api_key": "sk-secret-corporate-key",
        },
    }
    resp = client.post("/api/ai/config", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["resource_name"] == "cog-fcb-generai-poc01"
    assert data["deployment_id"] == "gpt-5.4"
    assert data["api_version"] == "2024-12-01-preview"


@pytest.mark.asyncio
async def test_azure_openai_400_error_surfaces_sanitized_provider_detail():
    """Feature 011 (US1/FR-004): Verify HTTP 400 surfaces sanitized error detail without leaking api_key."""
    import httpx
    from app.aci.ai_aci import check_ai_connectivity

    secret_key = "SUPER_SECRET_AZURE_KEY_999"

    def bad_request_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "message": f"Invalid parameter XYZ with key {secret_key}",
                    "code": "invalid_request_error",
                }
            },
        )

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(bad_request_handler))
    res = await check_ai_connectivity(
        model_name="gpt-5.4",
        api_key=secret_key,
        provider="azureopenai",
        resource_name="cog-fcb-generai-poc01",
        deployment_id="gpt-5.4",
        api_version="2024-12-01-preview",
        http_client=mock_client,
    )
    assert res["ok"] is False
    assert "Invalid parameter XYZ" in res["message"]
    assert secret_key not in res["message"]
    assert "••••••••" in res["message"]
    await mock_client.aclose()


