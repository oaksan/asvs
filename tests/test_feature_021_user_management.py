"""Automated TDD Test Suite for Feature 021: Complete User Management & Password Reset (Tab 5).

Spec Reference: specs/021-complete-user-management/spec.md
Plan Reference: specs/021-complete-user-management/plan.md
Constitutional Principles: I (Zero-Leakage), IV (Guardrails & RBAC), VI (Code Quality & Traceability)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.auth import SESSION_COOKIE_NAME, UserSessionStore, get_current_user
from app.main import app
from app.models import AuditLog, Run, RunStatus, User, UserAIConfig, UserRole
from tests.conftest import create_test_user


@pytest.fixture(autouse=True)
def clean_auth_overrides():
    """Ensure get_current_user override from legacy tests is removed for strict auth tests."""
    app.dependency_overrides.pop(get_current_user, None)
    yield
    app.dependency_overrides.pop(get_current_user, None)


# ==============================================================================
# User Story 1: Alteração Voluntária da Própria Senha (POST /api/auth/change-password)
# ==============================================================================


def test_self_change_password_success(unauth_client: TestClient, db_session: Session):
    """US1 Scenario 1: Authenticated user successfully changes own password with correct current password."""
    # Given: a regular user in the database
    user = create_test_user(
        db_session,
        username="self_user",
        password="CurrentPassword123!",
        role="user",
        must_change_password=False,
    )

    # When: user logs in and submits change password form with valid current password
    login_resp = unauth_client.post(
        "/api/auth/login",
        json={"username": "self_user", "password": "CurrentPassword123!"},
    )
    assert login_resp.status_code == 200

    resp = unauth_client.post(
        "/api/auth/change-password",
        json={
            "current_password": "CurrentPassword123!",
            "new_password": "NewSecretPassword456!",
        },
    )

    # Then: password is updated, must_change_password is False, response is 200 OK
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("ok") is True

    db_session.refresh(user)
    assert user.must_change_password is False

    # And: old password no longer works for login
    fresh_client = TestClient(app)
    bad_login = fresh_client.post(
        "/api/auth/login",
        json={"username": "self_user", "password": "CurrentPassword123!"},
    )
    assert bad_login.status_code == 401

    # And: new password works for login
    good_login = fresh_client.post(
        "/api/auth/login",
        json={"username": "self_user", "password": "NewSecretPassword456!"},
    )
    assert good_login.status_code == 200


def test_self_change_password_wrong_current_password(
    unauth_client: TestClient, db_session: Session
):
    """US1 Scenario 2: Change password fails with HTTP 400 when current password is wrong."""
    # Given: authenticated user
    create_test_user(
        db_session,
        username="wrong_pw_user",
        password="CorrectPassword123!",
        role="user",
    )
    login_resp = unauth_client.post(
        "/api/auth/login",
        json={"username": "wrong_pw_user", "password": "CorrectPassword123!"},
    )
    assert login_resp.status_code == 200

    # When: user submits incorrect current password
    resp = unauth_client.post(
        "/api/auth/change-password",
        json={
            "current_password": "WrongPassword999!",
            "new_password": "NewValidPassword123!",
        },
    )

    # Then: returns HTTP 400 Bad Request
    assert resp.status_code == 400
    assert "incorreta" in resp.json().get("detail", "").lower()


# ==============================================================================
# User Story 2: Redefinição Administrativa de Senha de Terceiros (POST /api/users/{id}/reset-password)
# ==============================================================================


def test_admin_reset_user_password_success(
    auth_admin_client: TestClient, unauth_client: TestClient, db_session: Session
):
    """US2 Scenario 1 & 2: Admin sets temporary password for another user.

    Validates:
    - must_change_password becomes True
    - Old sessions are terminated
    - New password works for login
    - Zero-Leakage: no password_hash in response
    """
    # Given: a target user with an active session
    target = create_test_user(
        db_session,
        username="analyst_target",
        password="InitialPassword123!",
        role="user",
        must_change_password=False,
    )

    # Target user logs in on their own client
    target_client = TestClient(app)
    t_login = target_client.post(
        "/api/auth/login",
        json={"username": "analyst_target", "password": "InitialPassword123!"},
    )
    assert t_login.status_code == 200

    # Target's session works
    me_resp_before = target_client.get("/api/auth/me")
    assert me_resp_before.status_code == 200

    # When: Admin calls POST /api/users/{id}/reset-password
    temp_password = "TemporaryPassword2026!"
    reset_resp = auth_admin_client.post(
        f"/api/users/{target.id}/reset-password",
        json={"new_password": temp_password},
    )

    # Then: returns HTTP 200 with UserResponse
    assert reset_resp.status_code == 200
    res_data = reset_resp.json()
    assert res_data["id"] == target.id
    assert res_data["username"] == "analyst_target"
    assert res_data["must_change_password"] is True
    assert "password_hash" not in res_data
    assert "password" not in res_data

    # And: database record has must_change_password=True
    db_session.refresh(target)
    assert target.must_change_password is True

    # And: old sessions are invalidated (session termination)
    me_resp_after = target_client.get("/api/auth/me")
    assert me_resp_after.status_code == 401

    # And: old password no longer works
    bad_login = unauth_client.post(
        "/api/auth/login",
        json={"username": "analyst_target", "password": "InitialPassword123!"},
    )
    assert bad_login.status_code == 401

    # And: new temporary password works for login and indicates must_change_password=True
    new_login = unauth_client.post(
        "/api/auth/login",
        json={"username": "analyst_target", "password": temp_password},
    )
    assert new_login.status_code == 200
    assert new_login.json()["must_change_password"] is True


def test_admin_cannot_reset_own_password_via_reset_endpoint(
    auth_admin_client: TestClient, db_session: Session
):
    """US2 Scenario 3: Admin cannot use third-party reset endpoint on own account (HTTP 400)."""
    # Given: admin user ID
    admin_user = db_session.exec(select(User).where(User.username == "admin")).first()
    assert admin_user is not None

    # When: admin calls reset-password on own id
    resp = auth_admin_client.post(
        f"/api/users/{admin_user.id}/reset-password",
        json={"new_password": "NewAdminPassword123!"},
    )

    # Then: returns HTTP 400 Bad Request
    assert resp.status_code == 400
    detail = resp.json().get("detail", "").lower()
    assert "própria senha" in detail or "inválida" in detail or "alterar sua" in detail


# ==============================================================================
# User Story 3: Alteração de Papel e Prevenção de Auto-Rebaixamento / Lockout
# ==============================================================================


def test_admin_change_user_role_success(
    auth_admin_client: TestClient, db_session: Session
):
    """US3 Scenario 1: Admin can promote user to admin and demote back to user."""
    # Given: a regular user
    user = create_test_user(
        db_session,
        username="promotable_user",
        role="user",
    )

    # Create active session for promotable_user
    session_store = UserSessionStore.get_instance()
    session_store.create_session(user)

    # When: Admin promotes user to admin
    promote_resp = auth_admin_client.patch(
        f"/api/users/{user.id}/role",
        json={"role": "admin"},
    )

    # Then: role is updated to admin
    assert promote_resp.status_code == 200
    assert promote_resp.json()["role"] == "admin"
    db_session.refresh(user)
    assert user.role == "admin"

    # And: active sessions for user are terminated to enforce re-login with new claims
    tokens = [t for t, s in session_store._sessions.items() if s.user_id == user.id]
    assert len(tokens) == 0

    # When: Admin demotes user back to user
    demote_resp = auth_admin_client.patch(
        f"/api/users/{user.id}/role",
        json={"role": "user"},
    )

    # Then: role is updated back to user
    assert demote_resp.status_code == 200
    assert demote_resp.json()["role"] == "user"
    db_session.refresh(user)
    assert user.role == "user"


def test_admin_cannot_change_own_role(
    auth_admin_client: TestClient, db_session: Session
):
    """US3 Scenario 2: Admin cannot change their own role (HTTP 400)."""
    admin_user = db_session.exec(select(User).where(User.username == "admin")).first()
    assert admin_user is not None

    resp = auth_admin_client.patch(
        f"/api/users/{admin_user.id}/role",
        json={"role": "user"},
    )
    assert resp.status_code == 400
    detail = resp.json().get("detail", "").lower()
    assert "própria" in detail or "papel" in detail


def test_cannot_demote_last_admin(
    auth_admin_client: TestClient, db_session: Session
):
    """US3 Scenario 3: Demoting the last active admin is blocked with HTTP 400."""
    # Given: a second admin user
    second_admin = create_test_user(
        db_session,
        username="second_admin",
        role="admin",
        is_active=True,
    )

    # Deactivate the primary admin in DB so second_admin is the only active admin remaining
    primary_admin = db_session.exec(select(User).where(User.username == "admin")).first()
    assert primary_admin is not None
    primary_admin.is_active = False
    db_session.add(primary_admin)
    db_session.commit()

    # When: attempting to demote the sole active admin
    resp = auth_admin_client.patch(
        f"/api/users/{second_admin.id}/role",
        json={"role": "user"},
    )

    # Then: blocked with HTTP 400 Bad Request
    assert resp.status_code == 400
    assert "último administrador" in resp.json().get("detail", "").lower()


# ==============================================================================
# User Story 4: Exclusão Segura com Preservação de Histórico e Anti-Lockout
# ==============================================================================


def test_admin_delete_user_success(
    auth_admin_client: TestClient, db_session: Session
):
    """US4 Scenario 1: Admin deletes another user.

    Validates:
    - UserAIConfig is deleted in cascade
    - Historic Run records are reassigned to executing admin
    - AuditLog entries are dissociated (user_id set to None)
    - User is removed from DB
    - Active sessions are terminated
    """
    # Given: a target user with UserAIConfig, a Run, and an AuditLog entry
    target = create_test_user(
        db_session,
        username="user_to_delete",
        role="user",
    )

    # Associated UserAIConfig
    ai_cfg = UserAIConfig(
        user_id=target.id,
        provider="gemini",
        model_name="gemini-2.0-flash",
        encrypted_api_key=b"sample_encrypted_key",
        nonce=b"sample_nonce_bytes",
    )
    db_session.add(ai_cfg)

    # Associated Run
    run_record = Run(
        target_url="http://localhost:8000",
        source_path="/tmp/project",
        status=RunStatus.COMPLETED,
        user_id=target.id,
    )
    db_session.add(run_record)
    db_session.commit()
    db_session.refresh(run_record)

    # Associated AuditLog
    audit_entry = AuditLog(
        run_id=run_record.id or 1,
        finding_id=1,
        req_id="V1.1.1",
        action="test_action",
        previous_value=False,
        new_value=True,
        justification="Test audit log justification",
        user_id=target.id,
    )
    db_session.add(audit_entry)
    db_session.commit()
    db_session.refresh(audit_entry)

    # Active session in UserSessionStore
    session_store = UserSessionStore.get_instance()
    session_store.create_session(target)

    # When: Admin calls DELETE /api/users/{id}
    del_resp = auth_admin_client.delete(f"/api/users/{target.id}")

    # Then: HTTP 200 OK
    assert del_resp.status_code == 200
    assert del_resp.json().get("id") == target.id

    # And: User is removed from database
    assert db_session.get(User, target.id) is None

    # And: UserAIConfig is purged in cascade
    orphan_cfg = db_session.exec(
        select(UserAIConfig).where(UserAIConfig.user_id == target.id)
    ).first()
    assert orphan_cfg is None

    # And: Run was reassigned to executing admin
    db_session.refresh(run_record)
    assert run_record.user_id is not None
    assert run_record.user_id != target.id

    # And: AuditLog entry is preserved and dissociated from deleted user
    db_session.refresh(audit_entry)
    assert audit_entry.user_id is None

    # And: User's active sessions were terminated
    tokens = [t for t, s in session_store._sessions.items() if s.user_id == target.id]
    assert len(tokens) == 0


def test_admin_cannot_delete_self(
    auth_admin_client: TestClient, db_session: Session
):
    """US4 Scenario 2: Admin attempting to delete own account is rejected with HTTP 400."""
    admin_user = db_session.exec(select(User).where(User.username == "admin")).first()
    assert admin_user is not None

    resp = auth_admin_client.delete(f"/api/users/{admin_user.id}")
    assert resp.status_code == 400
    detail = resp.json().get("detail", "").lower()
    assert "própria conta" in detail or "auto-exclusão" in detail or "a si próprio" in detail


def test_admin_cannot_deactivate_self(
    auth_admin_client: TestClient, db_session: Session
):
    """Guardrail: Admin cannot deactivate their own account (HTTP 400)."""
    admin_user = db_session.exec(select(User).where(User.username == "admin")).first()
    assert admin_user is not None

    resp = auth_admin_client.patch(
        f"/api/users/{admin_user.id}/status",
        json={"is_active": False},
    )
    assert resp.status_code == 400
    assert "própria conta" in resp.json().get("detail", "").lower()


def test_cannot_delete_last_admin(
    auth_admin_client: TestClient, db_session: Session
):
    """US4 Scenario 3: Deleting the last active admin is rejected with HTTP 400."""
    # Given: a second admin user
    target_admin = create_test_user(
        db_session,
        username="sole_active_admin",
        role="admin",
        is_active=True,
    )

    # Deactivate the caller admin in the DB so target_admin is the only active admin remaining
    primary_admin = db_session.exec(select(User).where(User.username == "admin")).first()
    assert primary_admin is not None
    primary_admin.is_active = False
    db_session.add(primary_admin)
    db_session.commit()

    # When: Admin attempts to delete the sole active admin
    resp = auth_admin_client.delete(f"/api/users/{target_admin.id}")

    # Then: rejected with HTTP 400
    assert resp.status_code == 400
    assert "último administrador" in resp.json().get("detail", "").lower()


# ==============================================================================
# RBAC Guardrails: Usuário comum bloqueado em todos os novos endpoints
# ==============================================================================


def test_non_admin_forbidden_on_all_new_endpoints(
    auth_user_client: TestClient, db_session: Session
):
    """US4 / RBAC Guardrail: Non-admin users strictly receive HTTP 403 Forbidden on all management endpoints."""
    # POST /api/users/{id}/reset-password
    r_reset = auth_user_client.post(
        "/api/users/1/reset-password",
        json={"new_password": "HackerPassword123!"},
    )
    assert r_reset.status_code == 403

    # PATCH /api/users/{id}/role
    r_role = auth_user_client.patch(
        "/api/users/1/role",
        json={"role": "admin"},
    )
    assert r_role.status_code == 403

    # DELETE /api/users/{id}
    r_del = auth_user_client.delete("/api/users/1")
    assert r_del.status_code == 403


# ==============================================================================
# Edge Cases & Validation Guardrails
# ==============================================================================


def test_endpoints_return_404_for_nonexistent_user(
    auth_admin_client: TestClient
):
    """Edge Case: Endpoints return HTTP 404 Not Found when target user does not exist."""
    nonexistent_id = 99999

    r_reset = auth_admin_client.post(
        f"/api/users/{nonexistent_id}/reset-password",
        json={"new_password": "ValidPassword123!"},
    )
    assert r_reset.status_code == 404

    r_role = auth_admin_client.patch(
        f"/api/users/{nonexistent_id}/role",
        json={"role": "admin"},
    )
    assert r_role.status_code == 404

    r_del = auth_admin_client.delete(f"/api/users/{nonexistent_id}")
    assert r_del.status_code == 404


def test_reset_password_validates_payload_length(
    auth_admin_client: TestClient, db_session: Session
):
    """Input Guardrail: Password reset enforces minimum 8 characters via Pydantic."""
    target = create_test_user(
        db_session,
        username="short_pw_target",
        role="user",
    )
    resp = auth_admin_client.post(
        f"/api/users/{target.id}/reset-password",
        json={"new_password": "short"},
    )
    assert resp.status_code == 422


def test_ui_assets_feature_021():
    """Verify that index.html and app.js include all UI components for Feature 021."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    html = (root / "templates" / "index.html").read_text(encoding="utf-8")
    js = (root / "static" / "app.js").read_text(encoding="utf-8")

    # index.html
    assert "self-change-password-form" in html
    assert "self-current-password" in html
    assert "self-new-password" in html
    assert "self-confirm-password" in html
    assert "reset-user-dialog" in html
    assert "reset-user-new-password" in html
    assert "v=021" in html

    # app.js
    assert "self-change-password-form" in js
    assert "reset-user-dialog" in js
    assert "(Você)" in js
    assert "reset-password" in js
    assert "openResetUserModal" in js


