# Contratos de Interface: API de IA Segura, AI Evaluator Agent e Guardrail DAST (`003-ai-evaluator-and-dast-guardrails`)

**Feature**: [spec.md](../spec.md)  
**Date**: 2026-10-13

---

## 1. Contratos REST (`app/main.py`)

### 1.1 `GET /api/ai/status`

Consulta o estado atual do provedor de IA sem vazar a chave de API.

- **Request**: `GET /api/ai/status`
- **Response `200 OK` (Configurado)**:
  ```json
  {
    "configured": true,
    "model_name": "gemini-2.0-flash",
    "key_masked": "••••••••",
    "provider": "gemini"
  }
  ```
- **Response `200 OK` (Não Configurado)**:
  ```json
  {
    "configured": false,
    "model_name": null,
    "key_masked": null,
    "provider": "gemini"
  }
  ```

---

### 1.2 `POST /api/ai/config`

Configura o modelo e a chave de API em memória de forma estritamente *write-only*.

- **Request Body**:
  ```json
  {
    "model_name": "gemini-2.0-flash",
    "api_key": "AIzaSy..."
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "configured": true,
    "model_name": "gemini-2.0-flash",
    "key_masked": "••••••••",
    "message": "Credenciais de IA atualizadas em memória com sucesso."
  }
  ```
- **Response `400 Bad Request`**: Se `model_name` ou `api_key` forem vazios.

---

### 1.3 `POST /api/ai/test-connection`

Executa um handshake de teste com o provedor de IA sem registrar ou expor a chave de API.

- **Request Body** (Opcional — se fornecido, testa as credenciais recebidas; se vazio ou omitido, testa as credenciais salvas em memória):
  ```json
  {
    "model_name": "gemini-2.0-flash",
    "api_key": "AIzaSy..."
  }
  ```
- **Response `200 OK` (Sucesso)**:
  ```json
  {
    "ok": true,
    "model_name": "gemini-2.0-flash",
    "latency_ms": 145,
    "message": "Conexão com o modelo 'gemini-2.0-flash' estabelecida com sucesso (145 ms)."
  }
  ```
- **Response `200 OK` (Falha Sanitizada)**:
  ```json
  {
    "ok": false,
    "model_name": "gemini-2.0-flash",
    "latency_ms": 320,
    "message": "Falha de autenticação com o provedor de IA (HTTP 400/401): verifique se a chave de API e o modelo estão corretos."
  }
  ```

---

### 1.4 `POST /api/runs` (Guardrail DAST Atualizado)

- **Cenário de Violação de Guardrail**:
  ```json
  {
    "source_type": "workspace_path",
    "workspace_subpath": "app",
    "target_url": "http://localhost:8000",
    "zap_authorized": false
  }
  ```
- **Response `403 Forbidden`**:
  ```json
  {
    "detail": "Guardrail DAST acionado: execução dinâmica bloqueada porque o checkbox de autorização explícita não foi confirmado."
  }
  ```

---

## 2. Contratos da Camada ACI (`app/aci/ai_aci.py`)

### `run_ai_evaluation`

```python
async def run_ai_evaluation(
    session: Session,
    run_id: int,
    req_id: str,
    source_path: str,
    *,
    agent_name: str = "AIEvaluatorAgent",
    model_name: str | None = None,
    api_key: str | None = None,
    http_client: httpx.AsyncClient | None = None,
    timeout_sec: float = 20.0,
) -> ACIResponse[dict[str, Any]]:
    """Inspects workspace templates and source files, and queries the configured AI model.

    Enforces ACI truncation limits (max 4000 characters context) and structured JSON output.
    Returns ACIResponse containing:
    {
        "req_id": req_id,
        "verdict": "PASS" | "FAIL" | "INCONCLUSIVE" | "MANUAL_REQUIRED",
        "confidence": "HIGH" | "MEDIUM" | "LOW",
        "rationale": str,
        "model_used": str,
        "evidence_snippets": list[str]
    }
    """
```

