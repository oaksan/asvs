"""UI Presentation tests for 005-production-grade-ui-redesign.

Validates that the rendered HTML is clean of legacy ASVS 4.0 columns and internal debugging
jargons, while strictly preserving security guardrails (DAST authorization checkbox and AI Gate).
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ui_removes_legacy_asvs_4_0_references() -> None:
    """Validate that GET / does not contain the legacy ASVS 4.0 column or migration badges."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # The legacy 4.0 equivalence column must NOT exist in the catalog table header
    assert "<th>Equivalência ASVS 4.0</th>" not in html
    assert "status de equivalência com o guia de testes ASVS 4.0" not in html


def test_ui_cleans_debugging_jargons_and_array_dumps() -> None:
    """Validate that raw array dumps and agent class pipeline strings are removed from UI."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # Raw pipeline class sequence should not be dumped in the main description
    assert "Scoper → SAST Semgrep → DAST OWASP ZAP → Triage → Verdict → Reporter" not in html


def test_ui_preserves_mandatory_security_guardrails() -> None:
    """Validate that mandatory DAST authorization and AI Gate UI elements are intact."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # DAST universal consent checkbox must remain present
    assert 'id="zap-authorized"' in html

    # AI configuration inputs must remain present
    assert 'id="ai-model-name"' in html
    assert 'id="ai-api-key"' in html
    assert 'type="password"' in html


def test_ui_separates_sast_and_dast_artifact_cards() -> None:
    """Feature 012 (US1/FR-002): Verify SAST and DAST artifacts are presented in separate dedicated cards."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert 'id="sast-artifact-card"' in html
    assert 'id="dast-artifact-card"' in html
    assert "artifact-split-grid" in html
    assert 'id="source-type"' in html
    assert 'id="workspace-path-group"' in html
    assert 'id="zip-upload-group"' in html
    assert 'id="target-url"' in html


def test_ui_enforces_hidden_css_rule_and_exclusive_sast_source_toggle() -> None:
    """Feature 012 (US1/FR-001): Verify [hidden] CSS rule prevents .form-field flex override and JS toggles exclusively."""
    css_resp = client.get("/static/theme.css")
    assert css_resp.status_code == 200
    css_text = css_resp.text
    assert "[hidden]" in css_text
    assert "display: none !important" in css_text

    js_resp = client.get("/static/app.js")
    assert js_resp.status_code == 200
    js_text = js_resp.text
    assert "syncSastSourceFields" in js_text


def test_ui_and_api_default_zap_mode_is_always_active_scan() -> None:
    """Feature 012 (US2/FR-003): Verify scan mode is always Active Scan ('active') by default in UI and schema."""
    from app.models import CreateRunRequest

    req = CreateRunRequest()
    assert req.zap_mode == "active"

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert 'id="zap-mode"' in html
    assert 'value="active"' in html


def test_ui_includes_automatic_zap_online_polling_after_startup() -> None:
    """Feature 012 (US3/FR-004): Verify automatic ZAP connectivity validation runs a few seconds after startup."""
    js_resp = client.get("/static/app.js")
    assert js_resp.status_code == 200
    js_text = js_resp.text
    assert "scheduleZapAutoCheck" in js_text




# ---------------------------------------------------------------------------
# Feature 014 — UX simplificada e foco em compliance
# ---------------------------------------------------------------------------


def test_ui_has_no_catalog_tab_or_catalog_jargon() -> None:
    """Feature 014 (US1/FR-001/FR-002): catalog tab and '8 / 345' jargon removed from the rendered UI."""
    html = client.get("/").text
    for forbidden in (
        "tab-catalog",
        "panel-catalog",
        "in-scope-catalog-tbody",
        "full-catalog-tbody",
        "8 / 345",
        "345 Requisitos",
        "8 Req)",
        "8 Requisitos",
    ):
        assert forbidden not in html, forbidden


def test_ui_navigation_tabs_renumbered_without_gaps() -> None:
    """Feature 014 (US1): remaining tabs are numbered 1..4 without gaps."""
    html = client.get("/").text
    assert "1. Nova Avaliação" in html
    assert "2. Resultados" in html
    assert "3. Histórico" in html
    assert "4. Configuração de IA" in html


def test_app_js_has_no_catalog_loaders_and_keeps_requirements_api() -> None:
    """Feature 014 (FR-001/FR-008): JS catalog loaders removed; backend API preserved."""
    js = client.get("/static/app.js").text
    for name in ("loadFullCatalog", "loadInScopeCatalog", "initCatalogControls"):
        assert name not in js, name
    resp = client.get("/api/requirements/in-scope")
    assert resp.status_code == 200
    assert resp.json()["total"] == 8


def test_verdicts_table_renders_requirement_description_column() -> None:
    """Feature 014 (US2/FR-003) / 015: description shown under each req id + fallback."""
    html = client.get("/").text
    js = client.get("/static/app.js").text
    assert "O que foi verificado" not in html  # Feature 015: merged into first column
    assert "req-description" in js
    assert "req_description" in js
    assert "Descrição normativa indisponível" in js


def test_ui_includes_compliance_hero_with_progressbar() -> None:
    """Feature 014 (US3/FR-004): compliance hero card with accessible progressbar."""
    html = client.get("/").text
    js = client.get("/static/app.js").text
    assert 'id="compliance-hero"' in html
    assert 'role="progressbar"' in html
    assert "buildComplianceSummary" in js


def test_ui_friendly_verdict_labels_do_not_change_exported_codes() -> None:
    """Feature 014 (US4/FR-005/FR-006): friendly labels only in presentation layer; tech details collapsible."""
    js = client.get("/static/app.js").text
    css = client.get("/static/theme.css").text
    html = client.get("/").text
    assert "VERDICT_LABELS_PT" in js
    assert "Revisão manual" in js
    assert "tech-details" in css
    from app.main import APP_UI_VERSION

    assert f"?v={APP_UI_VERSION}" in html


# ---------------------------------------------------------------------------
