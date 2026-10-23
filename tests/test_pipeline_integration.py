"""End-to-End Pipeline Integration & Self-Assessment Tests (`T018`, `T038`)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
import httpx
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.agents.orchestrator import OrchestratorAgent
from app.core.ai_secrets import AISecretStore
from app.main import app, get_orchestrator, get_session


def _make_client(db_engine: Engine, session: Session) -> TestClient:
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_orchestrator] = lambda: OrchestratorAgent(
        db_engine=db_engine
    )
    return TestClient(app)


def test_catalog_endpoints_return_8_in_scope_and_345_total(
    db_engine: Engine, session: Session
) -> None:
    """Verify catalog endpoints return 8 in-scope V1 L1 requirements and 345 total (V1-V17)."""
    client = _make_client(db_engine, session)
    try:
        resp_scope = client.get("/api/requirements/in-scope")
        assert resp_scope.status_code == 200
        data_scope = resp_scope.json()
        assert data_scope["total"] == 8
        req_ids = [item["req_id"] for item in data_scope["items"]]
        assert req_ids == [
            "V1.2.1",
            "V1.2.2",
            "V1.2.3",
            "V1.2.4",
            "V1.2.5",
            "V1.3.1",
            "V1.3.2",
            "V1.5.1",
        ]

        resp_all = client.get("/api/requirements?page=1&page_size=350")
        assert resp_all.status_code == 200
        data_all = resp_all.json()
        assert data_all["total"] == 345

        resp_v17 = client.get("/api/requirements?chapter_id=V17")
        assert resp_v17.status_code == 200
        v17_data = resp_v17.json()
        assert v17_data["total"] > 0
        assert all(item["chapter_name"] == "WebRTC" for item in v17_data["items"])
    finally:
        app.dependency_overrides.clear()


def test_create_run_enforces_security_guardrails(
    db_engine: Engine, session: Session
) -> None:
    """POST /api/runs rejects unauthorized DAST, non-allowlisted URLs, and path traversal."""
    store = AISecretStore.get_instance()
    store.set_credentials("gemini-2.0-flash", "test-key-guardrails")
    client = _make_client(db_engine, session)
    try:
        # 1. Missing zap_authorized checkbox when target_url is provided -> 403
        r1 = client.post(
            "/api/runs",
            json={
                "source_type": "workspace_path",
                "workspace_subpath": "tests/vulnerable_app",
                "target_url": "http://localhost:8081",
                "zap_authorized": False,
                "zap_mode": "baseline",
            },
        )
        assert r1.status_code == 403
        assert "autorização" in r1.json()["detail"].lower()

        # 2. Target URL outside allowlist -> 403
        r2 = client.post(
            "/api/runs",
            json={
                "source_type": "workspace_path",
                "workspace_subpath": "tests/vulnerable_app",
                "target_url": "https://untrusted-external-target.org",
                "zap_authorized": True,
                "zap_mode": "baseline",
            },
        )
        assert r2.status_code == 403
        assert "allowlist" in r2.json()["detail"].lower()

        # 3. Path traversal outside workspace -> 400
        r3 = client.post(
            "/api/runs",
            json={
                "source_type": "workspace_path",
                "workspace_subpath": "../../etc/passwd",
                "target_url": None,
                "zap_authorized": True,
                "zap_mode": "baseline",
            },
        )
        assert r3.status_code == 400
        assert "fora do workspace" in r3.json()["detail"].lower()
    finally:
        store.reset_instance()
        app.dependency_overrides.clear()


def test_full_pipeline_detects_fails_on_vulnerable_app_and_passes_self_assessment(
    db_engine: Engine, session: Session
) -> None:
    """Run full pipeline on `tests/vulnerable_app` (expect FAILs) and on `app` (expect 0 FAILs)."""
    store = AISecretStore.get_instance()
    store.set_credentials("gemini-2.0-flash", "test-key-full-pipeline")
    client = _make_client(db_engine, session)
    try:
        # ----------------------------------------------------------------------
        # 1. Assess `tests/vulnerable_app` (Deliberately Vulnerable Target Fixture)
        # ----------------------------------------------------------------------
        resp_vuln = client.post(
            "/api/runs?sync=true",
            json={
                "source_type": "workspace_path",
                "workspace_subpath": "tests/vulnerable_app",
                "target_url": None,
                "zap_authorized": True,
                "zap_mode": "baseline",
            },
        )
        assert resp_vuln.status_code == 202
        vuln_run_id = resp_vuln.json()["run_id"]
        assert resp_vuln.json()["status"] == "COMPLETED"

        detail_vuln = client.get(f"/api/runs/{vuln_run_id}").json()
        assert detail_vuln["metrics"]["total_in_scope"] == 8
        assert detail_vuln["metrics"]["fail_count"] == 8
        assert detail_vuln["metrics"]["pass_count"] == 0
        assert detail_vuln["metrics"]["pass_percentage"] == 0.0

        verdicts_by_req = {v["req_id"]: v for v in detail_vuln["verdicts"]}
        for req_id in (
            "V1.2.1",
            "V1.2.2",
            "V1.2.3",
            "V1.2.4",
            "V1.2.5",
            "V1.3.1",
            "V1.3.2",
            "V1.5.1",
        ):
            assert verdicts_by_req[req_id]["status"] == "FAIL", (
                f"Expected FAIL for {req_id} on vulnerable_app"
            )
            assert verdicts_by_req[req_id]["active_findings_count"] >= 1

        # Verify navigable evidence endpoint works for findings
        first_finding_id = detail_vuln["findings"][0]["id"]
        ev_resp = client.get(f"/api/findings/{first_finding_id}/evidence")
        assert ev_resp.status_code == 200
        ev_data = ev_resp.json()
        assert len(ev_data["evidences"]) >= 1
        assert ev_data["evidences"][0]["code_snippet"]

        # ----------------------------------------------------------------------
        # 2. Self-Assessment on `app` (SAST-only mode: Constitution Principles II & IV)
        #    - 0 FAIL across all 8 V1 L1 requirements
        #    - V1.3.2 (tools: ["semgrep"]) -> PASS (12.5%)
        #    - V1.3.1 (rich HTML/WYSIWYG without surface in app/) -> MANUAL_REQUIRED
        #    - V1.2.1, V1.2.2, V1.2.3, V1.2.4, V1.2.5, V1.5.1 (tools: ["semgrep", "zap"])
        #      -> INCONCLUSIVE because OWASP ZAP was skipped in SAST-only mode
        # ----------------------------------------------------------------------
        resp_self = client.post(
            "/api/runs?sync=true",
            json={
                "source_type": "workspace_path",
                "workspace_subpath": "app",
                "target_url": None,
                "zap_authorized": True,
                "zap_mode": "baseline",
            },
        )
        assert resp_self.status_code == 202
        self_run_id = resp_self.json()["run_id"]
        assert resp_self.json()["status"] == "COMPLETED"

        detail_self = client.get(f"/api/runs/{self_run_id}").json()
        assert detail_self["metrics"]["fail_count"] == 0, (
            f"Self-assessment of app/ produced unexpected findings: {detail_self['findings']}"
        )
        assert detail_self["metrics"]["pass_count"] == 1
        assert detail_self["metrics"]["inconclusive_count"] == 6
        assert detail_self["metrics"]["manual_count"] == 1
        assert detail_self["metrics"]["pass_percentage"] == 12.5

        self_verdicts_by_req = {v["req_id"]: v for v in detail_self["verdicts"]}
        assert self_verdicts_by_req["V1.3.2"]["status"] == "PASS"
        assert self_verdicts_by_req["V1.3.1"]["status"] in {"MANUAL_REQUIRED", "INCONCLUSIVE"}
        for zap_req in ("V1.2.1", "V1.2.2", "V1.2.3", "V1.2.4", "V1.2.5", "V1.5.1"):
            assert self_verdicts_by_req[zap_req]["status"] == "INCONCLUSIVE", (
                f"Expected INCONCLUSIVE for {zap_req} on SAST-only run, got {self_verdicts_by_req[zap_req]['status']}"
            )
            assert "OWASP ZAP" in self_verdicts_by_req[zap_req]["rationale"]

        # ----------------------------------------------------------------------
        # 3. Compare `vulnerable_app` run vs `app` self-assessment run
        # ----------------------------------------------------------------------
        cmp_resp = client.get(
            f"/api/runs/compare?base_run_id={vuln_run_id}&target_run_id={self_run_id}"
        )
        assert cmp_resp.status_code == 200
        cmp_data = cmp_resp.json()
        assert cmp_data["deltas"]["pass_percentage"] == 12.5
        assert cmp_data["deltas"]["fail_count"] == -8
        assert len(cmp_data["requirement_transitions"]) == 8

        # ----------------------------------------------------------------------
        # 4. Export Reports (JSON and static HTML)
        # ----------------------------------------------------------------------
        exp_json = client.get(f"/api/runs/{self_run_id}/export?format=json")
        assert exp_json.status_code == 200
        assert exp_json.json()["run"]["id"] == self_run_id

        exp_html = client.get(f"/api/runs/{self_run_id}/export?format=html")
        assert exp_html.status_code == 200
        assert "<!DOCTYPE html>" in exp_html.text
        assert "OWASP ASVS 5.0" in exp_html.text
    finally:
        store.reset_instance()
        app.dependency_overrides.clear()


def test_zap_status_endpoint_and_dast_baseline_and_active_verdict_progression(
    db_engine: Engine, session: Session
) -> None:
    """Validate GET /api/zap/status (T010) and full DAST pipeline verdicts: 50.0% PASS in baseline and 87.5% PASS in active mode (T006)."""
    import httpx

    def mock_zap_handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/JSON/core/view/version/"):
            return httpx.Response(200, json={"version": "2.15.0"})
        if path.endswith("/JSON/core/action/accessUrl/"):
            return httpx.Response(200, json={"Result": "OK"})
        if path.endswith("/JSON/spider/action/scan/"):
            return httpx.Response(200, json={"scan": "1"})
        if path.endswith("/JSON/spider/view/status/"):
            return httpx.Response(200, json={"status": "100"})
        if path.endswith("/JSON/spider/view/results/"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        "http://localhost:8000/",
                        "http://localhost:8000/api/requirements/in-scope",
                    ]
                },
            )
        if path.endswith("/JSON/pscan/view/recordsToScan/"):
            return httpx.Response(200, json={"recordsToScan": "0"})
        if path.endswith("/JSON/ascan/action/scan/"):
            return httpx.Response(200, json={"scan": "2"})
        if path.endswith("/JSON/ascan/view/status/"):
            return httpx.Response(200, json={"status": "100"})
        if path.endswith("/JSON/core/view/alerts/"):
            return httpx.Response(200, json={"alerts": []})
        return httpx.Response(404)

    mock_dast_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_zap_handler))
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_orchestrator] = lambda: OrchestratorAgent(
        db_engine=db_engine,
        dast_http_client=mock_dast_client,
    )
    store = AISecretStore.get_instance()
    store.set_credentials("gemini-2.0-flash", "test-key-dast-progression")
    client = TestClient(app)
    try:
        # 1. Verify GET /api/zap/status schema (T010)
        st_resp = client.get("/api/zap/status")
        assert st_resp.status_code == 200
        st_json = st_resp.json()
        assert isinstance(st_json["online"], bool)
        assert "zap_base_url" in st_json
        assert "host.docker.internal" in st_json["allowed_hosts"]
        assert "message" in st_json

        # 2. SAST + ZAP Baseline mode on `app` -> 50.0% PASS (4 PASS, 3 INCONCLUSIVE, 1 MANUAL_REQUIRED)
        resp_base = client.post(
            "/api/runs?sync=true",
            json={
                "source_type": "workspace_path",
                "workspace_subpath": "app",
                "target_url": "http://localhost:8000",
                "zap_authorized": True,
                "zap_mode": "baseline",
            },
        )
        assert resp_base.status_code == 202
        base_run_id = resp_base.json()["run_id"]
        detail_base = client.get(f"/api/runs/{base_run_id}").json()
        assert detail_base["metrics"]["fail_count"] == 0
        assert detail_base["metrics"]["pass_count"] == 4
        assert detail_base["metrics"]["inconclusive_count"] == 3
        assert detail_base["metrics"]["manual_count"] == 1
        assert detail_base["metrics"]["pass_percentage"] == 50.0

        base_verdicts = {v["req_id"]: v["status"] for v in detail_base["verdicts"]}
        for req_pass in ("V1.2.1", "V1.2.2", "V1.2.3", "V1.3.2"):
            assert base_verdicts[req_pass] == "PASS"
        for req_inc in ("V1.2.4", "V1.2.5", "V1.5.1"):
            assert base_verdicts[req_inc] == "INCONCLUSIVE"
        assert base_verdicts["V1.3.1"] == "MANUAL_REQUIRED"

        # 3. SAST + ZAP Active mode on `app` -> 87.5% PASS (7 PASS, 0 INCONCLUSIVE, 1 MANUAL_REQUIRED)
        resp_act = client.post(
            "/api/runs?sync=true",
            json={
                "source_type": "workspace_path",
                "workspace_subpath": "app",
                "target_url": "http://localhost:8000",
                "zap_authorized": True,
                "zap_mode": "active",
            },
        )
        assert resp_act.status_code == 202
        act_run_id = resp_act.json()["run_id"]
        detail_act = client.get(f"/api/runs/{act_run_id}").json()
        assert detail_act["metrics"]["fail_count"] == 0
        assert detail_act["metrics"]["pass_count"] == 7
        assert detail_act["metrics"]["inconclusive_count"] == 0
        assert detail_act["metrics"]["manual_count"] == 1
        assert detail_act["metrics"]["pass_percentage"] == 87.5

        act_verdicts = {v["req_id"]: v["status"] for v in detail_act["verdicts"]}
        for req_pass in (
            "V1.2.1",
            "V1.2.2",
            "V1.2.3",
            "V1.2.4",
            "V1.2.5",
            "V1.3.2",
            "V1.5.1",
        ):
            assert act_verdicts[req_pass] == "PASS"
        assert act_verdicts["V1.3.1"] == "MANUAL_REQUIRED"
    finally:
        store.reset_instance()
        app.dependency_overrides.clear()


def test_full_pipeline_active_dast_with_ai_achieves_100_percent_pass(
    db_engine: Engine, session: Session
) -> None:
    """Validate 100.0% PASS (8/8 PASS, 0 FAIL, 0 INC, 0 MANUAL) when ZAP Active + AI Evaluator are configured."""
    def mock_zap_handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/JSON/core/view/version/"):
            return httpx.Response(200, json={"version": "2.15.0"})
        if path.endswith("/JSON/core/action/accessUrl/"):
            return httpx.Response(200, json={"Result": "OK"})
        if path.endswith("/JSON/spider/action/scan/"):
            return httpx.Response(200, json={"scan": "1"})
        if path.endswith("/JSON/spider/view/status/"):
            return httpx.Response(200, json={"status": "100"})
        if path.endswith("/JSON/spider/view/results/"):
            return httpx.Response(
                200,
                json={"results": ["http://localhost:8000/", "http://localhost:8000/api/requirements/in-scope"]},
            )
        if path.endswith("/JSON/pscan/view/recordsToScan/"):
            return httpx.Response(200, json={"recordsToScan": "0"})
        if path.endswith("/JSON/ascan/action/scan/"):
            return httpx.Response(200, json={"scan": "2"})
        if path.endswith("/JSON/ascan/view/status/"):
            return httpx.Response(200, json={"status": "100"})
        if path.endswith("/JSON/core/view/alerts/"):
            return httpx.Response(200, json={"alerts": []})
        return httpx.Response(404)

    def mock_ai_handler(request: httpx.Request) -> httpx.Response:
        # Mock Gemini response returning structured PASS for V1.3.1
        resp_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "verdict": "PASS",
                                        "confidence": "HIGH",
                                        "rationale": "Autoescape padrão ativo em Jinja2 e sem renderização não sanitizada de HTML rico.",
                                        "evidence_snippets": ["templates/index.html"],
                                    }
                                )
                            }
                        ]
                    }
                }
            ]
        }
        return httpx.Response(200, json=resp_payload)

    mock_dast_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_zap_handler))
    mock_ai_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_ai_handler))

    # Configure AI credentials in volatile store
    store = AISecretStore.get_instance()
    store.set_credentials("gemini-2.0-flash", "test-secret-ai-key-100-pct")

    try:
        app.dependency_overrides[get_session] = lambda: session
        app.dependency_overrides[get_orchestrator] = lambda: OrchestratorAgent(
            db_engine=db_engine,
            dast_http_client=mock_dast_client,
            ai_http_client=mock_ai_client,
        )
        client = TestClient(app)

        resp = client.post(
            "/api/runs?sync=true",
            json={
                "source_type": "workspace_path",
                "workspace_subpath": "app",
                "target_url": "http://localhost:8000",
                "zap_authorized": True,
                "zap_mode": "active",
            },
        )
        assert resp.status_code == 202
        run_id = resp.json()["run_id"]
        detail = client.get(f"/api/runs/{run_id}").json()

        # Check metrics reach 100.0% PASS
        m = detail["metrics"]
        assert m["total_in_scope"] == 8
        assert m["pass_count"] == 8
        assert m["fail_count"] == 0
        assert m["inconclusive_count"] == 0
        assert m["manual_count"] == 0
        assert m["pass_percentage"] == 100.0

        # Verify all 8 requirements are PASS
        verdicts = {v["req_id"]: v for v in detail["verdicts"]}
        assert len(verdicts) == 8
        for req_id, v in verdicts.items():
            assert v["status"] == "PASS", f"Expected PASS for {req_id}, got {v['status']}"

        # Verify V1.3.1 specific details
        v131 = verdicts["V1.3.1"]
        assert v131["status"] == "PASS"
        assert v131["confidence_level"] == "HIGH"
        assert "ai_evaluator" in v131["tools_used"]
        assert any("AIEvaluatorAgent" in ev for ev in v131["positive_evidence"])
    finally:
        store.reset_instance()
        app.dependency_overrides.clear()



