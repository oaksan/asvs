"""Automated tests for Authentication, Local User Management, and RBAC (Feature 007).

Spec Reference: specs/007-auth-rbac-and-encrypted-user-ai-config/spec.md
Contracts: specs/007-auth-rbac-and-encrypted-user-ai-config/contracts/auth-api.yaml
Tasks: T002
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.ai_secrets import AISecretStore
from app.main import app
from app.models import AuditLog, Finding, Run, RunStatus, User, UserRole
from tests.conftest import create_test_user, login_user


# ==============================================================================
# User Story 1: Autenticação Local e Troca Mandatória de Senha
# ==============================================================================


def test_initial_db_seeds_admin_with_must_change_password(db_session: Session):
    """US1 / SC-002: Startup with empty DB initializes admin user with must_change_password=True."""
    admin = db_session.exec(select(User).where(User.username == "admin")).first()
    assert admin is not None, "Conta padrão 'admin' deve existir após inicialização do banco."
    assert admin.role == "admin"
    assert admin.must_change_password is True
    assert admin.is_active is True


def test_login_success_with_default_credentials(unauth_client: TestClient, db_session: Session):
    """US1 Scenario 2: Login with admin/admin issues secure session cookie and indicates must_change_password."""
    resp = unauth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["username"] == "admin"
    assert data["role"] == "admin"
    assert data["must_change_password"] is True
    assert "asvs_session" in resp.cookies
    cookie_header = resp.headers.get("set-cookie", "")
    assert "asvs_session" in cookie_header
    assert "httponly" in cookie_header.lower()
    assert "samesite=lax" in cookie_header.lower()


def test_login_incorrect_password_returns_401(unauth_client: TestClient):
    """US1 Scenario 1: Submitting incorrect password returns 401 Unauthorized."""
    resp = unauth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert resp.status_code == 401
    assert "asvs_session" not in resp.cookies


def test_login_nonexistent_user_returns_401(unauth_client: TestClient):
    """US1: Submitting non-existent username returns 401 Unauthorized."""
    resp = unauth_client.post(
        "/api/auth/login",
        json={"username": "nonexistent_user", "password": "admin"},
    )
    assert resp.status_code == 401


def test_unauthenticated_request_to_protected_routes_returns_401(unauth_client: TestClient):
    """US1 / SC-001: Accessing protected endpoints without active session strictly returns 401."""
    resp_runs = unauth_client.get("/api/runs")
    assert resp_runs.status_code == 401

    resp_me = unauth_client.get("/api/auth/me")
    assert resp_me.status_code == 401

    resp_users = unauth_client.get("/api/users")
    assert resp_users.status_code == 401


def test_user_with_must_change_password_blocked_with_403(unauth_client: TestClient):
    """US1 Scenario 3: User with must_change_password=True is blocked on general routes with 403."""
    login_resp = unauth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["must_change_password"] is True

    resp_runs = unauth_client.get("/api/runs")
    assert resp_runs.status_code == 403
    assert "senha" in resp_runs.json().get("detail", "").lower()

    resp_users = unauth_client.get("/api/users")
    assert resp_users.status_code == 403


def test_change_password_success_unblocks_protected_routes(
    unauth_client: TestClient, db_session: Session
):
    """US1 Scenario 4: POST /api/auth/change-password updates password, clears flag, and unblocks access."""
    unauth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )

    change_resp = unauth_client.post(
        "/api/auth/change-password",
        json={"current_password": "admin", "new_password": "NewStrongAdminPassword123!"},
    )
    assert change_resp.status_code == 200
    assert change_resp.json()["ok"] is True

    me_resp = unauth_client.get("/api/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["must_change_password"] is False

    runs_resp = unauth_client.get("/api/runs")
    assert runs_resp.status_code == 200


def test_change_password_rejects_incorrect_current_password(unauth_client: TestClient):
    """US1: POST /api/auth/change-password fails if current password is incorrect."""
    unauth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    resp = unauth_client.post(
        "/api/auth/change-password",
        json={"current_password": "wrong-current-pass", "new_password": "NewStrongPass123!"},
    )
    assert resp.status_code in (400, 401)


def test_change_password_enforces_minimum_length(unauth_client: TestClient):
    """US1 Scenario 3: Passwords shorter than 8 characters are strictly rejected."""
    unauth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    resp = unauth_client.post(
        "/api/auth/change-password",
        json={"current_password": "admin", "new_password": "short"},
    )
    assert resp.status_code in (400, 422)


def test_logout_invalidates_session_and_clears_cookie(unauth_client: TestClient):
    """US1 Scenario 5: POST /api/auth/logout invalidates session and removes access."""
    unauth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    logout_resp = unauth_client.post("/api/auth/logout")
    assert logout_resp.status_code == 200
    assert logout_resp.json()["ok"] is True

    me_resp = unauth_client.get("/api/auth/me")
    assert me_resp.status_code == 401


def test_session_fixation_immunity_regenerates_session_token(unauth_client: TestClient):
    """FR-005: Successful authentication regenerates session token for fixation immunity."""
    resp1 = unauth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    cookie1 = resp1.cookies.get("asvs_session")

    resp2 = unauth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    cookie2 = resp2.cookies.get("asvs_session")

    assert cookie1 != cookie2, "O token de sessão deve ser regenerado em cada login bem-sucedido."


# ==============================================================================
# User Story 4: Gestão de Usuários Locais (RBAC Admin)
# ==============================================================================


def test_admin_can_list_users(auth_admin_client: TestClient):
    """US4 Scenario 3 / FR-011: Admin can list all users; password hashes are strictly omitted."""
    resp = auth_admin_client.get("/api/users")
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)
    assert len(users) >= 1

    admin_entry = users[0]
    assert "id" in admin_entry
    assert "username" in admin_entry
    assert "role" in admin_entry
    assert "is_active" in admin_entry
    assert "password_hash" not in admin_entry
    assert "password_salt" not in admin_entry


def test_regular_user_cannot_list_users(auth_user_client: TestClient):
    """US4 Scenario 4 / FR-011: Regular user gets 403 Forbidden when calling GET /api/users."""
    resp = auth_user_client.get("/api/users")
    assert resp.status_code == 403
    assert "administradores" in resp.json().get("detail", "").lower()


def test_admin_can_create_new_user(auth_admin_client: TestClient, unauth_client: TestClient):
    """US4 Scenario 2 / FR-011: Admin creates new local user; user can log in with must_change_password=True."""
    payload = {
        "username": "analyst_clara",
        "password": "ClaraPassword123!",
        "role": "user",
    }
    create_resp = auth_admin_client.post("/api/users", json=payload)
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["username"] == "analyst_clara"
    assert data["role"] == "user"
    assert data["must_change_password"] is True
    assert "password_hash" not in data

    login_resp = unauth_client.post(
        "/api/auth/login",
        json={"username": "analyst_clara", "password": "ClaraPassword123!"},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["must_change_password"] is True


def test_regular_user_cannot_create_users(auth_user_client: TestClient):
    """US4 Scenario 4: Regular user calling POST /api/users is rejected with 403 Forbidden."""
    payload = {
        "username": "hacker_user",
        "password": "HackerPassword123!",
        "role": "admin",
    }
    resp = auth_user_client.post("/api/users", json=payload)
    assert resp.status_code == 403


def test_create_user_duplicate_username_fails(auth_admin_client: TestClient):
    """US4 / contracts: Duplicate username creation returns 400 Bad Request."""
    payload = {
        "username": "duplicate_user",
        "password": "DuplicatePassword123!",
        "role": "user",
    }
    resp1 = auth_admin_client.post("/api/users", json=payload)
    assert resp1.status_code == 201

    resp2 = auth_admin_client.post("/api/users", json=payload)
    assert resp2.status_code == 400


def test_admin_can_deactivate_and_reactivate_user(
    auth_admin_client: TestClient, unauth_client: TestClient, db_session: Session
):
    """US4 / EC-003: Admin deactivates account; deactivated user cannot log in."""
    user = create_test_user(
        db_session,
        username="user_to_deactivate",
        password="ValidPassword123!",
        role="user",
    )

    deact_resp = auth_admin_client.patch(
        f"/api/users/{user.id}/status",
        json={"is_active": False},
    )
    assert deact_resp.status_code == 200
    assert deact_resp.json()["is_active"] is False

    login_resp = unauth_client.post(
        "/api/auth/login",
        json={"username": "user_to_deactivate", "password": "ValidPassword123!"},
    )
    assert login_resp.status_code == 401

    react_resp = auth_admin_client.patch(
        f"/api/users/{user.id}/status",
        json={"is_active": True},
    )
    assert react_resp.status_code == 200
    assert react_resp.json()["is_active"] is True


def test_lockout_prevention_blocks_deactivating_last_active_admin(
    auth_admin_client: TestClient, db_session: Session
):
    """US4 Scenario 5 / FR-012: Lockout prevention blocks deactivating the only active admin."""
    admin = db_session.exec(select(User).where(User.username == "admin")).first()
    assert admin is not None

    resp = auth_admin_client.patch(
        f"/api/users/{admin.id}/status",
        json={"is_active": False},
    )
    assert resp.status_code in (400, 403)
    assert "lockout" in resp.json().get("detail", "").lower() or "último administrador" in resp.json().get("detail", "").lower()


# ==============================================================================
# User Story 2: RBAC e Prevenção Inegociável de IDOR
# ==============================================================================


def _setup_runs_for_users(db_session: Session) -> tuple[int, int, int, int]:
    """Cria dois usuários e duas avaliações distintas para testes de IDOR."""
    user_a = create_test_user(db_session, "user_alice", "AlicePass123!", role="user")
    user_b = create_test_user(db_session, "user_bob", "BobPass123!", role="user")

    run_a = Run(
        source_type="workspace_path",
        source_path="tests/vulnerable_app",
        user_id=user_a.id,
        owner_username="user_alice",
        status=RunStatus.COMPLETED.value,
    )
    run_b = Run(
        source_type="workspace_path",
        source_path="tests/vulnerable_app",
        user_id=user_b.id,
        owner_username="user_bob",
        status=RunStatus.COMPLETED.value,
    )
    db_session.add(run_a)
    db_session.add(run_b)
    db_session.commit()
    db_session.refresh(run_a)
    db_session.refresh(run_b)

    finding_a = Finding(
        run_id=run_a.id,
        req_id="V1.2.4",
        tool="semgrep",
        rule_or_plugin_id="v1-2-4-sql-injection",
        title="SQL Injection Finding",
        primary_location="app/db.py:42",
        fingerprint="fp-alice-12345",
    )
    db_session.add(finding_a)
    db_session.commit()
    db_session.refresh(finding_a)

    return user_a.id, user_b.id, run_a.id, finding_a.id


def test_run_creation_binds_authenticated_user_identity(
    auth_user_client: TestClient, db_session: Session
):
    """FR-007: Run creation binds current_user.id and current_user.username."""
    AISecretStore.get_instance().set_credentials("gemini-2.0-flash", "test-key-valid")
    payload = {
        "source_type": "workspace_path",
        "workspace_subpath": "tests/vulnerable_app",
        "target_url": None,
        "zap_authorized": True,
        "zap_mode": "baseline",
    }
    resp = auth_user_client.post("/api/runs", json=payload)
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]

    run_row = db_session.get(Run, run_id)
    assert run_row is not None
    assert run_row.owner_username == "analyst_bob"


def test_admin_sees_all_runs_while_user_sees_only_own_runs(
    auth_admin_client: TestClient, unauth_client: TestClient, db_session: Session
):
    """US2 Scenario 1 & 3 / FR-008: Admin lists all runs; regular user sees strictly their own runs."""
    _, _, run_a_id, _ = _setup_runs_for_users(db_session)

    admin_runs_resp = auth_admin_client.get("/api/runs")
    assert admin_runs_resp.status_code == 200
    admin_run_ids = [r["id"] for r in admin_runs_resp.json()["items"]]
    assert run_a_id in admin_run_ids

    alice_client = TestClient(app)
    alice_client.post(
        "/api/auth/login",
        json={"username": "user_alice", "password": "AlicePass123!"},
    )
    alice_runs_resp = alice_client.get("/api/runs")
    assert alice_runs_resp.status_code == 200
    alice_run_ids = [r["id"] for r in alice_runs_resp.json()["items"]]
    assert run_a_id in alice_run_ids

    bob_client = TestClient(app)
    bob_client.post(
        "/api/auth/login",
        json={"username": "user_bob", "password": "BobPass123!"},
    )
    bob_runs_resp = bob_client.get("/api/runs")
    assert bob_runs_resp.status_code == 200
    bob_run_ids = [r["id"] for r in bob_runs_resp.json()["items"]]
    assert run_a_id not in bob_run_ids, "Bob NUNCA deve visualizar as execuções pertencentes à Alice."


def test_idor_regular_user_blocked_from_other_users_run_endpoints(
    db_session: Session
):
    """US2 Scenario 2 / FR-009 / SC-003: Strict 403 Forbidden for IDOR across all run sub-resources."""
    _, _, run_a_id, finding_a_id = _setup_runs_for_users(db_session)

    bob_client = TestClient(app)
    bob_client.post(
        "/api/auth/login",
        json={"username": "user_bob", "password": "BobPass123!"},
    )

    assert bob_client.get(f"/api/runs/{run_a_id}").status_code == 403
    assert bob_client.get(f"/api/runs/{run_a_id}/findings").status_code == 403
    assert bob_client.get(f"/api/runs/{run_a_id}/export?format=json").status_code == 403
    assert bob_client.get(f"/api/runs/{run_a_id}/export?format=html").status_code == 403
    assert bob_client.post(f"/api/runs/{run_a_id}/cancel").status_code == 403
    assert bob_client.post(f"/api/runs/{run_a_id}/rerun").status_code == 403
    assert bob_client.get(f"/api/findings/{finding_a_id}/evidence").status_code == 403
    assert bob_client.get(f"/api/runs/{run_a_id}/events").status_code == 403


def test_idor_compare_runs_rejected_when_accessing_third_party_runs(
    db_session: Session
):
    """EC-004: GET /api/runs/compare returns 403 Forbidden if any compared run belongs to another user."""
    _, _, run_a_id, _ = _setup_runs_for_users(db_session)

    bob_client = TestClient(app)
    bob_client.post(
        "/api/auth/login",
        json={"username": "user_bob", "password": "BobPass123!"},
    )

    resp = bob_client.get(f"/api/runs/compare?base_run_id={run_a_id}&target_run_id={run_a_id}")
    assert resp.status_code == 403


def test_triage_audit_log_enforces_immutable_session_actor(db_session: Session):
    """US2 Scenario 4 / FR-010: Triage operation strictly writes actor from current session username."""
    _, _, run_a_id, finding_a_id = _setup_runs_for_users(db_session)

    alice_client = TestClient(app)
    alice_client.post(
        "/api/auth/login",
        json={"username": "user_alice", "password": "AlicePass123!"},
    )

    triage_payload = {
        "is_false_positive": True,
        "justification": "Validação de entrada com regex estrita inspecionada no código.",
        "actor": "fake_spoofed_admin",
    }
    resp = alice_client.patch(f"/api/findings/{finding_a_id}/triage", json=triage_payload)
    assert resp.status_code == 200

    audit_entry = db_session.exec(
        select(AuditLog).where(AuditLog.finding_id == finding_a_id)
    ).first()
    assert audit_entry is not None
    assert audit_entry.actor == "user_alice", "O actor do AuditLog DEVE ser extraído compulsoriamente da sessão ativa, ignorando spoofing."


def test_triage_of_other_users_finding_blocked_with_403(db_session: Session):
    """US2: Triage attempt by non-owner returns 403 Forbidden."""
    _, _, _, finding_a_id = _setup_runs_for_users(db_session)

    bob_client = TestClient(app)
    bob_client.post(
        "/api/auth/login",
        json={"username": "user_bob", "password": "BobPass123!"},
    )

    triage_payload = {
        "is_false_positive": True,
        "justification": "Tentativa indevida de triagem em achado de terceiro.",
    }
    resp = bob_client.patch(f"/api/findings/{finding_a_id}/triage", json=triage_payload)
    assert resp.status_code == 403


def test_authorized_sse_events_streaming(db_session: Session):
    """Verify that an authorized owner can stream SSE events without Queue iteration TypeError."""
    _, _, run_a_id, _ = _setup_runs_for_users(db_session)

    alice_client = TestClient(app)
    alice_client.post(
        "/api/auth/login",
        json={"username": "user_alice", "password": "AlicePass123!"},
    )

    with alice_client.stream("GET", f"/api/runs/{run_a_id}/events") as stream_resp:
        assert stream_resp.status_code == 200
        assert "text/event-stream" in stream_resp.headers["content-type"]
        # Consume the first event/line to ensure generator yields properly without exception
        for line in stream_resp.iter_lines():
            if line:
                assert "pipeline_update" in line or "data" in line
                break

