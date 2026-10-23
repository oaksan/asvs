"""Session management, authentication dependencies, and RBAC authorization (Feature 007)."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session

from app.core.ai_secrets import AISecretStore
from app.core.crypto import decrypt_secret
from app.database import get_session
from app.models import Run, SessionUser, User, UserAIConfig, UserRole

SESSION_COOKIE_NAME = "asvs_session"
SESSION_MAX_AGE_SECONDS = 8 * 3600  # 8 hours
SESSION_IDLE_TIMEOUT_SECONDS = 3600  # 1 hour


@dataclass
class SessionData:
    """In-memory active session tracking volatile AI credentials and user state."""

    session_token: str
    user_id: int
    username: str
    role: str
    must_change_password: bool
    is_active: bool
    created_at: float
    last_active: float
    ai_api_key: str | None = None
    ai_provider: str = "gemini"
    ai_model_name: str = "gemini-2.0-flash"
    ai_resource_name: str | None = None
    ai_deployment_id: str | None = None
    ai_api_version: str = "2024-06-01"


class UserSessionStore:
    """Thread-safe in-memory session manager for authenticated users and volatile AI secrets."""

    _instance: UserSessionStore | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._lock_state = threading.Lock()
        self._sessions: dict[str, SessionData] = {}

    @classmethod
    def get_instance(cls) -> UserSessionStore:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None

    def create_session(
        self,
        user: User,
        ai_config: UserAIConfig | None = None,
    ) -> SessionData:
        """Create a new session, decrypt any saved AI config into volatile memory, and return session data."""
        now = time.time()
        session_token = secrets.token_urlsafe(32)

        decrypted_key: str | None = None
        provider = "gemini"
        model_name = "gemini-2.0-flash"
        resource_name: str | None = None
        deployment_id: str | None = None
        api_version = "2024-06-01"

        if ai_config:
            try:
                decrypted_key = decrypt_secret(
                    ai_config.encrypted_api_key,
                    ai_config.nonce,
                )
                provider = ai_config.provider
                model_name = ai_config.model_name
                resource_name = ai_config.resource_name
                deployment_id = ai_config.deployment_id
                api_version = ai_config.api_version

                AISecretStore.get_instance().set_credentials(
                    model_name=model_name,
                    api_key=decrypted_key,
                    provider=provider,
                    resource_name=resource_name,
                    deployment_id=deployment_id,
                    api_version=api_version,
                )
            except Exception:
                decrypted_key = None

        s_data = SessionData(
            session_token=session_token,
            user_id=int(user.id or 0),
            username=user.username,
            role=user.role,
            must_change_password=user.must_change_password,
            is_active=user.is_active,
            created_at=now,
            last_active=now,
            ai_api_key=decrypted_key,
            ai_provider=provider,
            ai_model_name=model_name,
            ai_resource_name=resource_name,
            ai_deployment_id=deployment_id,
            ai_api_version=api_version,
        )

        with self._lock_state:
            self._sessions[session_token] = s_data

        return s_data

    def get_session(self, session_token: str | None) -> SessionData | None:
        """Retrieve active session by token, validating expiration."""
        if not session_token:
            return None

        now = time.time()
        with self._lock_state:
            s_data = self._sessions.get(session_token)
            if not s_data:
                return None

            if (
                now - s_data.created_at > SESSION_MAX_AGE_SECONDS
                or now - s_data.last_active > SESSION_IDLE_TIMEOUT_SECONDS
            ):
                del self._sessions[session_token]
                return None

            s_data.last_active = now
            return s_data

    def terminate_session(self, session_token: str | None) -> bool:
        """Terminate active session and purge volatile in-memory AI credentials."""
        if not session_token:
            return False

        with self._lock_state:
            s_data = self._sessions.pop(session_token, None)
            if s_data:
                s_data.ai_api_key = None
                AISecretStore.get_instance().clear_credentials()
                return True
        return False

    def terminate_user_sessions(self, user_id: int) -> None:
        """Terminate all sessions for a specific user ID."""
        with self._lock_state:
            tokens_to_remove = [
                token
                for token, s_data in self._sessions.items()
                if s_data.user_id == user_id
            ]
            for token in tokens_to_remove:
                s_data = self._sessions.pop(token, None)
                if s_data:
                    s_data.ai_api_key = None
            AISecretStore.get_instance().clear_credentials()

    def update_password_changed(self, user_id: int) -> None:
        """Update must_change_password=False for all active sessions of this user."""
        with self._lock_state:
            for s_data in self._sessions.values():
                if s_data.user_id == user_id:
                    s_data.must_change_password = False

    def set_session_ai_credentials(
        self,
        session_token: str,
        api_key: str,
        provider: str = "gemini",
        model_name: str = "gemini-2.0-flash",
        resource_name: str | None = None,
        deployment_id: str | None = None,
        api_version: str = "2024-06-01",
    ) -> None:
        """Update volatile AI credentials on the active session."""
        with self._lock_state:
            s_data = self._sessions.get(session_token)
            if s_data:
                s_data.ai_api_key = api_key
                s_data.ai_provider = provider
                s_data.ai_model_name = model_name
                s_data.ai_resource_name = resource_name
                s_data.ai_deployment_id = deployment_id
                s_data.ai_api_version = api_version


user_session_store = UserSessionStore.get_instance()


async def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> SessionUser:
    """FastAPI dependency: validate session cookie and enforce authentication & password rotation."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação obrigatória: cookie de sessão ausente.",
        )

    s_data = user_session_store.get_session(token)
    if not s_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada. Faça login novamente.",
        )

    if not s_data.is_active:
        user_session_store.terminate_session(token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Conta de usuário inativa.",
        )

    if s_data.must_change_password:
        allowed_paths = (
            "/api/auth/change-password",
            "/api/auth/logout",
            "/api/auth/me",
        )
        if request.url.path not in allowed_paths:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Troca de senha mandatória pendente. Altere sua senha antes de prosseguir.",
            )

    return SessionUser(
        id=s_data.user_id,
        username=s_data.username,
        role=s_data.role,
        must_change_password=s_data.must_change_password,
        is_active=s_data.is_active,
    )


async def require_admin(
    current_user: SessionUser = Depends(get_current_user),
) -> SessionUser:
    """FastAPI dependency: strictly require admin role or return 403 Forbidden."""
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: funcionalidade restrita a administradores.",
        )
    return current_user


def verify_run_access(
    run_id: int,
    current_user: SessionUser,
    session: Session,
) -> Run:
    """Verify run exists and enforce RBAC: Admin sees all; User sees strictly their own runs."""
    run_row = session.get(Run, run_id)
    if not run_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run #{run_id} não encontrada.",
        )

    if current_user.role != UserRole.ADMIN.value and run_row.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: você não tem permissão para acessar esta avaliação.",
        )
    return run_row

