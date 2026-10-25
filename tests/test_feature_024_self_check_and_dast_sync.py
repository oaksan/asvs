"""Automated TDD Test Suite for Feature 024: Self-Check & DAST/SAST Orchestrator State Synchronization.

Spec Reference: specs/024-fix-self-check-and-dast-orchestrator/spec.md
Plan Reference: specs/024-fix-self-check-and-dast-orchestrator/plan.md
Constitutional Principles: I (TDD), III (Agent Architecture & State), IV (Guardrails), V (Fluent UI & Stepper)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, select

from app.agents.dast_agent import DASTAgentOutput
from app.agents.orchestrator import OrchestratorAgent, OrchestratorInput, OrchestratorOutput
from app.agents.sast_agent import SASTAgentOutput
from app.agents.scoper import ScoperOutput
from app.core.ai_secrets import AISecretStore
from app.main import APP_UI_VERSION, app
from app.models import PipelineStage, Run, RunStatus

client = TestClient(app)


def test_orchestrator_default_timeout_is_180s() -> None:
    """FR-004: Default stage timeout in OrchestratorInput MUST be 180.0 seconds."""
    inp = OrchestratorInput(run_id=1)
    assert inp.stage_timeout_sec == 180.0


@pytest.mark.asyncio
async def test_orchestrator_timeout_emits_failed_for_both_sast_and_dast(tmp_path: Path) -> None:
    """FR-005: On timeout in concurrent SAST/DAST block, both SAST and DAST must emit stage_status='FAILED'."""
    db_file = tmp_path / "test_timeout.db"
    test_engine = create_engine(f"sqlite:///{db_file}")
    from sqlmodel import SQLModel
    SQLModel.metadata.create_all(test_engine)

    with Session(test_engine) as session:
        run = Run(
            user_id=1,
            owner_username="admin",
            source_type="workspace_path",
            source_path=str(tmp_path),
            target_url="http://localhost:8000",
            zap_authorized=True,
            zap_mode="active",
            status=RunStatus.PENDING.value,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id

    emitted_events: list[dict] = []

    orch = OrchestratorAgent(db_engine=test_engine)
    orch._emit = lambda run_id, **kwargs: emitted_events.append(kwargs)  # type: ignore

    # Mock scoper to enable DAST and return clean output
    mock_scoper_out = ScoperOutput(
        run_id=run_id,
        resolved_source_path=str(tmp_path),
        dast_enabled=True,
        summary_message="Scoper OK",
        code_files_count=5,
        total_files=5,
        languages={"python": 5},
    )

    async def slow_sast(*args, **kwargs):
        await asyncio.sleep(2.0)
        return SASTAgentOutput(run_id=run_id, summary_message="slow")

    with patch.object(orch.scoper, "run", return_value=mock_scoper_out), \
         patch.object(orch.sast_agent, "run", side_effect=lambda *a, **kw: asyncio.run(asyncio.sleep(2.0))), \
         patch.object(orch.dast_agent, "run", new_callable=AsyncMock) as mock_dast:
        mock_dast.return_value = DASTAgentOutput(
            run_id=run_id,
            dast_executed=True,
            urls_crawled=1,
            summary_message="DAST OK",
        )

        inp = OrchestratorInput(
            run_id=run_id,
            source_path=str(tmp_path),
            target_url="http://localhost:8000",
            stage_timeout_sec=0.1,
        )
        out = await orch.execute(inp)

    assert out.final_status == RunStatus.FAILED.value

    # Verify both SAST and DAST received FAILED events
    sast_failed = any(
        e.get("stage") == PipelineStage.SAST.value and e.get("stage_status") == "FAILED"
        for e in emitted_events
    )
    dast_failed = any(
        e.get("stage") == PipelineStage.DAST.value and e.get("stage_status") == "FAILED"
        for e in emitted_events
    )
    assert sast_failed, f"Expected SAST FAILED event in {emitted_events}"
    assert dast_failed, f"Expected DAST FAILED event in {emitted_events}"


def test_api_runs_accepts_self_check_payload(auth_admin_client: TestClient, db_session: Session) -> None:
    """FR-001: POST /api/runs natively accepts self-check workspace_path='app' payload."""
    AISecretStore.get_instance().set_credentials(
        api_key="test-key-024",
        model_name="gemini-2.0-flash",
        provider="gemini",
    )
    with patch("app.agents.orchestrator.OrchestratorAgent.execute", new_callable=AsyncMock):
        resp = auth_admin_client.post(
            "/api/runs",
            json={
                "source_type": "workspace_path",
                "workspace_subpath": "app",
                "target_url": "http://localhost:8000",
                "zap_authorized": True,
                "zap_mode": "active",
            },
        )
    assert resp.status_code == 202
    data = resp.json()
    assert data["ok"] is True
    run_id = data["run_id"]

    run_row = db_session.get(Run, run_id)
    assert run_row is not None
    assert run_row.source_type == "workspace_path"
    assert run_row.source_path.endswith("app")
    assert run_row.target_url == "http://localhost:8000"
    assert run_row.zap_authorized is True
    assert run_row.zap_mode == "active"


def test_ui_assets_decouple_self_check_and_bump_version_024() -> None:
    """FR-001 / FR-006: app.js contains decoupled selfCheckBtn implementation and version 024."""
    root = Path(__file__).resolve().parent.parent
    html = (root / "templates" / "index.html").read_text(encoding="utf-8")
    js = (root / "static" / "app.js").read_text(encoding="utf-8")

    # index.html version
    assert "v=024" in html
    assert "Versão 024" in html or "Versão {{ app_version }}" in html

    # app.js decoupled self-check call
    assert 'workspace_subpath: "app"' in js
    assert 'source_type: "workspace_path"' in js

    # app/main.py version
    assert APP_UI_VERSION == "024"
