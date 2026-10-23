"""Shared pytest fixtures for ASVS-Self-Assesment-Tool tests."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, select

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.agents.orchestrator import OrchestratorAgent
from app.database import get_session, seed_requirements_if_empty, seed_admin_if_empty
from app.main import app, get_orchestrator
from app.models import (
    AuditLog,
    Evidence,
    Finding,
    Requirement,
    Run,
    ToolCall,
    User,
    UserAIConfig,
    Verdict,
)


@pytest.fixture()
def db_engine(tmp_path: Path) -> Engine:
    """Provide an isolated SQLite Engine seeded with all 345 ASVS 5.0 requirements and admin user."""
    db_file = tmp_path / "test_asvs.db"
    test_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as s:
        seed_requirements_if_empty(s)
        seed_admin_if_empty(s)
    return test_engine


@pytest.fixture()
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    """Provide an isolated SQLite Session seeded with all 345 ASVS 5.0 requirements."""
    app.dependency_overrides[get_orchestrator] = lambda: OrchestratorAgent(db_engine=db_engine)
    with Session(db_engine) as s:
        app.dependency_overrides[get_session] = lambda: s
        yield s
        app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_orchestrator, None)


@pytest.fixture()
def session(db_session: Session) -> Session:
    """Alias fixture for `db_session`."""
    return db_session


# ---------------------------------------------------------------------------
# Fixtures e Utilitários de Autenticação (Feature 007)
# ---------------------------------------------------------------------------


def login_user(client: TestClient, username: str, password: str) -> Any:
    """Helper to authenticate a client via POST /api/auth/login and capture cookies."""
    return client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )


def create_test_user(
    session: Session,
    username: str,
    password: str = "TestPassword123!",
    role: str = "user",
    must_change_password: bool = False,
    is_active: bool = True,
) -> Any:
    """Helper to persist a test user directly into the database."""
    from app.core.crypto import hash_password

    pw_hash = hash_password(password)
    user = User(
        username=username,
        password_hash=pw_hash,
        role=role,
        must_change_password=must_change_password,
        is_active=is_active,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture()
def unauth_client(db_session: Session) -> TestClient:
    """Provide a fresh TestClient without active session cookies."""
    from app.core.auth import get_current_user
    app.dependency_overrides.pop(get_current_user, None)
    return TestClient(app)


@pytest.fixture()
def auth_admin_client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provide a TestClient authenticated as 'admin' with must_change_password=False."""
    from app.core.auth import get_current_user
    app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(app)

    admin_user = db_session.exec(
        select(User).where(User.username == "admin")
    ).first()

    if not admin_user:
        admin_user = create_test_user(
            db_session,
            username="admin",
            password="admin",
            role="admin",
            must_change_password=False,
        )
    else:
        admin_user.must_change_password = False
        db_session.add(admin_user)
        db_session.commit()

    login_res = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    if login_res.status_code == 200 and login_res.json().get("must_change_password"):
        client.post(
            "/api/auth/change-password",
            json={
                "current_password": "admin",
                "new_password": "AdminPassword123!",
            },
        )

    yield client


@pytest.fixture()
def auth_user_client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provide a TestClient authenticated as regular user 'analyst_bob' with role='user'."""
    from app.core.auth import get_current_user
    app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(app)

    regular_user = db_session.exec(
        select(User).where(User.username == "analyst_bob")
    ).first()

    if not regular_user:
        create_test_user(
            db_session,
            username="analyst_bob",
            password="BobPassword123!",
            role="user",
            must_change_password=False,
        )

    client.post(
        "/api/auth/login",
        json={"username": "analyst_bob", "password": "BobPassword123!"},
    )

    yield client


@pytest.fixture(autouse=True)
def auto_auth_for_legacy_tests(request: pytest.FixtureRequest) -> Generator[None, None, None]:
    """Provide automatic authenticated admin context for legacy tests, preserving strict auth in new tests."""
    module_name = request.module.__name__
    is_new_auth_test = "test_auth_rbac" in module_name or "test_encrypted_user_ai_secrets" in module_name

    from app.core.auth import get_current_user
    from app.models import SessionUser

    if is_new_auth_test:
        app.dependency_overrides.pop(get_current_user, None)
        yield
        app.dependency_overrides.pop(get_current_user, None)
    else:
        app.dependency_overrides[get_current_user] = lambda: SessionUser(
            id=1,
            username="admin",
            role="admin",
            must_change_password=False,
            is_active=True,
        )
        yield
        app.dependency_overrides.pop(get_current_user, None)
