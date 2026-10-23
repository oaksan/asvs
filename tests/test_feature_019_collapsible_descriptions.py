"""Feature 019: descrição completa em bloco recolhível para V1.2.1 a V1.5.1."""

from pathlib import Path
from fastapi.testclient import TestClient

from app.database import load_req_tool_mapping
from app.main import app

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_IDS = ["V1.2.1", "V1.2.2", "V1.2.3", "V1.2.4", "V1.2.5", "V1.3.1", "V1.3.2", "V1.5.1"]


def test_app_js_creates_collapsible_description_block() -> None:
    """Valida que app.js encapsula a descrição completa em um bloco details com 'Descrição completa'."""
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "req-desc-details" in js
    assert "Descrição completa" in js
    assert "req-description-body" in js


def test_theme_css_has_collapsible_styles_and_print_rule() -> None:
    """Valida que theme.css estiliza o bloco recolhível e abre na impressão."""
    css = (ROOT / "static" / "theme.css").read_text(encoding="utf-8")
    assert ".req-desc-details" in css
    assert "@media print" in css


def test_ui_version_is_valid() -> None:
    """Valida que templates e index expõem Versão válida."""
    with TestClient(app) as client:
        html = client.get("/").text
    assert "Versão " in html
    assert "?v=" in html

