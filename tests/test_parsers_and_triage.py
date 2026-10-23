"""Unit & API Tests for SARIF/ZAP Parsers, Triage Correlation, AuditLog, and HTML Escaping (`T027`)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.aci.semgrep_aci import _truncate_code_snippet, parse_sarif_findings
from app.aci.zap_aci import _truncate_http_message
from app.agents.reporter_agent import build_full_report_dict, render_static_html_report
from app.agents.triage_agent import TriageAgent, TriageAgentInput
from app.main import app, get_session
from app.models import AuditLog, Finding, Run, Verdict


def test_truncate_snippet_caps_at_20_lines() -> None:
    """Snippets longer than 20 lines must be truncated with an explicit marker."""
    long_code = "\n".join(f"linha_{i} = {i}" for i in range(1, 35))
    truncated = _truncate_code_snippet(long_code)
    lines = truncated.splitlines()
    assert len(lines) == 21
    assert "linhas truncadas pela ACI" in lines[-1]


def test_parse_sarif_findings_maps_rules_to_req_id(tmp_path: Path) -> None:
    """SARIF 2.1.0 parser extracts findings, maps ruleId -> req_id, and generates fingerprints."""
    sample_file = tmp_path / "sample.py"
    sample_file.write_text(
        "\n".join(f"x_{i} = {i}" for i in range(1, 30)),
        encoding="utf-8",
    )

    sarif_doc = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "Semgrep"}},
                "results": [
                    {
                        "ruleId": "config.semgrep_rules.v1-2-4-python-sql-string-concat",
                        "level": "error",
                        "message": {"text": "SQL query construída por f-string."},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": str(sample_file)},
                                    "region": {
                                        "startLine": 5,
                                        "endLine": 6,
                                        "snippet": {"text": 'cursor.execute(f"SELECT * FROM t WHERE id={uid}")'},
                                    },
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }
    parsed = parse_sarif_findings(
        sarif_doc,
        allowed_rules={"v1-2-4-python-sql-string-concat"},
        req_id="V1.2.4",
        base_dir=tmp_path,
    )
    assert len(parsed) == 1
    item = parsed[0]
    assert item["req_id"] == "V1.2.4"
    assert item["rule_or_plugin_id"] == "v1-2-4-python-sql-string-concat"
    assert item["severity"] == "HIGH"
    assert item["file_path"] == "sample.py"
    assert item["line_start"] == 5
    assert len(item["fingerprint"]) == 24


def test_truncate_http_message_bounds_payload_size() -> None:
    """ZAP HTTP message truncator caps oversized HTTP bodies at 2,048 characters."""
    oversized = "A" * 3500
    truncated = _truncate_http_message(oversized)
    assert len(truncated) < 2200
    assert "[corpo HTTP truncado pela ACI]" in truncated


def test_triage_agent_deduplicates_and_correlates_sast_dast(session: Session) -> None:
    """TriageAgent removes duplicate fingerprints and boosts confidence to HIGH on SAST+DAST match."""
    run = Run(
        source_type="workspace_path",
        source_path="tests/vulnerable_app",
        status="RUNNING",
        current_stage="TRIAGE",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    run_id = int(run.id or 1)

    f1 = Finding(
        run_id=run_id,
        req_id="V1.2.4",
        tool="semgrep",
        rule_or_plugin_id="v1-2-4-python-sql-string-concat",
        title="SQLi SAST",
        severity="HIGH",
        confidence="MEDIUM",
        fingerprint="dup_fp_12345",
        primary_location="app.py:42",
    )
    f2 = Finding(
        run_id=run_id,
        req_id="V1.2.4",
        tool="semgrep",
        rule_or_plugin_id="v1-2-4-python-sql-string-concat",
        title="SQLi SAST duplicate",
        severity="HIGH",
        confidence="MEDIUM",
        fingerprint="dup_fp_12345",
        primary_location="app.py:42",
    )
    f3 = Finding(
        run_id=run_id,
        req_id="V1.2.4",
        tool="zap",
        rule_or_plugin_id="40018",
        title="SQLi DAST",
        severity="HIGH",
        confidence="MEDIUM",
        fingerprint="zap_fp_67890",
        primary_location="GET http://localhost:8081/users",
    )
    session.add_all([f1, f2, f3])
    session.commit()

    agent = TriageAgent()
    out = agent.run(session, TriageAgentInput(run_id=run_id))

    assert out.total_raw == 3
    assert out.deduplicated_count == 2
    assert "V1.2.4" in out.correlated_reqs
    assert out.active_findings_by_req["V1.2.4"] == 2

    remaining = list(session.exec(select(Finding).where(Finding.run_id == run_id)).all())
    assert len(remaining) == 2
    assert all(r.confidence == "HIGH" for r in remaining)


def test_patch_finding_triage_creates_audit_log_and_recalculates_verdict(
    session: Session,
) -> None:
    """PATCH /api/findings/{id}/triage records AuditLog and recalculates verdict respecting required_tools."""
    scope_summary = {
        "code_files_count": 3,
        "surfaces_by_req": {
            "V1.2.4": {
                "surface_count": 2,
                "examples": ["db.py:10"],
                "positive_indicators": ["Consultas SQL parametrizadas confirmadas"],
                "manual_review_needed": False,
                "manual_reason": None,
            },
            "V1.3.2": {
                "surface_count": 3,
                "examples": ["app.py:1"],
                "positive_indicators": ["Módulos verificados sem eval()/exec()"],
                "manual_review_needed": False,
                "manual_reason": None,
            },
        },
    }
    run = Run(
        source_type="workspace_path",
        source_path="tests/vulnerable_app",
        status="COMPLETED",
        current_stage="DONE",
        scope_summary_json=json.dumps(scope_summary),
        pass_percentage=0.0,
        pass_count=0,
        fail_count=2,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    run_id = int(run.id or 1)

    finding_zap_req = Finding(
        run_id=run_id,
        req_id="V1.2.4",
        tool="semgrep",
        rule_or_plugin_id="v1-2-4-python-sql-string-concat",
        title="F-string em consulta estática de teste",
        severity="HIGH",
        confidence="MEDIUM",
        fingerprint="fp_triage_test_001",
        primary_location="db.py:15",
    )
    verdict_zap_req = Verdict(
        run_id=run_id,
        req_id="V1.2.4",
        status="FAIL",
        confidence_level="HIGH",
        tools_used_json='["semgrep"]',
        rules_executed_json='["v1-2-4-python-sql-string-concat"]',
        coverage_declared="3 arquivo(s) analisado(s)",
        positive_evidence_json="[]",
        active_findings_count=1,
        rationale="Requisito V1.2.4 reprovado com 1 achado.",
        limitations="Apenas SAST.",
    )
    finding_sast_only_req = Finding(
        run_id=run_id,
        req_id="V1.3.2",
        tool="semgrep",
        rule_or_plugin_id="v1-3-2-python-eval-exec",
        title="Chamada de teste avaliada",
        severity="HIGH",
        confidence="MEDIUM",
        fingerprint="fp_triage_test_002",
        primary_location="app.py:20",
    )
    verdict_sast_only_req = Verdict(
        run_id=run_id,
        req_id="V1.3.2",
        status="FAIL",
        confidence_level="MEDIUM",
        tools_used_json='["semgrep"]',
        rules_executed_json='["v1-3-2-python-eval-exec"]',
        coverage_declared="3 arquivo(s) analisado(s)",
        positive_evidence_json="[]",
        active_findings_count=1,
        rationale="Requisito V1.3.2 reprovado com 1 achado.",
        limitations="Apenas SAST.",
    )
    session.add_all([finding_zap_req, verdict_zap_req, finding_sast_only_req, verdict_sast_only_req])
    session.commit()
    session.refresh(finding_zap_req)
    session.refresh(finding_sast_only_req)

    app.dependency_overrides[get_session] = lambda: session
    try:
        client = TestClient(app)
        # 1. V1.2.4 requires ["semgrep", "zap"] -> on a SAST-only run, marking FP transitions FAIL -> INCONCLUSIVE
        resp1 = client.patch(
            f"/api/findings/{finding_zap_req.id}/triage",
            json={
                "is_false_positive": True,
                "justification": "A string interpolada é constante interna fixa validada.",
                "actor": "auditor_sec",
            },
        )
        assert resp1.status_code == 200
        body1 = resp1.json()
        assert body1["is_false_positive"] is True
        assert body1["updated_verdict"]["status"] == "INCONCLUSIVE"
        assert body1["updated_verdict"]["active_findings_count"] == 0

        # 2. V1.3.2 requires ["semgrep"] -> on a SAST-only run, marking FP transitions FAIL -> PASS
        resp2 = client.patch(
            f"/api/findings/{finding_sast_only_req.id}/triage",
            json={
                "is_false_positive": True,
                "justification": "Falso positivo em comentário/teste estático.",
                "actor": "auditor_sec",
            },
        )
        assert resp2.status_code == 200
        body2 = resp2.json()
        assert body2["is_false_positive"] is True
        assert body2["updated_verdict"]["status"] == "PASS"
        assert body2["updated_verdict"]["active_findings_count"] == 0

        audits = list(
            session.exec(select(AuditLog).where(AuditLog.run_id == run_id)).all()
        )
        assert len(audits) == 2
        assert all(a.action == "MARK_FP" and a.actor == "admin" for a in audits)
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_static_html_report_contextual_escaping(session: Session) -> None:
    """Exported static HTML report must escape any untrusted `<script>` payload in findings."""
    run = Run(
        source_type="workspace_path",
        source_path="tests/vulnerable_app",
        status="COMPLETED",
        current_stage="DONE",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    run_id = int(run.id or 1)

    malicious_finding = Finding(
        run_id=run_id,
        req_id="V1.2.1",
        tool="semgrep",
        rule_or_plugin_id="v1-2-1-innerhtml-sink",
        title="<script>alert('xss_in_report')</script>",
        severity="HIGH",
        confidence="HIGH",
        fingerprint="xss_fp_999",
        primary_location="evil.js:1",
    )
    session.add(malicious_finding)
    session.commit()

    report_dict = build_full_report_dict(session, run_id)
    html_str = render_static_html_report(report_dict)
    assert "<script>alert('xss_in_report')</script>" not in html_str
    assert "&lt;script&gt;alert(&#x27;xss_in_report&#x27;)&lt;/script&gt;" in html_str

