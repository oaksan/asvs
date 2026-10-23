"""Feature 017: contrato dos endpoints de vereditos consumidos pela tela + sem 'undefined'."""

import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Run, RunStatus, Verdict
from tests.conftest import create_test_user, login_user

ROOT = Path(__file__).resolve().parent.parent
IDS = ["V1.2.1", "V1.2.2", "V1.2.3", "V1.2.4", "V1.2.5", "V1.3.1", "V1.3.2", "V1.5.1"]
FIELDS = ("section_id", "section_name", "req_description", "friendly_title", "description_pt")


def _csv_descriptions() -> dict[str, str]:
    path = ROOT / "docs" / "OWASP_Application_Security_Verification_Standard_5.0.0_en.csv"
    with open(path, encoding="utf-8", newline="") as fh:
        return {r["req_id"]: r["req_description"].strip() for r in csv.DictReader(fh)}


def _seed_run(session: Session, user_id: int | None) -> int:
    run = Run(
        source_type="workspace_path",
        source_path="tests/vulnerable_app",
        status=RunStatus.COMPLETED.value,
        user_id=user_id,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    for rid in IDS:
        session.add(
            Verdict(
                run_id=run.id,
                req_id=rid,
                status="PASS",
                coverage_declared="ok",
                rationale="ok",
                limitations="n/a",
            )
        )
    session.commit()
    return run.id


@pytest.fixture()
def owner_client(db_session: Session):
    user = create_test_user(db_session, "owner017")
    from app.core.auth import get_current_user
    from app.main import app

    app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(app)
    assert login_user(client, "owner017", "TestPassword123!").status_code == 200
    return client, user


def _check_items(items: list[dict]) -> None:
    csv_desc = _csv_descriptions()
    assert [i["req_id"] for i in items] == IDS
    for item in items:
        for f in FIELDS:
            assert str(item[f]).strip(), (item["req_id"], f)
        assert item["section_id"] == item["req_id"].rsplit(".", 1)[0]
        assert item["req_description"].strip() == csv_desc[item["req_id"]]
        assert item["description_pt"].startswith("Verificar")


def test_run_details_verdicts_contract(owner_client, db_session: Session) -> None:
    client, user = owner_client
    run_id = _seed_run(db_session, user.id)
    resp = client.get(f"/api/runs/{run_id}")
    assert resp.status_code == 200
    _check_items(resp.json()["verdicts"])


def test_run_verdicts_endpoint_contract(owner_client, db_session: Session) -> None:
    client, user = owner_client
    run_id = _seed_run(db_session, user.id)
    resp = client.get(f"/api/runs/{run_id}/verdicts")
    assert resp.status_code == 200
    _check_items(resp.json())


def test_rbac_preserved_for_other_user(owner_client, db_session: Session) -> None:
    client, user = owner_client
    other = create_test_user(db_session, "other017")
    run_id = _seed_run(db_session, other.id)
    resp = client.get(f"/api/runs/{run_id}/verdicts")
    assert resp.status_code in (403, 404)


def test_app_js_never_concatenates_unsafe_fields() -> None:
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "function safeText" in js
    assert "function deriveSectionId" in js
    assert 'v.section_id + " — " + v.section_name' not in js


def test_footer_exposes_version() -> None:
    from app.main import app

    with TestClient(app) as client:
        html = client.get("/").text
    assert "Versão " in html
