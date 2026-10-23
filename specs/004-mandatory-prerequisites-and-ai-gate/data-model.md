# Data Model & Schema Specifications: 004-mandatory-prerequisites-and-ai-gate

## 1. Entities & Validation Contracts

### 1.1 CreateRunRequest (`app/models.py`)

Modelo de entrada Pydantic recebido por `POST /api/runs`.

```python
class CreateRunRequest(BaseModel):
    """Payload to create and launch a new assessment Run."""

    source_type: Literal["workspace_path", "zip_upload"] = "workspace_path"
    workspace_subpath: str = "app"
    zip_filename: str | None = None
    target_url: str | None = None
    zap_authorized: bool = False  # Obrigatório ser True para qualquer execução
    zap_mode: Literal["baseline", "active"] = "baseline"
```

**Regras de Validação no Backend**:
1. `zap_authorized`: DEVE ser avaliado pelo gatekeeper `_parse_create_run_payload`. Se `False`, dispara `HTTPException(403)`.
2. `AISecretStore.get_instance().is_configured()`: DEVE ser avaliado antes da persistência de `Run`. Se `False`, dispara `HTTPException(412)`.

---

### 1.2 Error Responses Contracts

#### Erro 403: Violação de Guardrail DAST
- **Status HTTP**: `403 Forbidden`
- **Schema**:
```json
{
  "detail": "Guardrail DAST acionado: É obrigatório declarar autorização explícita para testes dinâmicos antes de iniciar qualquer avaliação."
}
```

#### Erro 412: Falha de Pré-requisito de Provedor de IA
- **Status HTTP**: `412 Precondition Failed`
- **Schema**:
```json
{
  "detail": "Pré-requisito de IA não atendido: O provedor de IA generativa deve ser configurado (modelo e API Key em memória) antes de iniciar a avaliação."
}
```

---

### 1.3 AI State Model (`app/models.py`)

```python
class AIConfigStatus(BaseModel):
    """Safe, read-only status of the in-memory AI configuration."""
    configured: bool
    model_name: str | None = None
    key_masked: str | None = None  # Sempre '••••••••' quando configurado, nunca a chave real
```

