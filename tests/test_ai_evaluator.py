"""Unit tests for AIEvaluatorAgent and ai_aci.run_ai_evaluation (US3).

Validates:
1. run_ai_evaluation with mocked Gemini JSON response emitting PASS.
2. run_ai_evaluation with mocked Gemini JSON response emitting FAIL.
3. Fallback to MANUAL_REQUIRED when AI credentials are not configured.
4. AIEvaluatorAgent integration creating findings on FAIL.
5. Path confinement guardrail on invalid source_path.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from sqlmodel import Session, select

from app.aci.ai_aci import run_ai_evaluation
from app.agents.ai_evaluator_agent import (
    AIEvaluatorAgent,
    AIEvaluatorAgentInput,
)
from app.core.ai_secrets import AISecretStore
from app.database import engine, init_db
from app.models import Finding, Run, RunStatus, ToolCall


@pytest.fixture(autouse=True)
def setup_db_and_secrets():
    init_db()
    AISecretStore.reset_instance()
    yield
    AISecretStore.reset_instance()


@pytest.fixture
def test_run():
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
        return run


@pytest.mark.asyncio
async def test_run_ai_evaluation_unconfigured_fallback(test_run):
    """When AI is not configured, run_ai_evaluation returns MANUAL_REQUIRED."""
    with Session(engine) as session:
        res = await run_ai_evaluation(
            session,
            run_id=test_run.id,
            req_id="V1.3.1",
            source_path="app",
        )
        assert res.ok is True
        assert res.data["verdict"] == "MANUAL_REQUIRED"
        assert "não configurado" in res.data["rationale"]

        # Check ToolCall recorded
        tc = session.exec(
            select(ToolCall).where(
                ToolCall.run_id == test_run.id,
                ToolCall.aci_name == "ai_aci",
                ToolCall.command == "run_ai_evaluation",
            )
        ).first()
        assert tc is not None
        assert "MANUAL_REQUIRED" in tc.output_summary


@pytest.mark.asyncio
async def test_run_ai_evaluation_pass_with_mock_client(test_run):
    """When Gemini returns PASS JSON, run_ai_evaluation outputs PASS with high confidence."""
    store = AISecretStore.get_instance()
    store.set_credentials("gemini-2.0-flash", "test-api-key-12345")

    mock_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "verdict": "PASS",
                                    "confidence": "HIGH",
                                    "rationale": "Autoescape Jinja2 ativo e sem HTML sanitizado desprotegido.",
                                    "evidence_snippets": ["templates/index.html"],
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_gemini_response

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_resp

    with Session(engine) as session:
        res = await run_ai_evaluation(
            session,
            run_id=test_run.id,
            req_id="V1.3.1",
            source_path="app",
            http_client=mock_client,
        )

        assert res.ok is True
        assert res.data["verdict"] == "PASS"
        assert res.data["confidence"] == "HIGH"
        assert "Autoescape" in res.data["rationale"]
        assert "templates/index.html" in res.data["evidence_snippets"]


@pytest.mark.asyncio
async def test_ai_evaluator_agent_fail_creates_finding(test_run):
    """When AI evaluator returns FAIL, AIEvaluatorAgent persists a Finding."""
    store = AISecretStore.get_instance()
    store.set_credentials("gemini-2.0-flash", "test-api-key-12345")

    mock_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "verdict": "FAIL",
                                    "confidence": "HIGH",
                                    "rationale": "Uso de |safe em input sem sanitização detectado.",
                                    "evidence_snippets": ["app/views.py"],
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_gemini_response

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_resp

    agent = AIEvaluatorAgent()
    with Session(engine) as session:
        output = await agent.run(
            session,
            AIEvaluatorAgentInput(
                run_id=test_run.id,
                source_path="app",
                req_ids=["V1.3.1"],
            ),
            http_client=mock_client,
        )

        assert output.evaluations_by_req["V1.3.1"]["verdict"] == "FAIL"

        # Check Finding was persisted
        finding = session.exec(
            select(Finding).where(
                Finding.run_id == test_run.id,
                Finding.req_id == "V1.3.1",
                Finding.tool == "ai_evaluator",
            )
        ).first()
        assert finding is not None
        assert "Violação identificada pelo AIEvaluatorAgent" in finding.title


@pytest.mark.asyncio
async def test_run_ai_evaluation_confinement_guardrail(test_run):
    """Paths outside confined root are blocked by guardrail."""
    with Session(engine) as session:
        res = await run_ai_evaluation(
            session,
            run_id=test_run.id,
            req_id="V1.3.1",
            source_path="/etc/shadow",
            base_root=Path("/home/user/felipe/speckit/asvs"),
        )
        assert res.ok is False
        assert res.data["verdict"] == "INCONCLUSIVE"
        assert "Bloqueio de guardrail" in res.summary_message
