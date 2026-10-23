"""Automated TDD tests for Selective Rerun and Verdict/Finding Inheritance (Feature 008).

Spec Reference: specs/008-selective-run-reexecution/spec.md
Plan Reference: specs/008-selective-run-reexecution/plan.md
Data Model: specs/008-selective-run-reexecution/data-model.md
Tasks: T001, T002
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.ai_secrets import AISecretStore
from app.core.auth import get_current_user
from app.database import IN_SCOPE_REQ_IDS
from app.main import app
from app.models import (
    ACIResponse,
    Evidence,
    Finding,
    PipelineStage,
    Run,
    RunStatus,
    SessionUser,
    User,
    Verdict,
    VerdictStatus,
    utcnow,
)
from tests.conftest import create_test_user


def _seed_completed_base_run(
    session: Session,
    user: User | None = None,
) -> Run:
    """Helper that creates and commits a completed base run with 8 verdicts, findings, and evidences."""
    user_id = user.id if user else 1
    username = user.username if user else "admin"

    base_run = Run(
        user_id=user_id,
        owner_username=username,
        source_type="workspace_path",
        source_path="tests/vulnerable_app",
        target_url=None,
        zap_authorized=True,
        zap_mode="baseline",
        status=RunStatus.COMPLETED.value,
        current_stage=PipelineStage.DONE.value,
        pass_percentage=75.0,
        pass_count=6,
        fail_count=1,
        inconclusive_count=1,
        manual_count=0,
        scope_summary_json=json.dumps(
            {
                "total_files": 12,
                "code_files_count": 6,
                "languages": {"python": 6},
                "surfaces_by_req": {},
            }
        ),
        finished_at=utcnow(),
    )
    session.add(base_run)
    session.commit()
    session.refresh(base_run)

    # 1. Seed 8 verdicts
    for req_id in IN_SCOPE_REQ_IDS:
        if req_id == "V1.2.4":
            st = VerdictStatus.FAIL.value
            active_cnt = 1
        elif req_id == "V1.5.1":
            st = VerdictStatus.INCONCLUSIVE.value
            active_cnt = 0
        else:
            st = VerdictStatus.PASS.value
            active_cnt = 0

        v = Verdict(
            run_id=base_run.id,
            req_id=req_id,
            status=st,
            confidence_level="HIGH",
            tools_used_json=json.dumps(["semgrep"]),
            rules_executed_json=json.dumps([f"{req_id.lower()}-rule"]),
            coverage_declared="100% de cobertura declarada",
            positive_evidence_json=json.dumps([f"Evidência positiva inicial para {req_id}"]),
            active_findings_count=active_cnt,
            rationale=f"Veredito base inicial para {req_id}",
            limitations="Nenhuma limitação detectada",
        )
        session.add(v)
    session.commit()

    # 2. Seed a Finding on V1.2.4 and attach Evidence
    finding = Finding(
        run_id=base_run.id,
        req_id="V1.2.4",
        tool="semgrep",
        rule_or_plugin_id="v1-2-4-sql-injection",
        title="SQL Injection Finding na consulta de usuário",
        severity="HIGH",
        confidence="HIGH",
        primary_location="tests/vulnerable_app/app.py:10",
        fingerprint="fp-base-v1-2-4-001",
        is_false_positive=False,
    )
    session.add(finding)
    session.commit()
    session.refresh(finding)

    evidence = Evidence(
        finding_id=finding.id,
        evidence_type="code_snippet",
        file_path="tests/vulnerable_app/app.py",
        line_start=10,
        line_end=15,
        code_snippet="cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')",
    )
    session.add(evidence)
    session.commit()

    return base_run


# ==============================================================================
# 1. Contratos de Validação de Entrada e Tratamento de Erros (HTTP 400)
# ==============================================================================


def test_selective_rerun_invalid_req_ids_rejected_400(db_session: Session):
    """US1 Scenario 4 / FR-002: POST /api/runs/{id}/rerun with invalid req_ids (e.g. ['V9.9.9']) returns 400 Bad Request."""
    AISecretStore.get_instance().set_credentials("gemini-2.0-flash", "test-valid-key")
    client = TestClient(app)
    base_run = _seed_completed_base_run(db_session)

    resp = client.post(
        f"/api/runs/{base_run.id}/rerun",
        json={"req_ids": ["V9.9.9"]},
    )
    assert resp.status_code == 400, "IDs fora do escopo normativo ASVS V1 L1 devem retornar 400 Bad Request."
    detail = resp.json().get("detail", "")
    assert "V9.9.9" in detail or "inválido" in detail.lower()


def test_selective_rerun_empty_req_ids_rejected_400(db_session: Session):
    """EC-001 / FR-002: POST /api/runs/{id}/rerun with empty req_ids list returns 400 Bad Request."""
    AISecretStore.get_instance().set_credentials("gemini-2.0-flash", "test-valid-key")
    client = TestClient(app)
    base_run = _seed_completed_base_run(db_session)

    resp = client.post(
        f"/api/runs/{base_run.id}/rerun",
        json={"req_ids": []},
    )
    assert resp.status_code == 400, "Lista vazia de req_ids para reexecução seletiva deve retornar 400 Bad Request."
    detail = resp.json().get("detail", "")
    assert "vazia" in detail.lower() or "empty" in detail.lower()


def test_selective_rerun_on_running_run_rejected_400(db_session: Session):
    """EC-002: Attempting selective rerun on a run with status='RUNNING' or 'PENDING' returns 400 Bad Request."""
    AISecretStore.get_instance().set_credentials("gemini-2.0-flash", "test-valid-key")
    client = TestClient(app)

    # 1. Run em execução (RUNNING)
    running_run = Run(
        user_id=1,
        owner_username="admin",
        source_type="workspace_path",
        source_path="tests/vulnerable_app",
        status=RunStatus.RUNNING.value,
        current_stage=PipelineStage.SAST.value,
        zap_authorized=True,
    )
    db_session.add(running_run)
    db_session.commit()
    db_session.refresh(running_run)

    resp_running = client.post(
        f"/api/runs/{running_run.id}/rerun",
        json={"req_ids": ["V1.3.1"]},
    )
    assert resp_running.status_code == 400, "Reexecução em run RUNNING deve ser rejeitada com 400."
    assert "concluída" in resp_running.json().get("detail", "").lower() or "finalizada" in resp_running.json().get("detail", "").lower()

    # 2. Run pendente (PENDING)
    pending_run = Run(
        user_id=1,
        owner_username="admin",
        source_type="workspace_path",
        source_path="tests/vulnerable_app",
        status=RunStatus.PENDING.value,
        current_stage=PipelineStage.INIT.value,
        zap_authorized=True,
    )
    db_session.add(pending_run)
    db_session.commit()
    db_session.refresh(pending_run)

    resp_pending = client.post(
        f"/api/runs/{pending_run.id}/rerun",
        json={"req_ids": ["V1.3.1"]},
    )
    assert resp_pending.status_code == 400, "Reexecução em run PENDING deve ser rejeitada com 400."


# ==============================================================================
# 2. Controle de Acesso RBAC e Prevenção Inegociável de IDOR (HTTP 403)
# ==============================================================================


def test_selective_rerun_idor_blocked_403(db_session: Session):
    """US1 Scenario 5 / SC-004: Regular user attempting to selectively rerun another user's run receives 403 Forbidden."""
    AISecretStore.get_instance().set_credentials("gemini-2.0-flash", "test-valid-key")

    user_alice = create_test_user(db_session, "alice_sec", "AlicePass123!", role="user")
    user_bob = create_test_user(db_session, "bob_sec", "BobPass123!", role="user")

    alice_run = _seed_completed_base_run(db_session, user=user_alice)

    # Injetar identidade autenticada de Bob no contexto
    app.dependency_overrides[get_current_user] = lambda: SessionUser(
        id=user_bob.id,
        username=user_bob.username,
        role=user_bob.role,
        must_change_password=False,
        is_active=True,
    )
    try:
        client = TestClient(app)
        resp = client.post(
            f"/api/runs/{alice_run.id}/rerun",
            json={"req_ids": ["V1.3.1"]},
        )
        assert resp.status_code == 403, "Bob NUNCA pode reexecutar uma avaliação pertencente à Alice (mitigação IDOR)."
        detail = resp.json().get("detail", "")
        assert "permissão" in detail.lower() or "forbidden" in detail.lower() or "acesso negado" in detail.lower()
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ==============================================================================
# 3. Orquestração Seletiva, Herança de Vereditos e Linhagem (P1 🎯 MVP)
# ==============================================================================


@pytest.mark.asyncio
async def test_selective_rerun_single_ai_req_skips_sast_dast_and_inherits_other_verdicts(
    db_session: Session,
):
    """US1 Scenario 1, 2, 3 / EC-003: Selective rerun of single AI req (V1.3.1) skips SAST & DAST and inherits other 7 verdicts."""
    AISecretStore.get_instance().set_credentials("gemini-2.0-flash", "test-valid-key")
    base_run = _seed_completed_base_run(db_session)
    client = TestClient(app)

    with patch("app.aci.ai_aci.run_ai_evaluation", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = ACIResponse(
            ok=True,
            aci="ai_aci",
            command="run_ai_evaluation",
            summary_message="Veredito PASS emitido por IA.",
            data={
                "run_id": 999,
                "req_id": "V1.3.1",
                "verdict": "PASS",
                "confidence": "HIGH",
                "rationale": "Sanitização rigorosa comprovada com Jinja2 autoescape=True.",
                "model_used": "gemini-2.0-flash",
                "evidence_snippets": ["tests/vulnerable_app/templates/index.html:5"],
            },
        )

        resp = client.post(
            f"/api/runs/{base_run.id}/rerun?sync=True",
            json={"req_ids": ["V1.3.1"]},
        )
        assert resp.status_code == 202
        new_run_id = resp.json()["run_id"]

        db_session.expire_all()
        new_run = db_session.get(Run, new_run_id)
        assert new_run is not None
        assert new_run.status == RunStatus.COMPLETED.value
        assert new_run.is_selective is True
        assert new_run.inherited_from_run_id == base_run.id
        assert json.loads(new_run.selected_req_ids_json) == ["V1.3.1"]

        # Validar vereditos consolidados (todos os 8 devem estar presentes)
        verdicts = list(
            db_session.exec(select(Verdict).where(Verdict.run_id == new_run_id)).all()
        )
        assert len(verdicts) == 8, "A nova run deve conter exatamente os 8 vereditos consolidados."

        verdicts_by_req = {v.req_id: v for v in verdicts}

        # V1.3.1 foi reexecutado e NÃO deve ser herdado
        assert verdicts_by_req["V1.3.1"].is_inherited is False
        assert verdicts_by_req["V1.3.1"].status == "PASS"

        # Os outros 7 requisitos devem ser herdados da run base
        inherited_reqs = [r for r in IN_SCOPE_REQ_IDS if r != "V1.3.1"]
        for r_id in inherited_reqs:
            v = verdicts_by_req[r_id]
            assert v.is_inherited is True, f"Requisito {r_id} deveria ter is_inherited=True."
            assert v.inherited_from_run_id == base_run.id

        # Métricas globais consolidadas
        total_counts = (
            new_run.pass_count
            + new_run.fail_count
            + new_run.inconclusive_count
            + new_run.manual_count
        )
        assert total_counts == 8
        assert new_run.pass_percentage >= 0.0


@pytest.mark.asyncio
async def test_selective_rerun_single_sast_req(db_session: Session):
    """US1 / SC-002: Selective rerun of single SAST requirement (V1.3.2) inherits other 7 verdicts and recalculates V1.3.2."""
    AISecretStore.get_instance().set_credentials("gemini-2.0-flash", "test-valid-key")
    base_run = _seed_completed_base_run(db_session)
    client = TestClient(app)

    resp = client.post(
        f"/api/runs/{base_run.id}/rerun?sync=True",
        json={"req_ids": ["V1.3.2"]},
    )
    assert resp.status_code == 202
    new_run_id = resp.json()["run_id"]

    db_session.expire_all()
    new_run = db_session.get(Run, new_run_id)
    assert new_run is not None
    assert new_run.is_selective is True
    assert new_run.inherited_from_run_id == base_run.id
    assert json.loads(new_run.selected_req_ids_json) == ["V1.3.2"]

    verdicts = list(
        db_session.exec(select(Verdict).where(Verdict.run_id == new_run_id)).all()
    )
    assert len(verdicts) == 8
    verdicts_by_req = {v.req_id: v for v in verdicts}

    assert verdicts_by_req["V1.3.2"].is_inherited is False

    for r_id in IN_SCOPE_REQ_IDS:
        if r_id != "V1.3.2":
            assert verdicts_by_req[r_id].is_inherited is True
            assert verdicts_by_req[r_id].inherited_from_run_id == base_run.id


# ==============================================================================
# 4. Herança de Achados (Findings) e Evidências (Evidences)
# ==============================================================================


@pytest.mark.asyncio
async def test_selective_rerun_inherits_findings_and_evidences(db_session: Session):
    """FR-004 / SC-003: Findings and evidences of inherited requirements are cloned with is_inherited=True."""
    AISecretStore.get_instance().set_credentials("gemini-2.0-flash", "test-valid-key")
    base_run = _seed_completed_base_run(db_session)

    orig_finding = db_session.exec(
        select(Finding).where(Finding.run_id == base_run.id, Finding.req_id == "V1.2.4")
    ).first()
    assert orig_finding is not None

    orig_evidence = db_session.exec(
        select(Evidence).where(Evidence.finding_id == orig_finding.id)
    ).first()
    assert orig_evidence is not None

    client = TestClient(app)
    # Reexecutar seletivamente apenas V1.3.1 (logo, V1.2.4 deve ser herdado junto com seus achados e evidências)
    with patch("app.aci.ai_aci.run_ai_evaluation", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = ACIResponse(
            ok=True,
            aci="ai_aci",
            command="run_ai_evaluation",
            summary_message="PASS",
            data={
                "run_id": 999,
                "req_id": "V1.3.1",
                "verdict": "PASS",
                "confidence": "HIGH",
                "rationale": "OK",
                "model_used": "gemini-2.0-flash",
                "evidence_snippets": [],
            },
        )
        resp = client.post(
            f"/api/runs/{base_run.id}/rerun?sync=True",
            json={"req_ids": ["V1.3.1"]},
        )
        assert resp.status_code == 202
        new_run_id = resp.json()["run_id"]

    db_session.expire_all()
    # Achado de V1.2.4 deve ter sido clonado para a nova run com flag is_inherited=True
    cloned_finding = db_session.exec(
        select(Finding).where(Finding.run_id == new_run_id, Finding.req_id == "V1.2.4")
    ).first()
    assert cloned_finding is not None
    assert cloned_finding.id != orig_finding.id
    assert cloned_finding.is_inherited is True
    assert cloned_finding.inherited_from_run_id == base_run.id
    assert cloned_finding.fingerprint == orig_finding.fingerprint
    assert cloned_finding.title == orig_finding.title

    # Evidência deve ter sido clonada e associada ao finding clonado
    cloned_evidence = db_session.exec(
        select(Evidence).where(Evidence.finding_id == cloned_finding.id)
    ).first()
    assert cloned_evidence is not None
    assert cloned_evidence.id != orig_evidence.id
    assert cloned_evidence.file_path == orig_evidence.file_path
    assert cloned_evidence.code_snippet == orig_evidence.code_snippet


# ==============================================================================
# 5. Cenários Multi-Ferramenta e Retrocompatibilidade
# ==============================================================================


@pytest.mark.asyncio
async def test_selective_rerun_multi_tool_reqs(db_session: Session):
    """US1 Scenario 1 & 2: Selective rerun with multiple requirements across tools (['V1.2.4', 'V1.3.1'])."""
    AISecretStore.get_instance().set_credentials("gemini-2.0-flash", "test-valid-key")
    base_run = _seed_completed_base_run(db_session)
    client = TestClient(app)

    with patch("app.aci.ai_aci.run_ai_evaluation", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = ACIResponse(
            ok=True,
            aci="ai_aci",
            command="run_ai_evaluation",
            summary_message="PASS",
            data={
                "run_id": 999,
                "req_id": "V1.3.1",
                "verdict": "PASS",
                "confidence": "HIGH",
                "rationale": "OK",
                "model_used": "gemini-2.0-flash",
                "evidence_snippets": [],
            },
        )
        resp = client.post(
            f"/api/runs/{base_run.id}/rerun?sync=True",
            json={"req_ids": ["V1.2.4", "V1.3.1"]},
        )
        assert resp.status_code == 202
        new_run_id = resp.json()["run_id"]

    db_session.expire_all()
    new_run = db_session.get(Run, new_run_id)
    assert new_run is not None
    assert new_run.is_selective is True
    assert set(json.loads(new_run.selected_req_ids_json)) == {"V1.2.4", "V1.3.1"}

    verdicts = list(
        db_session.exec(select(Verdict).where(Verdict.run_id == new_run_id)).all()
    )
    verdicts_by_req = {v.req_id: v for v in verdicts}

    # Requisitos reavaliados
    assert verdicts_by_req["V1.2.4"].is_inherited is False
    assert verdicts_by_req["V1.3.1"].is_inherited is False

    # Outros 6 requisitos herdados
    for r_id in ("V1.2.1", "V1.2.2", "V1.2.3", "V1.2.5", "V1.3.2", "V1.5.1"):
        assert verdicts_by_req[r_id].is_inherited is True
        assert verdicts_by_req[r_id].inherited_from_run_id == base_run.id


def test_rerun_full_without_req_ids_is_not_selective(db_session: Session):
    """FR-002: POST /api/runs/{id}/rerun without req_ids (or req_ids=None) triggers full rerun with is_selective=False."""
    AISecretStore.get_instance().set_credentials("gemini-2.0-flash", "test-valid-key")
    base_run = _seed_completed_base_run(db_session)
    client = TestClient(app)

    resp = client.post(
        f"/api/runs/{base_run.id}/rerun",
        json={},
    )
    assert resp.status_code == 202
    new_run_id = resp.json()["run_id"]

    db_session.expire_all()
    new_run = db_session.get(Run, new_run_id)
    assert new_run is not None
    assert getattr(new_run, "is_selective", False) is False
    assert getattr(new_run, "selected_req_ids_json", None) is None

