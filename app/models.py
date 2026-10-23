"""SQLModel entities and Pydantic contracts for ASVS-Self-Assesment-Tool."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field as PydanticField, field_validator
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class VerdictStatus(str, Enum):
    """Normative verdict states per Constitution Principle II."""

    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    MANUAL_REQUIRED = "MANUAL_REQUIRED"


class RunStatus(str, Enum):
    """Lifecycle states of an assessment run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PipelineStage(str, Enum):
    """Stages of the multi-agent assessment pipeline."""

    INIT = "INIT"
    SCOPER = "SCOPER"
    SAST = "SAST"
    DAST = "DAST"
    AI_EVALUATION = "AI_EVALUATION"
    TRIAGE = "TRIAGE"
    VERDICT = "VERDICT"
    REPORT = "REPORT"
    DONE = "DONE"


class UserRole(str, Enum):
    """Role-Based Access Control roles."""

    ADMIN = "admin"
    USER = "user"


class Requirement(SQLModel, table=True):
    """OWASP ASVS 5.0 requirement catalog entry (345 rows, V1-V17)."""

    req_id: str = Field(primary_key=True, index=True)
    chapter_id: str = Field(index=True, nullable=False)
    chapter_name: str = Field(nullable=False)
    section_id: str = Field(index=True, nullable=False)
    section_name: str = Field(nullable=False)
    req_description: str = Field(nullable=False)
    level: int = Field(index=True, nullable=False)
    in_scope: bool = Field(default=False, index=True, nullable=False)


class User(SQLModel, table=True):
    """Local user account for ASVS tool."""

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, nullable=False, max_length=50)
    password_hash: str = Field(nullable=False)
    role: str = Field(default=UserRole.USER.value, index=True, nullable=False)
    must_change_password: bool = Field(default=False, nullable=False)
    is_active: bool = Field(default=True, index=True, nullable=False)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)


class UserAIConfig(SQLModel, table=True):
    """Encrypted-at-rest AI credentials and settings per user."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True, nullable=False)
    provider: str = Field(default="gemini", nullable=False)
    model_name: str = Field(default="gemini-2.0-flash", nullable=False)
    resource_name: str | None = Field(default=None, nullable=True)
    deployment_id: str | None = Field(default=None, nullable=True)
    api_version: str = Field(default="2024-06-01", nullable=False)
    encrypted_api_key: bytes = Field(nullable=False)
    nonce: bytes = Field(nullable=False)
    key_masked: str = Field(default="••••••••", nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)


class Run(SQLModel, table=True):
    """Execution record of the multi-agent ASVS V1 L1 pipeline."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(default=1, foreign_key="user.id", index=True, nullable=False)
    owner_username: str = Field(default="admin", index=True, nullable=False)
    source_type: str = Field(default="workspace_path", nullable=False)
    source_path: str = Field(nullable=False)
    target_url: str | None = Field(default=None, nullable=True)
    zap_authorized: bool = Field(default=False, nullable=False)
    zap_mode: str = Field(default="baseline", nullable=False)
    status: str = Field(default=RunStatus.PENDING.value, index=True, nullable=False)
    current_stage: str = Field(default=PipelineStage.INIT.value, nullable=False)
    pass_percentage: float = Field(default=0.0, nullable=False)
    pass_count: int = Field(default=0, nullable=False)
    fail_count: int = Field(default=0, nullable=False)
    inconclusive_count: int = Field(default=0, nullable=False)
    manual_count: int = Field(default=0, nullable=False)
    scope_summary_json: str = Field(default="{}", nullable=False)
    error_message: str | None = Field(default=None, nullable=True)
    is_selective: bool = Field(default=False, nullable=False, index=True)
    selected_req_ids_json: str | None = Field(default=None, nullable=True)
    inherited_from_run_id: int | None = Field(default=None, foreign_key="run.id", index=True, nullable=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    finished_at: datetime | None = Field(default=None, nullable=True)


class ToolCall(SQLModel, table=True):
    """Observability log for every Agent-Computer Interface (ACI) invocation."""

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True, nullable=False)
    agent_name: str = Field(index=True, nullable=False)
    aci_name: str = Field(nullable=False)
    command: str = Field(nullable=False)
    args_json: str = Field(default="{}", nullable=False)
    status: str = Field(default="SUCCESS", nullable=False)
    duration_ms: int = Field(default=0, nullable=False)
    output_summary: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)


class Finding(SQLModel, table=True):
    """Normalized and deduplicated security finding from Semgrep (SAST) or ZAP (DAST)."""

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True, nullable=False)
    req_id: str = Field(foreign_key="requirement.req_id", index=True, nullable=False)
    tool: str = Field(index=True, nullable=False)
    rule_or_plugin_id: str = Field(nullable=False)
    title: str = Field(nullable=False)
    severity: str = Field(default="MEDIUM", nullable=False)
    confidence: str = Field(default="MEDIUM", nullable=False)
    fingerprint: str = Field(index=True, nullable=False)
    primary_location: str = Field(nullable=False)
    is_false_positive: bool = Field(default=False, index=True, nullable=False)
    fp_reason: str | None = Field(default=None, nullable=True)
    is_inherited: bool = Field(default=False, nullable=False, index=True)
    inherited_from_run_id: int | None = Field(default=None, foreign_key="run.id", index=True, nullable=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)


class Evidence(SQLModel, table=True):
    """Navigable code snippet or HTTP exchange evidence attached to a Finding."""

    id: int | None = Field(default=None, primary_key=True)
    finding_id: int = Field(foreign_key="finding.id", index=True, nullable=False)
    evidence_type: str = Field(nullable=False)
    file_path: str | None = Field(default=None, nullable=True)
    line_start: int | None = Field(default=None, nullable=True)
    line_end: int | None = Field(default=None, nullable=True)
    code_snippet: str | None = Field(default=None, nullable=True)
    http_method: str | None = Field(default=None, nullable=True)
    http_url: str | None = Field(default=None, nullable=True)
    http_request: str | None = Field(default=None, nullable=True)
    http_response: str | None = Field(default=None, nullable=True)


class Verdict(SQLModel, table=True):
    """Consolidated requirement verdict for one of the 8 ASVS V1 L1 requirements."""

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True, nullable=False)
    req_id: str = Field(foreign_key="requirement.req_id", index=True, nullable=False)
    status: str = Field(index=True, nullable=False)
    confidence_level: str = Field(default="MEDIUM", nullable=False)
    tools_used_json: str = Field(default="[]", nullable=False)
    rules_executed_json: str = Field(default="[]", nullable=False)
    coverage_declared: str = Field(nullable=False)
    positive_evidence_json: str = Field(default="[]", nullable=False)
    active_findings_count: int = Field(default=0, nullable=False)
    rationale: str = Field(nullable=False)
    limitations: str = Field(nullable=False)
    is_inherited: bool = Field(default=False, nullable=False, index=True)
    inherited_from_run_id: int | None = Field(default=None, foreign_key="run.id", index=True, nullable=True)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)


class AuditLog(SQLModel, table=True):
    """Immutable audit log entry for manual false-positive triage operations."""

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True, nullable=False)
    finding_id: int = Field(foreign_key="finding.id", index=True, nullable=False)
    req_id: str = Field(index=True, nullable=False)
    action: str = Field(nullable=False)
    previous_value: bool = Field(nullable=False)
    new_value: bool = Field(nullable=False)
    justification: str = Field(nullable=False)
    actor: str = Field(default="local_evaluator", nullable=False)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True, nullable=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)


# ---------------------------------------------------------------------------
# Authentication & RBAC Schemas (Feature 007)
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    """Payload for POST /api/auth/login."""

    username: str = PydanticField(..., min_length=1, max_length=50)
    password: str = PydanticField(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    """Response for POST /api/auth/login."""

    ok: bool = True
    user_id: int
    username: str
    role: str
    must_change_password: bool
    ai_configured: bool = False
    ai_model_name: str | None = None


class UserCreateRequest(BaseModel):
    """Payload for POST /api/users (Admin only)."""

    username: str = PydanticField(..., min_length=3, max_length=50)
    password: str = PydanticField(..., min_length=8, max_length=128)
    role: Literal["admin", "user"] = "user"


class UserResponse(BaseModel):
    """Safe user projection omitting sensitive credential hashes."""

    id: int
    username: str
    role: str
    must_change_password: bool
    is_active: bool
    created_at: datetime


class UserStatusUpdateRequest(BaseModel):
    """Payload for PATCH /api/users/{id}/status."""

    is_active: bool


class ChangePasswordRequest(BaseModel):
    """Payload for POST /api/auth/change-password."""

    current_password: str
    new_password: str = PydanticField(..., min_length=8, max_length=128)


class SessionUser(BaseModel):
    """Authenticated user identity injected into request context."""

    id: int
    username: str
    role: str
    must_change_password: bool = False
    is_active: bool = True


# ---------------------------------------------------------------------------
# Generic ACI Response Contract & API Request/Response Schemas
# ---------------------------------------------------------------------------

T = TypeVar("T")

MAX_ACI_PAGE_SIZE = 50


class ACIResponse(BaseModel, Generic[T]):
    """Standardized, compact Agent-Computer Interface response envelope."""

    ok: bool = True
    aci: Literal["workspace_aci", "semgrep_aci", "zap_aci", "ai_aci"]
    command: str
    summary_message: str = PydanticField(..., min_length=1)
    page: int = 1
    page_size: int = MAX_ACI_PAGE_SIZE
    total_items: int = 0
    total_pages: int = 1
    has_next: bool = False
    data: Any = None
    corrective_hint: str | None = None

    @field_validator("page_size")
    @classmethod
    def enforce_max_page_size(cls, v: int) -> int:
        if v < 1 or v > MAX_ACI_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_ACI_PAGE_SIZE}")
        return v


class CreateRunRequest(BaseModel):
    """Payload to start a new assessment run via JSON."""

    source_type: Literal["workspace_path", "zip_upload"] = "workspace_path"
    workspace_subpath: str = "tests/vulnerable_app"
    target_url: str | None = None
    zap_authorized: bool = False
    zap_mode: Literal["baseline", "active"] = "active"


class SelectiveRerunRequest(BaseModel):
    """Payload opcional para POST /api/runs/{run_id}/rerun com filtros de requisitos."""

    req_ids: list[str] | None = PydanticField(
        default=None,
        description="Lista de IDs normativos ASVS V1 L1 para reexecução seletiva. Se omitido ou null, reexecuta todos os 8 requisitos.",
    )

    @field_validator("req_ids")
    @classmethod
    def validate_selective_requirements(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        if not v or len(v) == 0:
            raise ValueError(
                "A lista de requisitos para reexecução seletiva não pode ser vazia. "
                "Para reexecução total, omita o campo req_ids ou passe null."
            )

        cleaned: list[str] = []
        for r in v:
            item = str(r).strip()
            if item and item not in cleaned:
                cleaned.append(item)

        if not cleaned:
            raise ValueError("A lista de requisitos não contém identificadores válidos.")

        from app.database import IN_SCOPE_REQ_IDS

        invalid = [r for r in cleaned if r not in IN_SCOPE_REQ_IDS]
        if invalid:
            raise ValueError(
                f"Requisitos inválidos ou fora do escopo normativo ASVS 5.0 V1 L1: {', '.join(invalid)}. "
                f"Requisitos permitidos: {', '.join(sorted(IN_SCOPE_REQ_IDS))}."
            )
        return cleaned


class TriageUpdateRequest(BaseModel):
    """Payload to mark or unmark a finding as false positive."""

    is_false_positive: bool
    justification: str = PydanticField(..., min_length=5, max_length=1000)
    actor: str = "local_evaluator"

    @field_validator("justification")
    @classmethod
    def validate_non_blank_justification(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 5:
            raise ValueError(
                "A justificativa de falso positivo é obrigatória e deve ter ao menos 5 caracteres."
            )
        return cleaned


class AIConfigStatus(BaseModel):
    """Masked status of AI provider configuration."""

    configured: bool
    model_name: str | None = None
    key_masked: str | None = None
    provider: str = "gemini"
    resource_name: str | None = None
    deployment_id: str | None = None
    api_version: str = "2024-06-01"


class AzureServiceSettings(BaseModel):
    """Service settings for Azure OpenAI inference payload."""

    resource_name: str = PydanticField(..., min_length=1)
    deployment_id: str = PydanticField(..., min_length=1)
    api_version: str = "2024-06-01"
    api_key: str = PydanticField(..., min_length=4)


class AIConfigRequest(BaseModel):
    """Payload to configure AI model in volatile memory."""

    model_name: str | None = None
    api_key: str | None = None
    provider: str | None = None
    resource_name: str | None = None
    deployment_id: str | None = None
    api_version: str = "2024-06-01"

    service: str | None = None
    service_settings: AzureServiceSettings | None = None


class AITestConnectionResponse(BaseModel):
    """Response of AI provider connectivity test."""

    ok: bool
    model_name: str
    latency_ms: int
    message: str


class AIChatTestRequest(BaseModel):
    """Request payload for AI Chat Playground."""

    message: str = PydanticField(..., min_length=1, max_length=2000)
    provider: str | None = None
    model_name: str | None = None
    api_key: str | None = None
    resource_name: str | None = None
    deployment_id: str | None = None
    api_version: str = "2024-06-01"


class AIChatTestResponse(BaseModel):
    """Response payload for AI Chat Playground."""

    ok: bool
    response_text: str
    latency_ms: int
    model_used: str
    provider: str


class AIEvaluatorInput(BaseModel):
    """Input payload for AIEvaluatorAgent."""

    run_id: int
    req_id: str = "V1.3.1"
    source_path: str


class AIEvaluatorOutput(BaseModel):
    """Output payload produced by AIEvaluatorAgent."""

    run_id: int
    req_id: str
    verdict: Literal["PASS", "FAIL", "INCONCLUSIVE", "MANUAL_REQUIRED"]
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    rationale: str
    model_used: str | None = None
    evidence_snippets: list[str] = PydanticField(default_factory=list)
