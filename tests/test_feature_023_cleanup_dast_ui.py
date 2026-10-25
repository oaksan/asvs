"""Automated TDD Test Suite for Feature 023: Visual Cleanup of DAST Artifact Card.

Spec Reference: specs/023-cleanup-dast-ui-hints/spec.md
Plan Reference: specs/023-cleanup-dast-ui-hints/plan.md
Constitutional Principles: I (TDD), IV (DAST Guardrails), V (WCAG 2.2 AA / Fluent 2)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.ai_secrets import AISecretStore
from app.main import APP_UI_VERSION, app

client = TestClient(app)


def test_dast_card_does_not_contain_allowlist_text() -> None:
    """FR-001: The DAST card MUST NOT contain the redundant allowlist informative text."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert "Allowlist permitida:" not in html
    assert "Alvos localhost/127.0.0.1 são resolvidos automaticamente" not in html


def test_dast_card_does_not_contain_fixed_scan_mode_box() -> None:
    """FR-002: The DAST card MUST NOT contain the redundant fixed scan mode info box."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert "Modo de Varredura Fixo: Active Scan (Ataque Ativo + Spider)" not in html
    assert "Cobertura dinâmica integral dos requisitos" not in html


def test_dast_card_does_not_contain_dast_auth_hint() -> None:
    """FR-003: The DAST card MUST NOT contain the redundant legal note under the checkbox."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert "Termo mandatório de conformidade legal e segurança operacional" not in html
    assert 'id="dast-auth-hint"' not in html


def test_zap_authorized_has_no_dangling_aria_describedby() -> None:
    """FR-004 / NFR-001: The zap_authorized checkbox MUST NOT have a dangling aria-describedby pointing to removed hint."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert 'aria-describedby="dast-auth-hint"' not in html


def test_dast_card_preserves_functional_elements_and_badge() -> None:
    """FR-005 / NFR-002: The DAST card preserves required functional controls, badge, and hidden mode input."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # Header badge
    assert "OWASP ZAP • Active Scan Fixo" in html
    assert 'class="badge badge-PASS"' in html

    # Target URL input
    assert 'id="target-url"' in html
    assert 'name="target_url"' in html

    # Hidden scan mode input
    assert 'id="zap-mode"' in html
    assert 'value="active"' in html

    # DAST auth container & checkbox
    assert 'id="dast-auth-container"' in html
    assert 'id="zap-authorized"' in html
    assert 'name="zap_authorized"' in html
    assert "Declaro que possuo autorização explícita para executar testes dinâmicos" in html

    # Version check
    assert APP_UI_VERSION == "023"
    assert "v=023" in html
    assert "Versão 023" in html


def test_dast_functional_guardrail_blocks_without_consent(auth_admin_client: TestClient) -> None:
    """NFR-002: Submissions without zap_authorized=True remain blocked with HTTP 403."""
    AISecretStore.get_instance().set_credentials(
        api_key="test-key-023",
        model_name="gemini-2.0-flash",
        provider="gemini",
    )
    resp = auth_admin_client.post(
        "/api/runs",
        json={
            "source_type": "workspace_path",
            "workspace_subpath": "app",
            "target_url": "http://localhost:8000",
            "zap_authorized": False,
            "zap_mode": "active",
        },
    )
    assert resp.status_code == 403
    assert "dast" in resp.json().get("detail", "").lower()

