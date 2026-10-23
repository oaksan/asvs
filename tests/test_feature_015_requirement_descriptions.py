"""Feature 015: descrição e título amigável de cada requisito em 'Resultado por Verificação'."""

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.database import IN_SCOPE_REQ_IDS, load_req_tool_mapping
from app.main import app

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_IDS = ["V1.2.1", "V1.2.2", "V1.2.3", "V1.2.4", "V1.2.5", "V1.3.1", "V1.3.2", "V1.5.1"]


def test_mapping_has_friendly_title_for_all_in_scope() -> None:
    reqs = load_req_tool_mapping()["requirements"]
    for rid in EXPECTED_IDS:
        assert reqs[rid].get("friendly_title", "").strip(), rid
    assert sorted(IN_SCOPE_REQ_IDS) == sorted(EXPECTED_IDS)


def test_in_scope_endpoint_returns_description_and_friendly_title() -> None:
    with TestClient(app) as client:
        data = client.get("/api/requirements/in-scope").json()
    assert data["total"] == 8
    ids = [i["req_id"] for i in data["items"]]
    assert sorted(ids) == sorted(EXPECTED_IDS)
    for item in data["items"]:
        assert item["req_description"].strip()
        assert item["friendly_title"].strip()


def test_html_table_has_four_columns_without_separate_description_column() -> None:
    with TestClient(app) as client:
        html = client.get("/").text
    assert "O que foi verificado" not in html
    start = html.index('id="verdicts-table"')
    thead = html[start : html.index("</thead>", start)]
    assert len(re.findall(r"<th[ >]", thead)) == 4
    assert 'colspan="4"' in html[html.index('id="verdicts-tbody"') :][:400]


def test_app_js_renders_title_description_with_fallback() -> None:
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "friendly_title" in js
    assert "req-description" in js
    assert 'lang: "pt-BR"' in js
    assert "/api/requirements/in-scope" in js
    assert "Descrição normativa indisponível" in js
