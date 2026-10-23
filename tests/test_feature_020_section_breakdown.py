"""Feature 020: preenchimento correto de Resultados por Categoria e inclusão de section_breakdown em GET /api/runs/{id}."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Run, RunStatus, Verdict
from app.main import app
from tests.conftest import create_test_user, login_user

ROOT = Path(__file__).resolve().parent.parent

# 5 em V1.2, 2 em V1.3, 1 em V1.5
REQ_STATUSES = {
    "V1.2.1": "PASS",
    "V1.2.2": "PASS",
    "V1.2.3": "PASS",
    "V1.2.4": "FAIL",
    "V1.2.5": "PASS",
    "V1.3.1": "PASS",
    "V1.3.2": "PASS",
    "V1.5.1": "PASS",
}


def _seed_run_with_verdicts(session: Session, user_id: int | None) -> int:
    run = Run(
        source_type="workspace_path",
        source_path="tests/vulnerable_app",
        status=RunStatus.COMPLETED.value,
        user_id=user_id,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    for rid, st in REQ_STATUSES.items():
        session.add(
            Verdict(
                run_id=run.id,
                req_id=rid,
                status=st,
                coverage_declared="ok",
                rationale="ok",
                limitations="n/a",
            )
        )
    session.commit()
    return run.id


@pytest.fixture()
def authenticated_client(db_session: Session):
    user = create_test_user(db_session, "user020")
    from app.core.auth import get_current_user
    app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(app)
    assert login_user(client, "user020", "TestPassword123!").status_code == 200
    return client, user


def test_get_run_details_includes_section_breakdown(authenticated_client, db_session: Session) -> None:
    """Valida que GET /api/runs/{id} inclui a chave 'section_breakdown' com contagens precisas."""
    client, user = authenticated_client
    run_id = _seed_run_with_verdicts(db_session, user.id)

    resp = client.get(f"/api/runs/{run_id}")
    assert resp.status_code == 200
    data = resp.json()

    assert "section_breakdown" in data, "Chave 'section_breakdown' deve estar presente no retorno de GET /api/runs/{id}"
    sb = data["section_breakdown"]
    assert "V1.2" in sb
    assert "V1.3" in sb
    assert "V1.5" in sb

    # V1.2 tem 4 PASS e 1 FAIL no seed
    assert sb["V1.2"]["PASS"] == 4
    assert sb["V1.2"]["FAIL"] == 1
    assert sb["V1.2"]["total"] == 5

    # V1.3 tem 2 PASS
    assert sb["V1.3"]["PASS"] == 2
    assert sb["V1.3"]["FAIL"] == 0
    assert sb["V1.3"]["total"] == 2

    # V1.5 tem 1 PASS
    assert sb["V1.5"]["PASS"] == 1
    assert sb["V1.5"]["FAIL"] == 0
    assert sb["V1.5"]["total"] == 1


def test_app_js_has_defensive_section_breakdown_fallback() -> None:
    """Valida que app.js possui computação de fallback para section_breakdown a partir de verdicts."""
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "secBreakdown" in js
    assert "deriveSectionId" in js
