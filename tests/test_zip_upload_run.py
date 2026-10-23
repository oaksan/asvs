"""Automated TDD tests for ZIP Upload Assessment Flow and Guardrails (Features 009 & 010).

Spec Reference: specs/009-fix-zip-upload-assessment/spec.md, specs/010-unified-zip-upload-and-cache-busting/spec.md
"""

from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.aci import workspace_aci
from app.core.ai_secrets import AISecretStore
from app.main import app
from app.models import Run


def _make_zip_bytes(files: dict[str, str | bytes]) -> bytes:
    """Create an in-memory ZIP archive from a filename->content mapping."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_zip_upload_with_zip_file_field_and_real_extracted_path(db_session: Session):
    """POST /api/runs/upload accepts 'zip_file' field and persists the real extracted directory in Run.source_path."""
    AISecretStore.get_instance().set_credentials(
        api_key="test-key-zip-009",
        model_name="gemini-2.5-flash",
        provider="gemini",
    )
    zip_bytes = _make_zip_bytes(
        {
            "juice-shop-master/app.js": "const express = require('express');\n",
            "juice-shop-master/routes/search.ts": "export function search(q: string) { return q; }\n",
        }
    )

    client = TestClient(app)
    with patch("app.agents.orchestrator.OrchestratorAgent.execute", new_callable=AsyncMock):
        resp = client.post(
            "/api/runs/upload",
            data={
                "source_type": "zip_upload",
                "zap_authorized": "true",
                "zap_mode": "active",
                "target_url": "http://localhost:3000",
            },
            files={"zip_file": ("juice-shop-master.zip", zip_bytes, "application/zip")},
        )

    assert resp.status_code == 202, f"Expected 202, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["ok"] is True
    run_id = body["run_id"]

    run_row = db_session.get(Run, run_id)
    assert run_row is not None
    extracted_path = Path(run_row.source_path)
    try:
        assert extracted_path.exists(), f"Run.source_path '{extracted_path}' does not exist on disk!"
        assert (extracted_path / "juice-shop-master" / "app.js").exists()

        # Verify Scoper can scan the extracted path without guardrail errors
        scope_res = workspace_aci.scan_workspace_surface(db_session, run_id, run_row.source_path)
        assert scope_res.ok is True
        assert scope_res.data["total_files"] >= 2
    finally:
        if extracted_path.exists() and ".workspace_uploads" in str(extracted_path):
            shutil.rmtree(extracted_path, ignore_errors=True)


def test_post_api_runs_accepts_multipart_zip_upload_directly(db_session: Session):
    """POST /api/runs natively supports multipart/form-data zip_upload by delegating to create_run_via_upload."""
    AISecretStore.get_instance().set_credentials(
        api_key="test-key-zip-010",
        model_name="gemini-2.5-flash",
        provider="gemini",
    )
    zip_bytes = _make_zip_bytes(
        {
            "juice-shop-master/server.ts": "console.log('Juice Shop');\n",
        }
    )

    client = TestClient(app)
    with patch("app.agents.orchestrator.OrchestratorAgent.execute", new_callable=AsyncMock):
        resp = client.post(
            "/api/runs",
            data={
                "source_type": "zip_upload",
                "zap_authorized": "true",
                "zap_mode": "active",
                "target_url": "http://localhost:3000",
            },
            files={"zip_file": ("juice-shop-master.zip", zip_bytes, "application/zip")},
        )

    assert resp.status_code == 202, f"Expected 202 on POST /api/runs multipart, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["ok"] is True
    run_row = db_session.get(Run, body["run_id"])
    assert run_row is not None
    extracted_path = Path(run_row.source_path)
    try:
        assert (extracted_path / "juice-shop-master" / "server.ts").exists()
    finally:
        if extracted_path.exists() and ".workspace_uploads" in str(extracted_path):
            shutil.rmtree(extracted_path, ignore_errors=True)


def test_extract_safe_zip_supports_over_2000_files_like_juice_shop(tmp_path: Path):
    """extract_safe_zip allows archives with 2,500 files (such as OWASP Juice Shop)."""
    zip_path = tmp_path / "large_project.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i in range(2500):
            zf.writestr(f"juice-shop-master/src/file_{i}.ts", f"export const x_{i} = {i};\n")

    extracted_dir = workspace_aci.extract_safe_zip(zip_path, run_id="test_2500", base_root=tmp_path)
    assert extracted_dir.exists()
    assert (extracted_dir / "juice-shop-master" / "src" / "file_0.ts").exists()
    assert (extracted_dir / "juice-shop-master" / "src" / "file_2499.ts").exists()


def test_zip_upload_rejects_zip_slip_with_json_400(db_session: Session):
    """POST /api/runs/upload rejects malicious ZipSlip archive with HTTP 400 in valid JSON."""
    AISecretStore.get_instance().set_credentials(
        api_key="test-key-zip-009",
        model_name="gemini-2.5-flash",
        provider="gemini",
    )
    malicious_bytes = _make_zip_bytes({"../../evil_escape.py": "print('escaped')"})

    client = TestClient(app)
    resp = client.post(
        "/api/runs/upload",
        data={
            "zap_authorized": "true",
            "zap_mode": "baseline",
        },
        files={"zip_file": ("evil.zip", malicious_bytes, "application/zip")},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert "path traversal" in data.get("detail", "").lower()


def test_validation_error_422_returns_string_detail_never_object_list(db_session: Session):
    """Validation errors return a human-readable string in 'detail' (never a raw list that turns into [object Object])."""
    client = TestClient(app, raise_server_exceptions=False)
    # Send raw non-UTF8 bytes with application/json header to trigger validation error
    resp = client.post(
        "/api/runs",
        content=b"PK\x03\x04\n\x00\x00\x00\x08\x00\xe4lO]\xff\xfe\xfd\x80invalid_json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422, f"Expected 422 JSON, got {resp.status_code}: {resp.text}"
    payload = resp.json()
    assert isinstance(payload.get("detail"), str), f"Expected detail to be str, got: {type(payload.get('detail'))}"
    assert "[object Object]" not in payload["detail"]
    assert isinstance(payload.get("errors"), list)


def test_static_assets_and_index_have_cache_busting_and_no_cache_headers():
    """GET / includes ?v=014 cache-busting and /static/app.js returns Cache-Control: no-cache."""
    client = TestClient(app)
    res_index = client.get("/")
    assert res_index.status_code == 200
    assert "/static/app.js?v=014" in res_index.text

    res_js = client.get("/static/app.js")
    assert res_js.status_code == 200
    assert "no-cache" in res_js.headers.get("cache-control", "").lower()
    assert 'fetch("/api/runs/upload"' in res_js.text


def test_real_juice_shop_master_zip_upload_via_post_api_runs(db_session: Session):
    """If /home/user/felipe/speckit/juice-shop-master.zip exists, verify it uploads and extracts via POST /api/runs."""
    real_zip = Path("/home/user/felipe/speckit/juice-shop-master.zip")
    if not real_zip.exists():
        return

    AISecretStore.get_instance().set_credentials(
        api_key="test-key-zip-js",
        model_name="gemini-2.5-flash",
        provider="gemini",
    )
    client = TestClient(app)
    with patch("app.agents.orchestrator.OrchestratorAgent.execute", new_callable=AsyncMock):
        with open(real_zip, "rb") as fh:
            resp = client.post(
                "/api/runs",
                data={
                    "source_type": "zip_upload",
                    "zap_authorized": "true",
                    "zap_mode": "active",
                    "target_url": "http://localhost:3000",
                },
                files={"zip_file": ("juice-shop-master.zip", fh, "application/zip")},
            )

    assert resp.status_code == 202, f"Expected 202 for juice-shop-master.zip, got {resp.status_code}: {resp.text}"
    body = resp.json()
    run_row = db_session.get(Run, body["run_id"])
    assert run_row is not None
    extracted_path = Path(run_row.source_path)
    try:
        assert extracted_path.exists()
        scope_res = workspace_aci.scan_workspace_surface(db_session, body["run_id"], run_row.source_path)
        assert scope_res.ok is True
        assert scope_res.data["total_files"] > 500
    finally:
        if extracted_path.exists() and ".workspace_uploads" in str(extracted_path):
            shutil.rmtree(extracted_path, ignore_errors=True)

