"""Feature 016: descrições em português (pt-BR) de V1.2.1 a V1.5.1, preservando o texto normativo."""

import csv
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine, load_req_tool_mapping
from app.main import app
from app.models import Requirement

ROOT = Path(__file__).resolve().parent.parent
IDS = ["V1.2.1", "V1.2.2", "V1.2.3", "V1.2.4", "V1.2.5", "V1.3.1", "V1.3.2", "V1.5.1"]


def _csv_descriptions() -> dict[str, str]:
    path = ROOT / "docs" / "OWASP_Application_Security_Verification_Standard_5.0.0_en.csv"
    with open(path, encoding="utf-8", newline="") as fh:
        return {r["req_id"]: r["req_description"].strip() for r in csv.DictReader(fh)}


def test_mapping_has_description_pt_for_all_eight() -> None:
    reqs = load_req_tool_mapping()["requirements"]
    for rid in IDS:
        text = reqs[rid].get("description_pt", "").strip()
        assert len(text) > 40, rid
        assert text.startswith("Verificar"), rid


def test_in_scope_endpoint_exposes_pt_and_keeps_english_normative_text() -> None:
    csv_desc = _csv_descriptions()
    with TestClient(app) as client:
        items = client.get("/api/requirements/in-scope").json()["items"]
    assert sorted(i["req_id"] for i in items) == sorted(IDS)
    for item in items:
        assert item["description_pt"].strip()
        assert item["req_description"].strip() == csv_desc[item["req_id"]]


def test_database_req_description_unchanged_from_csv() -> None:
    csv_desc = _csv_descriptions()
    with TestClient(app):
        with Session(engine) as session:
            rows = session.exec(select(Requirement).where(Requirement.req_id.in_(IDS))).all()
    assert len(rows) == 8
    for r in rows:
        assert r.req_description.strip() == csv_desc[r.req_id]


def test_report_builder_includes_description_pt() -> None:
    src = (ROOT / "app" / "agents" / "reporter_agent.py").read_text(encoding="utf-8")
    assert '"description_pt"' in src


def test_app_js_uses_pt_primary_with_original_and_fallback() -> None:
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "description_pt" in js
    assert 'lang: "pt-BR"' in js
    assert "Texto original (ASVS 5.0, inglês)" in js
    assert "req_description" in js
    assert "Descrição normativa indisponível" in js
