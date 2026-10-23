"""FastAPI Application Entrypoint (`app/main.py`).

Exposes REST & Server-Sent Events (SSE) endpoints for the OWASP ASVS 5.0
Chapter V1 (Level 1) Self-Assessment Tool. Uses FastAPI dependency injection
(`Depends`) for database sessions, configuration, authentication, and the multi-agent orchestrator.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

import jinja2
from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ValidationError
from sse_starlette.sse import EventSourceResponse
from sqlmodel import Session, func, select

from app.aci import ai_aci
from app.aci.ai_aci import check_ai_connectivity
from app.aci.workspace_aci import (
    WORKSPACE_ROOT,
    extract_safe_zip,
    paginate_items,
    resolve_and_confine_path,
)
from app.aci.zap_aci import (
    check_zap_connectivity,
    get_allowed_hosts,
    validate_dast_target,
)
from app.agents.orchestrator import (
    OrchestratorAgent,
    OrchestratorInput,
    event_broker,
)
from app.agents.reporter_agent import build_full_report_dict, render_static_html_report
from app.agents.verdict_agent import recalculate_single_requirement_verdict
from app.core.ai_secrets import AISecretStore
from app.core.auth import (
    SESSION_COOKIE_NAME,
    get_current_user,
    require_admin,
    user_session_store,
    verify_run_access,
)
from app.core.crypto import decrypt_secret, encrypt_secret, hash_password, verify_password
from app.database import (
    IN_SCOPE_REQ_IDS,
    PROJECT_ROOT,
    engine,
    get_session,
    init_db,
    load_req_tool_mapping,
)
from app.models import (
    AIChatTestRequest,
    AIChatTestResponse,
    AIConfigRequest,
    AIConfigStatus,
    AITestConnectionResponse,
    AuditLog,
    ChangePasswordRequest,
    CreateRunRequest,
    Evidence,
    Finding,
    LoginRequest,
    LoginResponse,
    PipelineStage,
    Requirement,
    Run,
    RunStatus,
    SelectiveRerunRequest,
    SessionUser,
    TriageUpdateRequest,
    User,
    UserAIConfig,
    UserCreateRequest,
    UserResponse,
    UserRole,
    UserStatusUpdateRequest,
    Verdict,
    utcnow,
)


class ZAPDaemonStatus(BaseModel):
    """Pydantic schema for `GET /api/zap/status`."""

    online: bool
    version: str | None = None
    zap_base_url: str
    allowed_hosts: list[str]
    message: str


TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"

_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=jinja2.select_autoescape(["html", "xml"], default_for_string=True, default=True),
)
templates = Jinja2Templates(env=_jinja_env)


def get_config() -> dict[str, Any]:
    """Dependency returning the parsed `config/req_tool_mapping.yaml` dictionary."""
    return load_req_tool_mapping()


def get_orchestrator() -> OrchestratorAgent:
    """Dependency returning an `OrchestratorAgent` bound to the active database engine."""
    return OrchestratorAgent(db_engine=engine)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize SQLite schema, column migrations, and seeds on startup."""
    init_db(engine)
    yield


APP_UI_VERSION = "019"

app = FastAPI(
    title="OWASP ASVS 5.0 (V1 L1) Self-Assessment Tool",
    version="1.0.0",
    description=(
        "Multi-agent SAST (Semgrep) + DAST (OWASP ZAP) verification pipeline "
        "scoped strictly to ASVS 5.0 Chapter V1 (Encoding and Sanitization) Level 1."
    ),
    lifespan=lifespan,
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.middleware("http")
async def disable_static_cache_middleware(request: Request, call_next: Any) -> Response:
    """Ensure browser always fetches latest static JS/CSS and index HTML without stale cache and set security headers."""
    response: Response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self' https://unpkg.com; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    )
    return response


def _sanitize_validation_errors(obj: Any) -> Any:
    """Recursively replace raw bytes in FastAPI validation errors to prevent UnicodeDecodeError."""
    if isinstance(obj, bytes):
        return f"<binary data: {len(obj)} bytes>"
    if isinstance(obj, dict):
        return {k: _sanitize_validation_errors(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_validation_errors(item) for item in obj]
    return obj


@app.exception_handler(RequestValidationError)
async def safe_request_validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return HTTP 422 JSON safely with a readable string in 'detail' and list in 'errors'."""
    safe_errors = _sanitize_validation_errors(exc.errors())
    encoded_errors = jsonable_encoder(safe_errors)
    messages: list[str] = []
    if isinstance(encoded_errors, list):
        for err in encoded_errors:
            if isinstance(err, dict):
                loc = ".".join(str(x) for x in err.get("loc", []) if x != "body")
                msg = str(err.get("msg", "Parâmetro inválido"))
                messages.append(f"{loc}: {msg}" if loc else msg)
    detail_str = "; ".join(messages) if messages else "Dados de entrada inválidos na requisição."
    return JSONResponse(
        status_code=422,
        content={
            "detail": f"Erro de validação nos parâmetros enviados ({detail_str})",
            "errors": encoded_errors,
        },
    )


# ==============================================================================
# 1. UI Entrypoint & OWASP ZAP Daemon Connectivity Status
# ==============================================================================


@app.get("/")
async def index_page(
    request: Request,
    config: dict[str, Any] = Depends(get_config),
) -> Response:
    """Render the Fluent 2 Web UI dashboard with strict HTML autoescaping."""
    allowlist = sorted(get_allowed_hosts())
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "page_title": "Avaliação de Segurança — OWASP ASVS 5.0",
            "app_version": APP_UI_VERSION,
            "in_scope_req_ids": list(IN_SCOPE_REQ_IDS),
            "allowed_origins": allowlist,
            "scope_version": config.get("standard_version", "5.0.0"),
        },
    )


@app.get("/api/zap/status", response_model=ZAPDaemonStatus)
async def get_zap_daemon_status() -> ZAPDaemonStatus:
    """Check in real time whether the OWASP ZAP daemon is reachable and return connectivity metadata."""
    status_dict = await check_zap_connectivity()
    return ZAPDaemonStatus(**status_dict)


@app.get("/api/requirements/in-scope")
def get_in_scope_requirements(session: Session = Depends(get_session)) -> dict[str, Any]:
    """Return the 8 in-scope ASVS 5.0 V1 L1 requirements."""
    mapping_cfg = load_req_tool_mapping().get("requirements", {})
    reqs = list(
        session.exec(
            select(Requirement).where(Requirement.in_scope == True).order_by(Requirement.req_id)  # noqa: E712
        ).all()
    )
    return {
        "total": len(reqs),
        "items": [
            {
                "req_id": r.req_id,
                "chapter_id": r.chapter_id,
                "chapter_name": r.chapter_name,
                "section_id": r.section_id,
                "section_name": r.section_name,
                "req_description": r.req_description,
                "description_pt": mapping_cfg.get(r.req_id, {}).get("description_pt", ""),
                "friendly_title": mapping_cfg.get(r.req_id, {}).get("friendly_title")
                or r.section_name,
                "level": r.level,
                "in_scope": r.in_scope,
            }
            for r in reqs
        ],
    }


@app.get("/api/requirements")
def list_requirements(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    chapter_id: str | None = None,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """List ASVS requirements with optional chapter filter and pagination."""
    query = select(Requirement).order_by(Requirement.req_id)
    if chapter_id:
        query = query.where(Requirement.chapter_id == chapter_id.strip())

    reqs = list(session.exec(query).all())
    total = len(reqs)
    start = (page - 1) * page_size
    end = start + page_size
    items = reqs[start:end]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "req_id": r.req_id,
                "chapter_id": r.chapter_id,
                "chapter_name": r.chapter_name,
                "section_id": r.section_id,
                "section_name": r.section_name,
                "req_description": r.req_description,
                "level": r.level,
                "in_scope": r.in_scope,
            }
            for r in items
        ],
    }


# ==============================================================================
# 2. Authentication & User Management Endpoints (Feature 007)
# ==============================================================================


@app.post("/api/auth/login", response_model=LoginResponse)
def auth_login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Authenticate local user, issue HttpOnly session cookie, and decrypt saved AI config."""
    user = session.exec(
        select(User).where(User.username == payload.username.strip())
    ).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Conta de usuário inativa.",
        )

    old_token = request.cookies.get(SESSION_COOKIE_NAME)
    if old_token:
        user_session_store.terminate_session(old_token)

    ai_config = session.exec(
        select(UserAIConfig).where(UserAIConfig.user_id == user.id)
    ).first()

    session_data = user_session_store.create_session(user, ai_config)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_data.session_token,
        httponly=True,
        samesite="lax",
        path="/",
    )

    return {
        "ok": True,
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "must_change_password": user.must_change_password,
        "ai_configured": bool(session_data.ai_api_key),
        "ai_model_name": session_data.ai_model_name if session_data.ai_api_key else None,
    }


@app.post("/api/auth/logout")
def auth_logout(
    request: Request,
    response: Response,
) -> dict[str, Any]:
    """Terminate active session and purge volatile in-memory AI credentials."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        user_session_store.terminate_session(token)
    AISecretStore.get_instance().clear_credentials()
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return {"ok": True, "message": "Sessão encerrada com sucesso."}


@app.get("/api/auth/me", response_model=UserResponse)
def auth_me(
    current_user: SessionUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Return profile for the currently authenticated session."""
    user = session.get(User, current_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado.",
        )
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "must_change_password": user.must_change_password,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }


@app.post("/api/auth/change-password")
def auth_change_password(
    payload: ChangePasswordRequest,
    current_user: SessionUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Change password for the current user and unblock mandatory password change."""
    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova senha deve possuir no mínimo 8 caracteres.",
        )

    user = session.get(User, current_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado.",
        )

    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual incorreta.",
        )

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.updated_at = utcnow()
    session.add(user)
    session.commit()

    user_session_store.update_password_changed(user.id)
    return {"ok": True, "message": "Senha alterada com sucesso."}


@app.get("/api/users", response_model=list[UserResponse])
def list_users(
    admin: SessionUser = Depends(require_admin),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """List all local user accounts (Admin only). Password hashes are strictly omitted."""
    users = list(session.exec(select(User).order_by(User.id)).all())
    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "must_change_password": u.must_change_password,
            "is_active": u.is_active,
            "created_at": u.created_at,
        }
        for u in users
    ]


@app.post("/api/users", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
def create_user(
    payload: UserCreateRequest,
    admin: SessionUser = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Create a new local user with mandatory password change flag set (Admin only)."""
    uname = payload.username.strip()
    existing = session.exec(select(User).where(User.username == uname)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome de usuário já existe.",
        )

    new_user = User(
        username=uname,
        password_hash=hash_password(payload.password),
        role=payload.role,
        must_change_password=True,
        is_active=True,
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    return {
        "id": new_user.id,
        "username": new_user.username,
        "role": new_user.role,
        "must_change_password": new_user.must_change_password,
        "is_active": new_user.is_active,
        "created_at": new_user.created_at,
    }


@app.patch("/api/users/{user_id}/status", response_model=UserResponse)
def update_user_status(
    user_id: int,
    payload: UserStatusUpdateRequest,
    admin: SessionUser = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Activate or deactivate a user account with lockout protection for the last admin."""
    target_user = session.get(User, user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado.",
        )

    if payload.is_active is False and target_user.role == UserRole.ADMIN.value:
        active_admins = session.exec(
            select(func.count()).select_from(User).where(
                User.role == UserRole.ADMIN.value,
                User.is_active == True,  # noqa: E712
            )
        ).one()
        if active_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Operação bloqueada: não é permitido desativar o último administrador ativo (prevenção de lockout).",
            )

    target_user.is_active = payload.is_active
    target_user.updated_at = utcnow()
    session.add(target_user)
    session.commit()
    session.refresh(target_user)

    if not payload.is_active:
        user_session_store.terminate_user_sessions(target_user.id)

    return {
        "id": target_user.id,
        "username": target_user.username,
        "role": target_user.role,
        "must_change_password": target_user.must_change_password,
        "is_active": target_user.is_active,
        "created_at": target_user.created_at,
    }


# ==============================================================================
# 3. AI Provider Configuration, Connectivity & Chat Playground Endpoints
# ==============================================================================


@app.get("/api/ai/status", response_model=AIConfigStatus)
def get_ai_status(
    request: Request,
    current_user: SessionUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AIConfigStatus:
    """Return masked AI provider configuration for the authenticated user."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    s_data = user_session_store.get_session(token) if token else None

    if s_data and s_data.ai_api_key:
        return AIConfigStatus(
            configured=True,
            model_name=s_data.ai_model_name,
            key_masked="••••••••",
            provider=s_data.ai_provider,
            resource_name=s_data.ai_resource_name,
            deployment_id=s_data.ai_deployment_id,
            api_version=s_data.ai_api_version,
        )

    db_cfg = session.exec(
        select(UserAIConfig).where(UserAIConfig.user_id == current_user.id)
    ).first()

    if db_cfg:
        return AIConfigStatus(
            configured=True,
            model_name=db_cfg.model_name,
            key_masked="••••••••",
            provider=db_cfg.provider,
            resource_name=db_cfg.resource_name,
            deployment_id=db_cfg.deployment_id,
            api_version=db_cfg.api_version,
        )

    return AIConfigStatus(
        configured=False,
        model_name=None,
        key_masked=None,
        provider="gemini",
    )


@app.post("/api/ai/config", response_model=AIConfigStatus)
def set_ai_config(
    payload: AIConfigRequest,
    request: Request,
    current_user: SessionUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AIConfigStatus:
    """Configure and persist AI credentials encrypted at rest for the current user."""
    token = request.cookies.get(SESSION_COOKIE_NAME)

    if payload.service == "azureopenai" and payload.service_settings:
        provider = "azureopenai"
        resource_name, deployment_id, api_version = ai_aci.normalize_azure_settings(
            payload.service_settings.resource_name,
            payload.service_settings.deployment_id,
            payload.service_settings.api_version,
        )
        api_key = payload.service_settings.api_key
        model_name = deployment_id
    elif payload.provider == "azureopenai":
        provider = "azureopenai"
        resource_name, deployment_id, api_version = ai_aci.normalize_azure_settings(
            payload.resource_name,
            payload.deployment_id,
            payload.api_version or "2024-12-01-preview",
        )
        api_key = payload.api_key
        model_name = deployment_id or "gpt-5.4"
    else:
        provider = "gemini"
        model_name = payload.model_name or "gemini-2.0-flash"
        api_key = payload.api_key
        resource_name = None
        deployment_id = None
        api_version = "2024-06-01"

    if not api_key or len(api_key.strip()) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chave de API inválida.",
        )

    ciphertext, nonce = encrypt_secret(api_key.strip())

    existing_cfg = session.exec(
        select(UserAIConfig).where(UserAIConfig.user_id == current_user.id)
    ).first()

    if existing_cfg:
        existing_cfg.provider = provider
        existing_cfg.model_name = model_name
        existing_cfg.resource_name = resource_name
        existing_cfg.deployment_id = deployment_id
        existing_cfg.api_version = api_version
        existing_cfg.encrypted_api_key = ciphertext
        existing_cfg.nonce = nonce
        existing_cfg.key_masked = "••••••••"
        existing_cfg.updated_at = utcnow()
        session.add(existing_cfg)
    else:
        new_cfg = UserAIConfig(
            user_id=current_user.id,
            provider=provider,
            model_name=model_name,
            resource_name=resource_name,
            deployment_id=deployment_id,
            api_version=api_version,
            encrypted_api_key=ciphertext,
            nonce=nonce,
            key_masked="••••••••",
        )
        session.add(new_cfg)

    session.commit()

    if token:
        user_session_store.set_session_ai_credentials(
            session_token=token,
            api_key=api_key.strip(),
            provider=provider,
            model_name=model_name,
            resource_name=resource_name,
            deployment_id=deployment_id,
            api_version=api_version,
        )

    AISecretStore.get_instance().set_credentials(
        model_name=model_name,
        api_key=api_key.strip(),
        provider=provider,
        resource_name=resource_name,
        deployment_id=deployment_id,
        api_version=api_version,
    )

    return AIConfigStatus(
        configured=True,
        model_name=model_name,
        key_masked="••••••••",
        provider=provider,
        resource_name=resource_name,
        deployment_id=deployment_id,
        api_version=api_version,
    )


@app.post("/api/ai/test-connection", response_model=AITestConnectionResponse)
async def test_ai_connection(
    payload: AIConfigRequest,
    request: Request,
    current_user: SessionUser = Depends(get_current_user),
) -> AITestConnectionResponse:
    """Test connectivity to the selected AI provider using active or supplied credentials."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    s_data = user_session_store.get_session(token) if token else None

    if payload.service == "azureopenai" and payload.service_settings:
        provider = "azureopenai"
        resource_name = payload.service_settings.resource_name
        deployment_id = payload.service_settings.deployment_id
        api_version = payload.service_settings.api_version
        api_key = payload.service_settings.api_key
        model_name = deployment_id
    elif payload.provider == "azureopenai":
        provider = "azureopenai"
        resource_name = payload.resource_name or (s_data.ai_resource_name if s_data else None)
        deployment_id = payload.deployment_id or (s_data.ai_deployment_id if s_data else None)
        api_version = payload.api_version or (s_data.ai_api_version if s_data else "2024-06-01")
        api_key = payload.api_key or (s_data.ai_api_key if s_data else None)
        model_name = deployment_id or "azure-gpt"
    else:
        provider = "gemini"
        model_name = payload.model_name or (s_data.ai_model_name if s_data else "gemini-2.0-flash")
        api_key = payload.api_key or (s_data.ai_api_key if s_data else None)
        resource_name = None
        deployment_id = None
        api_version = "2024-06-01"

    if not api_key:
        api_key = AISecretStore.get_instance().get_api_key()

    result = await check_ai_connectivity(
        model_name=model_name or "gemini-2.0-flash",
        api_key=api_key,
        provider=provider,
        resource_name=resource_name,
        deployment_id=deployment_id,
        api_version=api_version,
    )
    return AITestConnectionResponse(**result)


@app.post("/api/ai/chat-test", response_model=AIChatTestResponse)
async def test_ai_chat(
    payload: AIChatTestRequest,
    request: Request,
    current_user: SessionUser = Depends(get_current_user),
) -> AIChatTestResponse:
    """Execute interactive chat with AI using active session credentials."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    s_data = user_session_store.get_session(token) if token else None

    provider = payload.provider or (s_data.ai_provider if s_data else None) or "gemini"
    model_name = payload.model_name or (s_data.ai_model_name if s_data else None)
    api_key = payload.api_key or (s_data.ai_api_key if s_data else None)
    resource_name = payload.resource_name or (s_data.ai_resource_name if s_data else None)
    deployment_id = payload.deployment_id or (s_data.ai_deployment_id if s_data else None)
    api_version = payload.api_version or (s_data.ai_api_version if s_data else "2024-06-01")

    if not api_key:
        api_key = AISecretStore.get_instance().get_api_key()
    if not model_name:
        model_name = AISecretStore.get_instance().get_model_name() or "gemini-2.0-flash"

    result = await ai_aci.chat_with_ai(
        message=payload.message,
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        resource_name=resource_name,
        deployment_id=deployment_id,
        api_version=api_version,
    )
    return AIChatTestResponse(**result)


# ==============================================================================
# 4. Assessment Lifecycle & RBAC Scoped Endpoints
# ==============================================================================


@app.post("/api/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_run(
    request: Request,
    background_tasks: BackgroundTasks,
    sync: bool = Query(default=False),
    current_user: SessionUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    config: dict[str, Any] = Depends(get_config),
    orchestrator: OrchestratorAgent = Depends(get_orchestrator),
) -> dict[str, Any]:
    """Start a new ASVS assessment run (supports both JSON workspace_path and multipart/form-data zip_upload)."""
    content_type = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in content_type:
        return await create_run_via_upload(
            request=request,
            background_tasks=background_tasks,
            sync=sync,
            current_user=current_user,
            session=session,
            config=config,
            orchestrator=orchestrator,
        )

    try:
        raw_body = await request.body()
        raw_json = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise RequestValidationError(
            [
                {
                    "type": "json_invalid",
                    "loc": ("body",),
                    "msg": "Corpo da requisição não é um JSON válido.",
                    "input": b"",
                }
            ]
        )

    try:
        payload = CreateRunRequest.model_validate(raw_json)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors())

    if not payload.zap_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guardrail DAST acionado: É obrigatório declarar autorização explícita (checkbox zap_authorized) para iniciar qualquer avaliação ASVS.",
        )

    # AI Prerequisite Gate
    token = request.cookies.get(SESSION_COOKIE_NAME)
    s_data = user_session_store.get_session(token) if token else None
    has_ai = bool(s_data and s_data.ai_api_key) or AISecretStore.get_instance().is_configured()
    if not has_ai:
        db_cfg = session.exec(select(UserAIConfig).where(UserAIConfig.user_id == current_user.id)).first()
        if db_cfg:
            has_ai = True
    if not has_ai:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Pré-requisito de IA não atendido: Um provedor de IA generativa deve ser configurado antes de iniciar a avaliação ASVS.",
        )

    try:
        resolved_source = resolve_and_confine_path(payload.workspace_subpath)
    except (PermissionError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    if not resolved_source.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Diretório de código fonte '{payload.workspace_subpath}' não encontrado no workspace.",
        )

    target_url_clean = None
    if payload.target_url:
        ok, err_msg = validate_dast_target(payload.target_url, payload.zap_authorized)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=err_msg,
            )
        target_url_clean = payload.target_url.strip()

    run = Run(
        user_id=current_user.id,
        owner_username=current_user.username,
        source_type="workspace_path",
        source_path=str(resolved_source),
        target_url=target_url_clean,
        zap_authorized=payload.zap_authorized,
        zap_mode=payload.zap_mode,
        status=RunStatus.PENDING.value,
        current_stage=PipelineStage.SCOPER.value,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    orch_input = OrchestratorInput(
        run_id=run.id,
        source_path=str(resolved_source),
        target_url=target_url_clean,
        zap_authorized=payload.zap_authorized,
        zap_mode=payload.zap_mode,
    )
    if sync:
        await orchestrator.execute(orch_input)
        session.refresh(run)
    else:
        background_tasks.add_task(orchestrator.execute, orch_input)

    return {
        "ok": True,
        "run_id": run.id,
        "status": run.status,
        "current_stage": run.current_stage,
        "owner_username": run.owner_username,
        "message": f"Avaliação #{run.id} iniciada com sucesso.",
    }


@app.post("/api/runs/upload", status_code=status.HTTP_202_ACCEPTED)
async def create_run_via_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    sync: bool = Query(default=False),
    current_user: SessionUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    config: dict[str, Any] = Depends(get_config),
    orchestrator: OrchestratorAgent = Depends(get_orchestrator),
) -> dict[str, Any]:
    """Upload a ZIP archive and start assessment bound to current user."""
    form = await request.form(max_part_size=300 * 1024 * 1024)
    zip_file = form.get("source_zip") or form.get("zip_file")
    if not zip_file or not hasattr(zip_file, "read"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo ZIP ausente no campo multipart 'source_zip' ou 'zip_file'.",
        )

    target_url = form.get("target_url")
    zap_authorized = str(form.get("zap_authorized", "")).lower() in ("true", "1", "on")
    zap_mode = str(form.get("zap_mode", "active"))

    if not zap_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guardrail DAST acionado: É obrigatório declarar autorização explícita (checkbox zap_authorized) para iniciar qualquer avaliação ASVS.",
        )

    # AI Prerequisite Gate
    token = request.cookies.get(SESSION_COOKIE_NAME)
    s_data = user_session_store.get_session(token) if token else None
    has_ai = bool(s_data and s_data.ai_api_key) or AISecretStore.get_instance().is_configured()
    if not has_ai:
        db_cfg = session.exec(select(UserAIConfig).where(UserAIConfig.user_id == current_user.id)).first()
        if db_cfg:
            has_ai = True
    if not has_ai:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Pré-requisito de IA não atendido: Um provedor de IA generativa deve ser configurado antes de iniciar a avaliação ASVS.",
        )

    target_url_clean = None
    if target_url:
        ok, err_msg = validate_dast_target(str(target_url), zap_authorized)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=err_msg,
            )
        target_url_clean = str(target_url).strip()

    upload_id = str(uuid.uuid4())[:8]

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_fh:
        content = await zip_file.read()
        tmp_fh.write(content)
        tmp_zip_path = Path(tmp_fh.name)

    try:
        extracted_dir = extract_safe_zip(tmp_zip_path, upload_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    finally:
        if tmp_zip_path.exists():
            tmp_zip_path.unlink()

    run = Run(
        user_id=current_user.id,
        owner_username=current_user.username,
        source_type="zip_upload",
        source_path=str(extracted_dir),
        target_url=target_url_clean,
        zap_authorized=zap_authorized,
        zap_mode=zap_mode,
        status=RunStatus.PENDING.value,
        current_stage=PipelineStage.SCOPER.value,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    orch_input = OrchestratorInput(
        run_id=run.id,
        source_path=str(extracted_dir),
        target_url=target_url_clean,
        zap_authorized=zap_authorized,
        zap_mode=zap_mode,
    )
    if sync:
        await orchestrator.execute(orch_input)
        session.refresh(run)
    else:
        background_tasks.add_task(orchestrator.execute, orch_input)

    return {
        "ok": True,
        "run_id": run.id,
        "status": run.status,
        "current_stage": run.current_stage,
        "owner_username": run.owner_username,
        "message": f"Avaliação #{run.id} criada via upload ZIP com sucesso.",
    }


@app.get("/api/runs")
def list_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    current_user: SessionUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """List runs: Admin sees all; regular user sees strictly their own runs."""
    base_query = select(Run).order_by(Run.id.desc())
    if current_user.role != UserRole.ADMIN.value:
        base_query = base_query.where(Run.user_id == current_user.id)

    runs = list(session.exec(base_query).all())
    items, _, _, total_pages, has_next = paginate_items(runs, page, page_size)
    total = len(runs)

    return {
        "items": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "owner_username": r.owner_username,
                "source_type": r.source_type,
                "source_path": r.source_path,
                "target_url": r.target_url,
                "zap_authorized": r.zap_authorized,
                "status": r.status,
                "current_stage": r.current_stage,
                "pass_percentage": r.pass_percentage,
                "pass_count": r.pass_count,
                "fail_count": r.fail_count,
                "inconclusive_count": r.inconclusive_count,
                "manual_count": r.manual_count,
                "is_selective": getattr(r, "is_selective", False),
                "selected_req_ids": json.loads(r.selected_req_ids_json) if getattr(r, "selected_req_ids_json", None) else None,
                "inherited_from_run_id": getattr(r, "inherited_from_run_id", None),
                "created_at": r.created_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in items
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_next": has_next,
    }


@app.get("/api/runs/compare")
def compare_runs(
    base_run_id: int = Query(...),
    target_run_id: int = Query(...),
    current_user: SessionUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Compare verdicts and findings between two runs (both must be accessible to user)."""
    run_a = verify_run_access(base_run_id, current_user, session)
    run_b = verify_run_access(target_run_id, current_user, session)

    verdicts_a = {v.req_id: v for v in session.exec(select(Verdict).where(Verdict.run_id == run_a.id)).all()}
    verdicts_b = {v.req_id: v for v in session.exec(select(Verdict).where(Verdict.run_id == run_b.id)).all()}

    comparisons = []
    for req_id in IN_SCOPE_REQ_IDS:
        va = verdicts_a.get(req_id)
        vb = verdicts_b.get(req_id)
        comparisons.append({
            "req_id": req_id,
            "base_status": va.status if va else "INCONCLUSIVE",
            "target_status": vb.status if vb else "INCONCLUSIVE",
            "changed": (va.status if va else None) != (vb.status if vb else None),
        })

    deltas = {
        "pass_percentage": round((run_b.pass_percentage or 0.0) - (run_a.pass_percentage or 0.0), 2),
        "pass_count": (run_b.pass_count or 0) - (run_a.pass_count or 0),
        "fail_count": (run_b.fail_count or 0) - (run_a.fail_count or 0),
        "inconclusive_count": (run_b.inconclusive_count or 0) - (run_a.inconclusive_count or 0),
        "manual_count": (run_b.manual_count or 0) - (run_a.manual_count or 0),
    }

    return {
        "base_run_id": base_run_id,
        "target_run_id": target_run_id,
        "comparisons": comparisons,
        "deltas": deltas,
        "requirement_transitions": comparisons,
    }


@app.get("/api/runs/{run_id}")
def get_run_details(
    run_id: int,
    current_user: SessionUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve execution details for a specific run (RBAC protected)."""
    run = verify_run_access(run_id, current_user, session)
    findings = list(session.exec(select(Finding).where(Finding.run_id == run.id)).all())
    verdicts = list_run_verdicts(run_id, current_user, session)
    return {
        "id": run.id,
        "user_id": run.user_id,
        "owner_username": run.owner_username,
        "source_type": run.source_type,
        "source_path": run.source_path,
        "target_url": run.target_url,
        "zap_authorized": run.zap_authorized,
        "status": run.status,
        "current_stage": run.current_stage,
        "pass_percentage": run.pass_percentage,
        "pass_count": run.pass_count,
        "fail_count": run.fail_count,
        "inconclusive_count": run.inconclusive_count,
        "manual_count": run.manual_count,
        "scope_summary": json.loads(run.scope_summary_json or "{}"),
        "error_message": run.error_message,
        "is_selective": getattr(run, "is_selective", False),
        "selected_req_ids": json.loads(run.selected_req_ids_json) if getattr(run, "selected_req_ids_json", None) else None,
        "inherited_from_run_id": getattr(run, "inherited_from_run_id", None),
        "created_at": run.created_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "metrics": {
            "total_in_scope": len(IN_SCOPE_REQ_IDS),
            "pass_percentage": run.pass_percentage,
            "pass_count": run.pass_count,
            "fail_count": run.fail_count,
            "inconclusive_count": run.inconclusive_count,
            "manual_count": run.manual_count,
        },
        "verdicts": verdicts,
        "findings": [
            {
                "id": f.id,
                "run_id": f.run_id,
                "req_id": f.req_id,
                "tool": f.tool,
                "rule_or_plugin_id": f.rule_or_plugin_id,
                "title": f.title,
                "severity": f.severity,
                "confidence": f.confidence,
                "primary_location": f.primary_location,
                "is_false_positive": f.is_false_positive,
                "fp_reason": f.fp_reason,
                "is_inherited": getattr(f, "is_inherited", False),
                "inherited_from_run_id": getattr(f, "inherited_from_run_id", None),
                "created_at": f.created_at.isoformat(),
            }
            for f in findings
        ],
    }


@app.get("/api/runs/{run_id}/events")
async def stream_run_events(
    run_id: int,
    request: Request,
    current_user: SessionUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> EventSourceResponse:
    """Stream real-time Server-Sent Events (SSE) for a run (RBAC protected)."""
    run_row = verify_run_access(run_id, current_user, session)
    q = event_broker.subscribe(run_id)

    async def event_generator() -> AsyncGenerator[dict[str, Any], None]:
        try:
            if q.empty() and run_row.status in (
                RunStatus.COMPLETED.value,
                RunStatus.FAILED.value,
                RunStatus.CANCELLED.value,
            ):
                yield {
                    "event": "pipeline_update",
                    "data": json.dumps(
                        {
                            "run_id": run_id,
                            "status": run_row.status,
                            "stage": run_row.current_stage,
                            "stage_status": "COMPLETED",
                            "progress_percent": 100,
                            "message": f"Execução #{run_id} já finalizada ({run_row.status}).",
                            "timestamp": utcnow().isoformat(),
                        },
                        default=str,
                    ),
                }
                return

            while True:
                if await request.is_disconnected():
                    break
                try:
                    event_data = await asyncio.wait_for(q.get(), timeout=1.0)
                    yield {
                        "event": "pipeline_update",
                        "data": json.dumps(event_data, default=str),
                    }
                    if event_data.get("status") in (
                        RunStatus.COMPLETED.value,
                        RunStatus.FAILED.value,
                        RunStatus.CANCELLED.value,
                    ):
                        break
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": ""}
        finally:
            event_broker.unsubscribe(run_id, q)

    return EventSourceResponse(event_generator())


@app.get("/api/runs/{run_id}/findings")
def list_run_findings(
    run_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    req_id: str | None = None,
    tool: str | None = None,
    include_false_positives: bool = True,
    current_user: SessionUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """List normalized security findings for a run (RBAC protected)."""
    verify_run_access(run_id, current_user, session)

    query = select(Finding).where(Finding.run_id == run_id)
    if req_id:
        query = query.where(Finding.req_id == req_id)
    if tool:
        query = query.where(Finding.tool == tool)
    if not include_false_positives:
        query = query.where(Finding.is_false_positive == False)  # noqa: E712

    findings = list(session.exec(query.order_id if hasattr(query, "order_id") else query).all())
    items, _, _, total_pages, has_next = paginate_items(findings, page, page_size)
    total = len(findings)

    return {
        "items": [
            {
                "id": f.id,
                "run_id": f.run_id,
                "req_id": f.req_id,
                "tool": f.tool,
                "rule_or_plugin_id": f.rule_or_plugin_id,
                "title": f.title,
                "severity": f.severity,
                "confidence": f.confidence,
                "primary_location": f.primary_location,
                "is_false_positive": f.is_false_positive,
                "fp_reason": f.fp_reason,
                "created_at": f.created_at.isoformat(),
            }
            for f in items
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_next": has_next,
    }


@app.get("/api/runs/{run_id}/verdicts")
def list_run_verdicts(
    run_id: int,
    current_user: SessionUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """List the 8 requirement verdicts for a run (RBAC protected)."""
    verify_run_access(run_id, current_user, session)

    verdicts = list(
        session.exec(
            select(Verdict).where(Verdict.run_id == run_id).order_by(Verdict.req_id)
        ).all()
    )
    # Feature 017: presentation fields consumed by the "Resultado por Verificação" table.
    req_ids = [v.req_id for v in verdicts]
    reqs_map = {
        r.req_id: r
        for r in session.exec(select(Requirement).where(Requirement.req_id.in_(req_ids))).all()
    } if req_ids else {}
    mapping_cfg = load_req_tool_mapping().get("requirements", {})

    def _present(req_id: str) -> dict[str, Any]:
        meta = reqs_map.get(req_id)
        cfg = mapping_cfg.get(req_id, {})
        section_name = meta.section_name if meta else cfg.get("section_name", "")
        return {
            "section_id": meta.section_id if meta else cfg.get("section_id", ""),
            "section_name": section_name,
            "req_description": meta.req_description if meta else "",
            "friendly_title": cfg.get("friendly_title") or section_name,
            "description_pt": cfg.get("description_pt", ""),
        }

    return [
        {
            "id": v.id,
            "req_id": v.req_id,
            **_present(v.req_id),
            "status": v.status,
            "confidence_level": v.confidence_level,
            "tools_used": json.loads(v.tools_used_json or "[]"),
            "rules_executed": json.loads(v.rules_executed_json or "[]"),
            "coverage_declared": v.coverage_declared,
            "positive_evidence": json.loads(v.positive_evidence_json or "[]"),
            "active_findings_count": v.active_findings_count,
            "rationale": v.rationale,
            "limitations": v.limitations,
            "is_inherited": getattr(v, "is_inherited", False),
            "inherited_from_run_id": getattr(v, "inherited_from_run_id", None),
            "updated_at": v.updated_at.isoformat(),
        }
        for v in verdicts
    ]


@app.get("/api/runs/{run_id}/export")
def export_run_report(
    run_id: int,
    format: str = Query(default="html", pattern="^(html|json)$"),
    current_user: SessionUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    """Export the evaluation report in HTML or JSON format (RBAC protected)."""
    verify_run_access(run_id, current_user, session)

    report_dict = build_full_report_dict(session, run_id)
    if format == "json":
        return JSONResponse(content=report_dict)

    html_content = render_static_html_report(report_dict)
    return Response(
        content=html_content,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=asvs-report-run-{run_id}.html"},
    )


@app.post("/api/runs/{run_id}/cancel")
def cancel_run(
    run_id: int,
    current_user: SessionUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Cancel a running assessment run (RBAC protected)."""
    run = verify_run_access(run_id, current_user, session)
    if run.status != RunStatus.RUNNING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível cancelar uma execução em estado '{run.status}'.",
        )

    run.status = RunStatus.CANCELLED.value
    run.finished_at = utcnow()
    session.add(run)
    session.commit()
    return {"ok": True, "message": f"Avaliação #{run_id} cancelada com sucesso."}


@app.post("/api/runs/{run_id}/rerun", status_code=status.HTTP_202_ACCEPTED)
async def rerun_run(
    run_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    payload: Any = Body(default=None),
    sync: bool = Query(default=False),
    current_user: SessionUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    orchestrator: OrchestratorAgent = Depends(get_orchestrator),
) -> dict[str, Any]:
    """Rerun an existing assessment using original parameters (RBAC protected)."""
    orig_run = verify_run_access(run_id, current_user, session)

    # AI Prerequisite Gate
    token = request.cookies.get(SESSION_COOKIE_NAME)
    s_data = user_session_store.get_session(token) if token else None
    has_ai = bool(s_data and s_data.ai_api_key) or AISecretStore.get_instance().is_configured()
    if not has_ai:
        db_cfg = session.exec(select(UserAIConfig).where(UserAIConfig.user_id == current_user.id)).first()
        if db_cfg:
            has_ai = True
    if not has_ai:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Pré-requisito de IA não atendido: Um provedor de IA generativa deve ser configurado antes de iniciar a avaliação ASVS.",
        )

    if orig_run.status in (RunStatus.RUNNING.value, RunStatus.PENDING.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível reexecutar uma avaliação em andamento ou pendente (status: '{orig_run.status}'). A avaliação deve estar concluída ou finalizada.",
        )

    selected_req_ids: list[str] | None = None
    is_selective = False
    if payload is not None:
        try:
            req_model = SelectiveRerunRequest.model_validate(payload)
            if req_model.req_ids:
                selected_req_ids = req_model.req_ids
                is_selective = True
        except (ValidationError, ValueError) as err:
            detail_msg = str(err)
            if hasattr(err, "errors"):
                detail_msg = "; ".join(e.get("msg", str(e)) for e in err.errors())
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Parâmetros de reexecução seletiva inválidos: {detail_msg}",
            )

    new_run = Run(
        user_id=current_user.id,
        owner_username=current_user.username,
        source_type=orig_run.source_type,
        source_path=orig_run.source_path,
        target_url=orig_run.target_url,
        zap_authorized=orig_run.zap_authorized,
        zap_mode=orig_run.zap_mode,
        status=RunStatus.PENDING.value,
        current_stage=PipelineStage.SCOPER.value,
        is_selective=is_selective,
        selected_req_ids_json=json.dumps(selected_req_ids) if selected_req_ids else None,
        inherited_from_run_id=orig_run.id if is_selective else None,
    )
    session.add(new_run)
    session.commit()
    session.refresh(new_run)

    orch_input = OrchestratorInput(
        run_id=new_run.id,
        previous_run_id=orig_run.id,
        selective_req_ids=selected_req_ids,
        source_path=new_run.source_path,
        target_url=new_run.target_url,
        zap_authorized=new_run.zap_authorized,
        zap_mode=new_run.zap_mode,
    )
    if sync:
        await orchestrator.execute(orch_input)
        session.refresh(new_run)
    else:
        background_tasks.add_task(orchestrator.execute, orch_input)

    return {
        "ok": True,
        "run_id": new_run.id,
        "status": new_run.status,
        "is_selective": is_selective,
        "selected_req_ids": selected_req_ids,
        "inherited_from_run_id": orig_run.id if is_selective else None,
        "message": (
            f"Reexecução seletiva #{new_run.id} iniciada para {len(selected_req_ids)} requisitos."
            if is_selective
            else f"Nova avaliação #{new_run.id} iniciada baseada na execução #{run_id}."
        ),
    }




# ==============================================================================
# 5. False Positive Triage & Evidence Retrieval (RBAC Protected)
# ==============================================================================


@app.patch("/api/findings/{finding_id}/triage")
def triage_finding(
    finding_id: int,
    payload: TriageUpdateRequest,
    current_user: SessionUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Mark/unmark finding as false positive; record immutable actor from session (RBAC protected)."""
    finding = session.get(Finding, finding_id)
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Achado #{finding_id} não encontrado.",
        )

    verify_run_access(finding.run_id, current_user, session)

    prev_val = finding.is_false_positive
    finding.is_false_positive = payload.is_false_positive
    finding.fp_reason = payload.justification if payload.is_false_positive else None
    session.add(finding)

    actor = current_user.username
    audit_entry = AuditLog(
        run_id=finding.run_id,
        finding_id=finding.id,
        req_id=finding.req_id,
        action="MARK_FP" if payload.is_false_positive else "UNMARK_FP",
        previous_value=prev_val,
        new_value=payload.is_false_positive,
        justification=payload.justification,
        actor=actor,
        user_id=current_user.id,
    )
    session.add(audit_entry)

    recalculate_single_requirement_verdict(session, finding.run_id, finding.req_id)
    session.commit()

    verdict = session.exec(
        select(Verdict).where(
            Verdict.run_id == finding.run_id,
            Verdict.req_id == finding.req_id,
        )
    ).first()

    return {
        "ok": True,
        "finding_id": finding.id,
        "is_false_positive": finding.is_false_positive,
        "fp_reason": finding.fp_reason,
        "actor": actor,
        "updated_verdict": {
            "status": verdict.status if verdict else "INCONCLUSIVE",
            "active_findings_count": verdict.active_findings_count if verdict else 0,
        },
        "message": "Triagem de falso positivo registrada com sucesso.",
    }


@app.get("/api/findings/{finding_id}/evidence")
def get_finding_evidence(
    finding_id: int,
    current_user: SessionUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve attached evidence snippets or HTTP exchanges (RBAC protected)."""
    finding = session.get(Finding, finding_id)
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Achado #{finding_id} não encontrado.",
        )

    verify_run_access(finding.run_id, current_user, session)

    evidences = list(
        session.exec(select(Evidence).where(Evidence.finding_id == finding_id)).all()
    )
    items = [
        {
            "id": e.id,
            "evidence_type": e.evidence_type,
            "file_path": e.file_path,
            "line_start": e.line_start,
            "line_end": e.line_end,
            "code_snippet": e.code_snippet,
            "http_method": e.http_method,
            "http_url": e.http_url,
            "http_request": e.http_request,
            "http_response": e.http_response,
        }
        for e in evidences
    ]
    return {
        "finding_id": finding_id,
        "total": len(items),
        "evidences": items,
    }
