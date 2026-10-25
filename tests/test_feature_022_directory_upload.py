"""Automated TDD Test Suite for Feature 022: Local Directory Code-Source Selection (Tab 1).

Spec Reference: specs/022-local-directory-picker/spec.md
Plan Reference: specs/022-local-directory-picker/plan.md
Constitutional Principles: I (ASVS V1 L1), IV (File Confinement & Safe Uploads), V (WCAG 2.2 AA / Fluent 2), VI (TDD)
"""

from __future__ import annotations

import io
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.aci.workspace_aci import (
    MAX_DIR_FILES,
    MAX_DIR_TOTAL_BYTES,
    MAX_DIR_UPLOAD_FILE_BYTES,
    WORKSPACE_ROOT,
    save_safe_directory_upload,
)
from app.core.ai_secrets import AISecretStore
from app.core.auth import get_current_user
from app.main import APP_UI_VERSION, app
from app.models import Run


@pytest.fixture(autouse=True)
def clean_auth_overrides():
    """Ensure clean dependency overrides for auth tests."""
    app.dependency_overrides.pop(get_current_user, None)
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _make_upload_file(filename: str, content: bytes) -> UploadFile:
    """Helper to construct an in-memory UploadFile instance."""
    buf = io.BytesIO(content)
    return UploadFile(file=buf, filename=filename, size=len(content))


# ==============================================================================
# Unit Tests for `save_safe_directory_upload`
# ==============================================================================


def test_save_safe_directory_upload_success(tmp_path: Path):
    """Persists multiple files preserving relative directory structure."""
    upload_id = "test_ok_123"
    files = [
        _make_upload_file("main.py", b"print('hello')\n"),
        _make_upload_file("calc.py", b"def add(a, b): return a + b\n"),
        _make_upload_file("README.md", b"# My Project\n"),
    ]
    paths = [
        "my-app/src/main.py",
        "my-app/src/utils/calc.py",
        "my-app/README.md",
    ]

    dest_dir = save_safe_directory_upload(files, paths, upload_id, base_root=tmp_path)
    assert dest_dir.exists()
    assert (dest_dir / "my-app" / "src" / "main.py").read_text() == "print('hello')\n"
    assert (dest_dir / "my-app" / "src" / "utils" / "calc.py").read_text() == "def add(a, b): return a + b\n"
    assert (dest_dir / "my-app" / "README.md").read_text() == "# My Project\n"


def test_save_safe_directory_upload_blocks_path_traversal(tmp_path: Path):
    """Rejects path traversal attempts with ../ and removes destination directory."""
    upload_id = "test_trav_1"
    files = [_make_upload_file("evil.py", b"malicious")]
    paths = ["my-app/../../evil.py"]

    with pytest.raises((PermissionError, ValueError)):
        save_safe_directory_upload(files, paths, upload_id, base_root=tmp_path)

    dest_dir = tmp_path / ".workspace_uploads" / f"dir_{upload_id}"
    assert not dest_dir.exists()


def test_save_safe_directory_upload_blocks_absolute_and_drive_paths(tmp_path: Path):
    """Rejects absolute paths and Windows drive letters."""
    upload_id = "test_abs_1"
    files = [_make_upload_file("passwd", b"root:x:0:0")]

    for bad_path in ["/etc/passwd", "\\windows\\system32", "C:\\app\\main.py", "D:/code/a.py"]:
        with pytest.raises((PermissionError, ValueError)):
            save_safe_directory_upload(files, [bad_path], upload_id, base_root=tmp_path)

        dest_dir = tmp_path / ".workspace_uploads" / f"dir_{upload_id}"
        assert not dest_dir.exists()


def test_save_safe_directory_upload_blocks_null_bytes_and_special_devices(tmp_path: Path):
    """Rejects null bytes, control characters, Windows devices and ADS."""
    upload_id = "test_special"
    files = [_make_upload_file("con.py", b"data")]

    for bad_path in [
        "app/foo\x00bar.py",
        "app/CON.py",
        "app/NUL",
        "app/AUX.txt",
        "app/PRN",
        "app/stream.txt:hidden",
        "app//empty_segment.py",
        "app/./dot_segment.py",
    ]:
        with pytest.raises((PermissionError, ValueError)):
            save_safe_directory_upload(files, [bad_path], upload_id, base_root=tmp_path)

        dest_dir = tmp_path / ".workspace_uploads" / f"dir_{upload_id}"
        assert not dest_dir.exists()


def test_save_safe_directory_upload_blocks_file_dir_conflict(tmp_path: Path):
    """Rejects conflicting file and directory names (e.g. 'app' as file and 'app/main.py')."""
    upload_id = "test_conflict"
    files = [
        _make_upload_file("app", b"file content"),
        _make_upload_file("main.py", b"code"),
    ]
    paths = ["src/app", "src/app/main.py"]

    with pytest.raises(ValueError):
        save_safe_directory_upload(files, paths, upload_id, base_root=tmp_path)

    dest_dir = tmp_path / ".workspace_uploads" / f"dir_{upload_id}"
    assert not dest_dir.exists()


def test_save_safe_directory_upload_enforces_size_limits(tmp_path: Path, monkeypatch):
    """Enforces per-file limit (5MB) and total aggregation limit."""
    upload_id = "test_size"

    # Per-file ceiling check
    large_file = _make_upload_file("big.bin", b"X" * (MAX_DIR_UPLOAD_FILE_BYTES + 10))
    with pytest.raises(ValueError) as excinfo:
        save_safe_directory_upload([large_file], ["app/big.bin"], upload_id, base_root=tmp_path)
    assert "limite máximo" in str(excinfo.value).lower() or "5 mb" in str(excinfo.value).lower()

    # Aggregate ceiling check (simulated with small monkeypatched limit)
    monkeypatch.setattr("app.aci.workspace_aci.MAX_DIR_TOTAL_BYTES", 50)
    files = [
        _make_upload_file("f1.txt", b"A" * 30),
        _make_upload_file("f2.txt", b"B" * 30),
    ]
    paths = ["app/f1.txt", "app/f2.txt"]
    with pytest.raises(ValueError) as exc_total:
        save_safe_directory_upload(files, paths, "test_total_size", base_root=tmp_path)
    assert "total" in str(exc_total.value).lower() or "300 mb" in str(exc_total.value).lower() or "limite" in str(exc_total.value).lower()


def test_save_safe_directory_upload_cleans_up_on_failure(tmp_path: Path):
    """Cleans up partially written directory if error occurs during streaming."""
    upload_id = "test_cleanup"

    class FailingIO(io.BytesIO):
        def read(self, *args, **kwargs):
            raise OSError("Simulated disk error during stream")

    bad_upload = UploadFile(file=FailingIO(b"abc"), filename="fail.py", size=3)
    good_upload = _make_upload_file("ok.py", b"ok")

    with pytest.raises(Exception):
        save_safe_directory_upload(
            [good_upload, bad_upload],
            ["app/ok.py", "app/fail.py"],
            upload_id,
            base_root=tmp_path,
        )

    dest_dir = tmp_path / ".workspace_uploads" / f"dir_{upload_id}"
    assert not dest_dir.exists()


# ==============================================================================
# Integration Tests for `POST /api/runs/upload-directory`
# ==============================================================================


def test_endpoint_upload_directory_success(auth_admin_client: TestClient, db_session: Session):
    """POST /api/runs/upload-directory accepts multipart files and paths, starting a Run with source_type='directory_upload'."""
    AISecretStore.get_instance().set_credentials(
        api_key="test-key-dir-022",
        model_name="gemini-2.0-flash",
        provider="gemini",
    )

    f1 = ("files", ("main.py", b"print(1)\n", "text/x-python"))
    f2 = ("files", ("calc.py", b"def add(a,b): return a+b\n", "text/x-python"))
    p1 = ("paths", "project/src/main.py")
    p2 = ("paths", "project/src/calc.py")

    with patch("app.agents.orchestrator.OrchestratorAgent.execute", new_callable=AsyncMock):
        resp = auth_admin_client.post(
            "/api/runs/upload-directory",
            data={
                "zap_authorized": "true",
                "zap_mode": "baseline",
                "target_url": "http://localhost:8000",
            },
            files=[f1, f2, p1, p2],
        )

    assert resp.status_code == 202, f"Expected 202, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["ok"] is True
    assert "run_id" in body
    run_id = body["run_id"]

    run_row = db_session.get(Run, run_id)
    assert run_row is not None
    assert run_row.source_type == "directory_upload"
    assert ".workspace_uploads" in run_row.source_path
    assert Path(run_row.source_path).exists()
    assert (Path(run_row.source_path) / "project" / "src" / "main.py").exists()


def test_endpoint_upload_directory_requires_auth(unauth_client: TestClient):
    """Unauthenticated access to upload-directory yields HTTP 401."""
    resp = unauth_client.post(
        "/api/runs/upload-directory",
        data={"zap_authorized": "true"},
        files=[("files", ("a.py", b"code", "text/x-python")), ("paths", "app/a.py")],
    )
    assert resp.status_code == 401


def test_endpoint_upload_directory_requires_dast_consent(auth_admin_client: TestClient):
    """Failure to provide zap_authorized=true triggers DAST guardrail HTTP 403."""
    AISecretStore.get_instance().set_credentials(
        api_key="test-key-022",
        model_name="gemini-2.0-flash",
        provider="gemini",
    )
    resp = auth_admin_client.post(
        "/api/runs/upload-directory",
        data={"zap_authorized": "false"},
        files=[("files", ("a.py", b"code", "text/x-python")), ("paths", "app/a.py")],
    )
    assert resp.status_code == 403
    assert "dast" in resp.json().get("detail", "").lower()


def test_endpoint_upload_directory_requires_ai_configured(auth_admin_client: TestClient):
    """Attempting upload without configured AI triggers HTTP 412."""
    AISecretStore.get_instance().clear_credentials()

    resp = auth_admin_client.post(
        "/api/runs/upload-directory",
        data={"zap_authorized": "true"},
        files=[("files", ("a.py", b"code", "text/x-python")), ("paths", "app/a.py")],
    )
    assert resp.status_code == 412
    assert "ia" in resp.json().get("detail", "").lower()


def test_endpoint_upload_directory_validates_list_parity(auth_admin_client: TestClient):
    """Mismatch between count of files and paths triggers HTTP 400."""
    AISecretStore.get_instance().set_credentials(
        api_key="test-key-022",
        model_name="gemini-2.0-flash",
        provider="gemini",
    )
    resp = auth_admin_client.post(
        "/api/runs/upload-directory",
        data={"zap_authorized": "true"},
        files=[
            ("files", ("a.py", b"code1", "text/x-python")),
            ("files", ("b.py", b"code2", "text/x-python")),
            ("paths", "app/a.py"),  # Only 1 path for 2 files
        ],
    )
    assert resp.status_code == 400
    assert "paridade" in resp.json().get("detail", "").lower() or "caminho" in resp.json().get("detail", "").lower()


# ==============================================================================
# UI & Static Assets Conformity
# ==============================================================================


def test_ui_assets_contain_directory_picker_and_no_workspace_label():
    """Validates that index.html and app.js implement directory picker and remove workspace path UI label."""
    root = Path(__file__).resolve().parent.parent
    html = (root / "templates" / "index.html").read_text(encoding="utf-8")
    js = (root / "static" / "app.js").read_text(encoding="utf-8")

    # index.html checks
    assert "Caminho em Diretório Local" in html
    assert 'value="directory_upload"' in html
    assert 'id="source-directory"' in html
    assert "webkitdirectory" in html
    assert 'id="source-directory-summary"' in html
    assert "Caminho em Workspace Local" not in html
    assert 'id="workspace-subpath"' not in html
    assert f"v={APP_UI_VERSION}" in html

    # app.js checks
    assert "upload-directory" in js
    assert "source-directory" in js
    assert "directory_upload" in js
    assert int(APP_UI_VERSION) >= 22

