# Data Model: Feature 007 (Autenticação, RBAC e Criptografia em Repouso de IA)

**Feature**: `007-auth-rbac-and-encrypted-user-ai-config`  
**Data**: 2026-10-15  
**Status**: Concluído (Modelagem Formal)

---

## 1. Entidades SQLModel

### 1.1. `User` (Contas de Acesso Local)

```python
from enum import Enum
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"

class User(SQLModel, table=True):
    """Conta de usuário local da ferramenta ASVS."""
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, nullable=False, max_length=50)
    password_hash: str = Field(nullable=False)  # Formato: pbkdf2:sha256:600000:<salt_hex>:<hash_hex>
    role: str = Field(default=UserRole.USER.value, index=True, nullable=False)
    must_change_password: bool = Field(default=False, nullable=False)
    is_active: bool = Field(default=True, index=True, nullable=False)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)
```

---

### 1.2. `UserAIConfig` (Credenciais de IA Criptografadas em Repouso)

```python
class UserAIConfig(SQLModel, table=True):
    """Configurações e credenciais de IA criptografadas em repouso por usuário."""
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True, nullable=False)
    provider: str = Field(default="gemini", nullable=False)  # 'azureopenai' ou 'gemini'
    model_name: str = Field(default="gemini-3.8-flash", nullable=False)
    resource_name: str | None = Field(default=None, nullable=True)
    deployment_id: str | None = Field(default=None, nullable=True)
    api_version: str = Field(default="2024-06-01", nullable=False)
    
    # Criptografia simétrica autenticada AES-256-GCM
    encrypted_api_key: bytes = Field(nullable=False)  # Ciphertext + Tag (16 bytes)
    nonce: bytes = Field(nullable=False)              # 12 bytes aleatórios
    key_masked: str = Field(default="••••••••", nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)
```

---

### 1.3. Enriquecimento de `Run` (Segregação de Posse Multi-Usuário)

```python
class Run(SQLModel, table=True):
    """Execution record of the multi-agent ASVS V1 L1 pipeline (enriquecido com posse)."""
    id: int | None = Field(default=None, primary_key=True)
    
    # Novos campos de auditoria e controle de acesso
    user_id: int = Field(default=1, foreign_key="user.id", index=True, nullable=False)
    owner_username: str = Field(default="admin", index=True, nullable=False)
    
    # Campos existentes mantidos intactos
    source_type: str = Field(default="workspace_path", nullable=False)
    source_path: str = Field(nullable=False)
    target_url: str | None = Field(default=None, nullable=True)
    zap_authorized: bool = Field(default=False, nullable=False)
    zap_mode: str = Field(default="baseline", nullable=False)
    status: str = Field(default="PENDING", index=True, nullable=False)
    current_stage: str = Field(default="INIT", nullable=False)
    pass_percentage: float = Field(default=0.0, nullable=False)
    pass_count: int = Field(default=0, nullable=False)
    fail_count: int = Field(default=0, nullable=False)
    inconclusive_count: int = Field(default=0, nullable=False)
    manual_count: int = Field(default=0, nullable=False)
    scope_summary_json: str = Field(default="{}", nullable=False)
    error_message: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    finished_at: datetime | None = Field(default=None, nullable=True)
```

---

## 2. Modelagem de Sessão em Memória (`UserSessionStore`)

```python
from dataclasses import dataclass

@dataclass
class ActiveSession:
    token: str
    user_id: int
    username: str
    role: str
    must_change_password: bool
    created_at: float
    last_active: float
    # Segredo decifrado mantido unicamente em memória para a sessão ativa
    decrypted_api_key: str | None = None
    ai_provider: str | None = None
    ai_model_name: str | None = None
    ai_resource_name: str | None = None
    ai_deployment_id: str | None = None
    ai_api_version: str = "2024-06-01"
```

---

## 3. Matriz de Autorização RBAC

| Recurso / Ação | Endpoint | Perfil `admin` | Perfil `user` |
| :--- | :--- | :---: | :---: |
| Autenticar | `POST /api/auth/login` | Permitido | Permitido |
| Encerrar Sessão | `POST /api/auth/logout` | Permitido | Permitido |
| Consultar Perfil | `GET /api/auth/me` | Permitido | Permitido |
| Alterar Própria Senha | `POST /api/auth/change-password` | Permitido | Permitido |
| Listar Usuários | `GET /api/users` | **Permitido** | ❌ **403 Forbidden** |
| Criar Usuário | `POST /api/users` | **Permitido** | ❌ **403 Forbidden** |
| Ativar/Desativar Usuário | `PATCH /api/users/{id}/status` | **Permitido** | ❌ **403 Forbidden** |
| Listar Avaliações | `GET /api/runs` | Retorna todas | Retorna apenas `user_id == me` |
| Criar Nova Avaliação | `POST /api/runs` | Permitido (dono=admin) | Permitido (dono=user) |
| Detalhes da Avaliação | `GET /api/runs/{id}` | Todas | Apenas se `run.user_id == me` |
| Streaming de Eventos SSE | `GET /api/runs/{id}/events` | Todas | Apenas se `run.user_id == me` |
| Cancelar Avaliação | `POST /api/runs/{id}/cancel` | Todas | Apenas se `run.user_id == me` |
| Reexecutar Avaliação | `POST /api/runs/{id}/rerun` | Todas | Apenas se `run.user_id == me` |
| Exportar Relatório HTML | `GET /api/runs/{id}/export` | Todas | Apenas se `run.user_id == me` |
| Triar Falso Positivo | `PATCH /api/findings/{id}/triage` | Todas | Apenas se `run.user_id == me` |
| Configurar IA | `POST /api/ai/config` | Salva no seu perfil | Salva no seu perfil |
| Chat Playground | `POST /api/ai/chat-test` | Usa sua chave | Usa sua chave |

