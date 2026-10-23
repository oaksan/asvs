"""Feature 018: descrição exclusiva em português para V1.2.1 a V1.5.1 sem texto original em inglês residual."""

from pathlib import Path
from fastapi.testclient import TestClient

from app.database import load_req_tool_mapping
from app.main import app

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_IDS = ["V1.2.1", "V1.2.2", "V1.2.3", "V1.2.4", "V1.2.5", "V1.3.1", "V1.3.2", "V1.5.1"]


def test_app_js_removes_original_english_text_block() -> None:
    """Valida que o bloco 'Texto original (ASVS 5.0, inglês)' foi removido de app.js."""
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "Texto original (ASVS 5.0, inglês)" not in js
    assert "req-original" not in js


def test_all_in_scope_requirements_have_portuguese_descriptions() -> None:
    """Valida que os 8 requisitos em escopo possuem descrição em português completa."""
    mapping = load_req_tool_mapping()["requirements"]
    for rid in EXPECTED_IDS:
        desc_pt = mapping[rid].get("description_pt", "").strip()
        assert desc_pt, f"Requisito {rid} deve ter description_pt preenchido"
        assert desc_pt.startswith("Verificar se"), f"Requisito {rid} deve começar com 'Verificar se'"


def test_ui_version_is_018() -> None:
    """Valida que templates e index expõem Versão 018."""
    with TestClient(app) as client:
        html = client.get("/").text
    assert "Versão 018" in html
    assert "?v=018" in html

