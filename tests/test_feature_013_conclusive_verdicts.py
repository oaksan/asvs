"""TDD Test Suite for Feature 013: Eliminate INCONCLUSIVE and MANUAL_REQUIRED Verdicts in Full Runs.

Tests:
1. `_collect_code_context_for_v1_3_1` reads past line 60 (capturing lines 120-124 of `app/main.py` with `select_autoescape`)
   and inspects `.ts` / `.js` files while skipping `node_modules`/`dist`.
2. `scan_workspace_surface` detects JS/TS surfaces for `V1.2.5`, `V1.3.1`, and `V1.5.1` and records positive indicators
   of verified non-exposure when `code_files_count > 0` and no unsafe OS command or XXE sink exists, while preserving
   `INCONCLUSIVE` (`surface_count == 0`, `positive_indicators == []`) when `code_files_count == 0`.
3. New multi-language Semgrep rules (`v1-2-5-js-child-process-exec`, `v1-3-1-js-angular-unsanitized-html`,
   `v1-5-1-js-xxe-libxml-noent`) are registered in `config/req_tool_mapping.yaml` and defined in `config/semgrep_rules/`.
4. `app/main.py` includes `X-Content-Type-Options: nosniff` and `Content-Security-Policy` headers on HTTP responses.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from sqlmodel import Session, select

from app.aci.ai_aci import _collect_code_context_for_v1_3_1
from app.aci.semgrep_aci import run_rules
from app.aci.workspace_aci import scan_workspace_surface
from app.database import PROJECT_ROOT, engine, init_db, load_req_tool_mapping
from app.main import app
from app.models import Evidence, Finding


def test_v1_3_1_context_collector_reads_beyond_line_60_in_app_main():
    """FR-001: `_collect_code_context_for_v1_3_1` must capture `select_autoescape` at lines 120-124 of `app/main.py`."""
    app_dir = (PROJECT_ROOT / "app").resolve()
    context_str, evidence_files = _collect_code_context_for_v1_3_1(app_dir)

    assert "main.py" in evidence_files
    assert "select_autoescape" in context_str
    assert "autoescape=jinja2.select_autoescape" in context_str


def test_v1_3_1_context_collector_supports_typescript_and_skips_node_modules(tmp_path: Path):
    """FR-001: `_collect_code_context_for_v1_3_1` must inspect `.ts` and `.js` files and ignore `node_modules`."""
    src_dir = tmp_path / "frontend" / "src"
    src_dir.mkdir(parents=True)
    ts_file = src_dir / "track-result.component.ts"
    # Place the relevant line after line 70 to ensure no 60-line truncation occurs on TS files either
    padding = "\n".join([f"// comment line {i}" for i in range(1, 75)])
    ts_file.write_text(
        f"{padding}\n"
        "export class TrackResultComponent {\n"
        "  render(input: string) {\n"
        "    return this.sanitizer.bypassSecurityTrustHtml(input);\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    nm_dir = tmp_path / "node_modules" / "some-pkg"
    nm_dir.mkdir(parents=True)
    (nm_dir / "index.js").write_text("elem.innerHTML = 'ignored';\n", encoding="utf-8")

    context_str, evidence_files = _collect_code_context_for_v1_3_1(tmp_path)
    assert any("track-result.component.ts" in f for f in evidence_files)
    assert "bypassSecurityTrustHtml" in context_str
    assert "some-pkg" not in context_str


def test_scan_workspace_surface_js_ts_and_non_exposure_positive_indicators(tmp_path: Path):
    """FR-004: `scan_workspace_surface` provides verified non-exposure indicators for V1.2.5 and V1.5.1 when code_files_count > 0."""
    ts_app = tmp_path / "clean_ts_app"
    ts_app.mkdir(parents=True)
    (ts_app / "server.ts").write_text(
        "import express from 'express';\n"
        "const app = express();\n"
        "app.get('/api/items', (req, res) => res.json({ items: [] }));\n",
        encoding="utf-8",
    )

    resp = scan_workspace_surface(None, run_id=0, source_path="clean_ts_app", base_root=tmp_path)
    assert resp.ok is True
    assert resp.data is not None
    assert resp.data["code_files_count"] == 1
    surfaces = resp.data["surfaces_by_req"]

    # V1.2.5 and V1.5.1 must have positive indicators when code files were scanned and no unsafe OS/XML calls exist
    assert len(surfaces["V1.2.5"]["positive_indicators"]) >= 1
    assert len(surfaces["V1.5.1"]["positive_indicators"]) >= 1


def test_scan_workspace_surface_empty_dir_has_zero_positive_indicators(tmp_path: Path):
    """SC-003 (Principle II): An empty directory (`code_files_count == 0`) must have 0 positive indicators."""
    empty_dir = tmp_path / "empty_project"
    empty_dir.mkdir(parents=True)
    (empty_dir / "README.md").write_text("# Empty project without code\n", encoding="utf-8")

    resp = scan_workspace_surface(None, run_id=0, source_path="empty_project", base_root=tmp_path)
    assert resp.ok is True
    assert resp.data is not None
    assert resp.data["code_files_count"] == 0
    surfaces = resp.data["surfaces_by_req"]

    for req_id in ("V1.2.5", "V1.3.1", "V1.5.1"):
        assert surfaces[req_id]["surface_count"] == 0
        assert surfaces[req_id]["positive_indicators"] == []


def test_new_js_ts_semgrep_rules_registered_and_detect_vulnerabilities(tmp_path: Path):
    """FR-003: New Semgrep rules for V1.2.5, V1.3.1, and V1.5.1 are mapped and detect vulnerable JS/TS patterns."""
    mapping = load_req_tool_mapping()
    reqs = mapping["requirements"]

    assert "v1-2-5-js-child-process-exec" in reqs["V1.2.5"]["semgrep_rules"]
    assert "v1-3-1-js-angular-unsanitized-html" in reqs["V1.3.1"]["semgrep_rules"]
    assert "v1-5-1-js-xxe-libxml-noent" in reqs["V1.5.1"]["semgrep_rules"]

    vuln_js_dir = tmp_path / "vuln_juice_sample"
    vuln_js_dir.mkdir(parents=True)
    (vuln_js_dir / "sample.ts").write_text(
        "import * as libxml from 'libxmljs';\n"
        "import { exec } from 'child_process';\n"
        "export function handleXml(xmlString: string, sanitizer: any, cmd: string) {\n"
        "  const doc = libxml.parseXml(xmlString, { noblanks: true, noent: true, nocdata: true });\n"
        "  const trusted = sanitizer.bypassSecurityTrustHtml(xmlString);\n"
        "  exec('sh -c ' + cmd);\n"
        "  return { doc, trusted };\n"
        "}\n",
        encoding="utf-8",
    )

    init_db(engine)
    with Session(engine) as session:
        try:
            for req_id in ("V1.2.5", "V1.3.1", "V1.5.1"):
                sast_resp = run_rules(
                    session,
                    run_id=99999,
                    req_id=req_id,
                    source_path="vuln_juice_sample",
                    base_root=tmp_path,
                )
                assert sast_resp.ok is True
                assert sast_resp.data is not None
                assert sast_resp.data["findings_count"] >= 1, f"Expected finding for {req_id}"
        finally:
            old_findings = list(session.exec(select(Finding).where(Finding.run_id == 99999)).all())
            for f in old_findings:
                evs = list(session.exec(select(Evidence).where(Evidence.finding_id == f.id)).all())
                for ev in evs:
                    session.delete(ev)
                session.delete(f)
            session.commit()


def test_security_headers_present_on_app_responses():
    """FR-005: `app/main.py` sets `X-Content-Type-Options: nosniff` and `Content-Security-Policy`."""
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    csp = resp.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
