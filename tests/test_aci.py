"""Unit tests for ACI guardrails, pagination, truncation, and zero-finding feedback (T017)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from sqlmodel import Session

from app.aci import semgrep_aci, workspace_aci, zap_aci
from app.models import Run


def test_workspace_aci_blocks_path_traversal(db_session: Session):
    """Paths containing '..' or escaping WORKSPACE_ROOT are rejected by the guardrail."""
    run = Run(source_type="workspace_path", source_path="tests/vulnerable_app")
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    res = workspace_aci.scan_workspace_surface(
        db_session, run.id, "../../etc/passwd"  # type: ignore[arg-type]
    )
    assert res.ok is False
    assert "Guardrail" in res.summary_message or "Bloqueio" in res.summary_message
    assert res.corrective_hint is not None


def test_extract_safe_zip_blocks_zip_slip(tmp_path: Path):
    """Archive entries containing '../' are blocked before extraction."""
    malicious_zip = tmp_path / "evil.zip"
    with zipfile.ZipFile(malicious_zip, "w") as zf:
        zf.writestr("../../outside.py", "print('pwned')")

    with pytest.raises(PermissionError, match="path traversal"):
        workspace_aci.extract_safe_zip(malicious_zip, run_id=99, base_root=tmp_path)


def test_aci_pagination_enforces_max_50_items():
    """paginate_items never returns more than 50 items per page even if requested."""
    items = list(range(135))
    sliced, cur_page, cur_size, total_pages, has_next = workspace_aci.paginate_items(
        items, page=1, page_size=500
    )
    assert len(sliced) == 50
    assert cur_page == 1
    assert cur_size == 50
    assert total_pages == 3
    assert has_next is True


def test_collapse_observation_history_keeps_sliding_window():
    """Observations older than K=5 are collapsed into single-line summaries."""
    obs = [
        {"command": f"cmd_{i}", "duration_ms": 10 * i, "summary_message": f"msg {i}"}
        for i in range(8)
    ]
    folded = workspace_aci.collapse_observation_history(obs, max_detailed=5)
    assert len(folded) == 8
    assert folded[0].get("collapsed") is True
    assert "Observação colapsada #1" in folded[0]["summary_line"]
    assert folded[2].get("collapsed") is True
    assert folded[3].get("collapsed") is None


def test_list_files_returns_explicit_message_when_zero_matches(db_session: Session):
    """Commands returning 0 items still provide a non-empty informative summary_message."""
    run = Run(source_type="workspace_path", source_path="tests/vulnerable_app")
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    res = workspace_aci.list_files(
        db_session, run.id, "tests/vulnerable_app", pattern="*.nonexistent_ext"  # type: ignore[arg-type]
    )
    assert res.ok is True
    assert res.total_items == 0
    assert "0 arquivos encontrados" in res.summary_message


@pytest.mark.asyncio
async def test_zap_aci_blocks_unauthorized_or_non_allowlisted_targets(db_session: Session):
    """ZAP ACI blocks scans when zap_authorized=False or host is not in allowlist."""
    run = Run(source_type="workspace_path", source_path="tests/vulnerable_app")
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    # 1. Missing authorization checkbox
    unauth = await zap_aci.zap_spider(
        db_session, run.id, "http://localhost:8000", zap_authorized=False  # type: ignore[arg-type]
    )
    assert unauth.ok is False
    assert "autorização" in unauth.summary_message

    # 2. Target outside allowlist
    external = await zap_aci.zap_scan(
        db_session,
        run.id,  # type: ignore[arg-type]
        "https://evil-external-domain.example.com",
        zap_authorized=True,
        mode="baseline",
    )
    assert external.ok is False
    assert "allowlist" in external.summary_message


def test_semgrep_aci_detects_findings_in_vulnerable_fixture(db_session: Session):
    """semgrep_aci.run_rules detects planted SQLi in tests/vulnerable_app."""
    run = Run(source_type="workspace_path", source_path="tests/vulnerable_app")
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    res = semgrep_aci.run_rules(
        db_session, run.id, "V1.2.4", "tests/vulnerable_app"  # type: ignore[arg-type]
    )
    assert res.ok is True
    assert res.total_items >= 1
    assert "achado(s) detectado(s)" in res.summary_message


@pytest.mark.asyncio
async def test_check_zap_connectivity_online_and_offline():
    """check_zap_connectivity reports online=True with version when ZAP responds, and online=False when unreachable (T010)."""
    import httpx

    def online_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/JSON/core/view/version/"):
            return httpx.Response(200, json={"version": "2.15.0"})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(online_handler)) as client_ok:
        st_ok = await zap_aci.check_zap_connectivity(http_client=client_ok)
        assert st_ok["online"] is True
        assert st_ok["version"] == "2.15.0"
        assert "host.docker.internal" in st_ok["allowed_hosts"]
        assert "ONLINE" in st_ok["message"]

    def offline_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(offline_handler)) as client_off:
        st_off = await zap_aci.check_zap_connectivity(http_client=client_off)
        assert st_off["online"] is False
        assert st_off["version"] is None
        assert "docker compose up -d zap" in st_off["message"]


@pytest.mark.asyncio
async def test_zap_aci_resolves_localhost_to_docker_host_and_polls_spider_pscan_ascan(
    db_session: Session,
):
    """zap_spider and zap_scan rewrite localhost -> host.docker.internal when needed and poll spider/pscan/ascan to 100% (T005)."""
    import httpx

    run = Run(source_type="workspace_path", source_path="app")
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    state_counters = {"spider_polls": 0, "pscan_polls": 0, "ascan_polls": 0}

    def zap_daemon_handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        params = dict(request.url.params)
        if path.endswith("/JSON/core/view/version/"):
            return httpx.Response(200, json={"version": "2.15.0"})
        if path.endswith("/JSON/core/action/accessUrl/"):
            target = params.get("url", "")
            # Simulate container isolation: localhost fails inside container, host.docker.internal succeeds
            if "localhost" in target or "127.0.0.1" in target:
                return httpx.Response(500, json={"code": "internal_error"})
            if "host.docker.internal" in target:
                return httpx.Response(200, json={"Result": "OK"})
            return httpx.Response(200, json={"Result": "OK"})
        if path.endswith("/JSON/spider/action/scan/"):
            return httpx.Response(200, json={"scan": "1"})
        if path.endswith("/JSON/spider/view/status/"):
            state_counters["spider_polls"] += 1
            pct = "45" if state_counters["spider_polls"] == 1 else "100"
            return httpx.Response(200, json={"status": pct})
        if path.endswith("/JSON/spider/view/results/"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        "http://host.docker.internal:8000/",
                        "http://host.docker.internal:8000/api/requirements/in-scope",
                    ]
                },
            )
        if path.endswith("/JSON/pscan/view/recordsToScan/"):
            state_counters["pscan_polls"] += 1
            rem = "2" if state_counters["pscan_polls"] == 1 else "0"
            return httpx.Response(200, json={"recordsToScan": rem})
        if path.endswith("/JSON/ascan/action/scan/"):
            return httpx.Response(200, json={"scan": "7"})
        if path.endswith("/JSON/ascan/view/status/"):
            state_counters["ascan_polls"] += 1
            pct = "50" if state_counters["ascan_polls"] == 1 else "100"
            return httpx.Response(200, json={"status": pct})
        if path.endswith("/JSON/core/view/alerts/"):
            return httpx.Response(200, json={"alerts": []})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(zap_daemon_handler)) as mock_client:
        spider_res = await zap_aci.zap_spider(
            db_session,
            run.id,  # type: ignore[arg-type]
            "http://localhost:8000",
            zap_authorized=True,
            http_client=mock_client,
            poll_interval_sec=0.01,
        )
        assert spider_res.ok is True
        sdata = spider_res.data or {}
        assert sdata["zap_daemon_used"] is True
        assert sdata["resolved_target_url"] == "http://host.docker.internal:8000/"
        assert sdata["spider_progress"] == 100
        assert sdata["urls_count"] == 2
        assert state_counters["spider_polls"] >= 2

        # Baseline scan: passive plugins executed (V1.2.1, V1.2.2, V1.2.3), active-only empty
        base_res = await zap_aci.zap_scan(
            db_session,
            run.id,  # type: ignore[arg-type]
            "http://localhost:8000",
            zap_authorized=True,
            mode="baseline",
            http_client=mock_client,
            poll_interval_sec=0.01,
        )
        assert base_res.ok is True
        bdata = base_res.data or {}
        assert bdata["zap_daemon_used"] is True
        assert bdata["pscan_records_remaining"] == 0
        assert bdata["ascan_progress"] is None
        assert len(bdata["executed_plugins_by_req"]["V1.2.1"]) >= 1
        assert bdata["executed_plugins_by_req"]["V1.2.4"] == []

        # Active scan: both passive and active plugins executed (all 6 DAST requirements covered)
        act_res = await zap_aci.zap_scan(
            db_session,
            run.id,  # type: ignore[arg-type]
            "http://localhost:8000",
            zap_authorized=True,
            mode="active",
            http_client=mock_client,
            poll_interval_sec=0.01,
        )
        assert act_res.ok is True
        adata = act_res.data or {}
        assert adata["zap_daemon_used"] is True
        assert adata["ascan_progress"] == 100
        assert state_counters["ascan_polls"] >= 2
        for req_id in ("V1.2.1", "V1.2.2", "V1.2.3", "V1.2.4", "V1.2.5", "V1.5.1"):
            assert len(adata["executed_plugins_by_req"][req_id]) >= 1


