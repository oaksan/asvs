# Contract: HTTP REST & Server-Sent Events (SSE) API (`app/main.py`)

**Feature**: `001-asvs-v1-assessment`  
**Date**: 2026-10-12  
**Framework**: FastAPI + `sse-starlette` + Jinja2 (`autoescape=True`)

---

## 1. Visão Geral dos Endpoints

| Método | Rota | Descrição |
| :--- | :--- | :--- |
| `GET` | `/` | Renderiza a página principal (`templates/index.html`) com Fluent 2 Design System e `autoescape=True`. |
| `GET` | `/api/requirements/in-scope` | Retorna os 8 requisitos em escopo (`chapter_id = 'V1'` e `level = 1`) enriquecidos com ferramentas, regras mapeadas e status de equivalência `4.0 → 5.0`. |
| `GET` | `/api/requirements` | Consulta paginada/filtrada somente leitura dos 345 requisitos do catálogo completo (`V1`–`V17`, níveis `1`–`3`). |
| `POST` | `/api/runs` | Valida autorização/allowlist/caminho (ou upload `.zip`), cria um registro `Run` e dispara o `Orchestrator` em background. |
| `GET` | `/api/runs` | Lista o histórico de execuções (`Run`) ordenado da mais recente para a mais antiga. |
| `GET` | `/api/runs/{run_id}` | Retorna o estado consolidado da execução: métricas, 8 vereditos, contagens por seção (`V1.2`, `V1.3`, `V1.5`) e log de chamadas ACI. |
| `GET` | `/api/runs/{run_id}/events` | Stream **SSE (`text/event-stream`)** com eventos em tempo real das etapas do pipeline (`SCOPER`, `SAST`, `DAST`, `TRIAGE`, `VERDICT`, `REPORT`). |
| `POST` | `/api/runs/{run_id}/cancel` | Solicita o cancelamento gracioso de uma execução em andamento (`status = "CANCELLED"`). |
| `POST` | `/api/runs/{run_id}/rerun` | Reexecuta de forma idempotente os mesmos parâmetros de uma `Run` anterior em uma nova instância auditável. |
| `GET` | `/api/runs/{run_id}/findings` | Lista achados (`Finding`) da execução com filtro por `req_id`, `severity`, `tool`, `include_fp` e paginação (máx. 50 por página). |
| `GET` | `/api/findings/{finding_id}/evidence` | Retorna o detalhe completo da evidência (`Evidence`) associada ao achado (`arquivo:linha` + snippet ou `request/response` HTTP). |
| `PATCH` | `/api/findings/{finding_id}/triage` | Marca ou desmarca um achado como falso positivo (`is_false_positive` + `justification` obrigatória), grava `AuditLog` e recalcula o `Verdict` do requisito e métricas da `Run`. |
| `GET` | `/api/runs/compare` | Compara duas execuções (`?base_run_id=X&target_run_id=Y`), retornando deltas de `% PASS`, contagens e transições de veredito para cada um dos 8 requisitos. |
| `GET` | `/api/runs/{run_id}/export` | Exporta o relatório completo da avaliação em formato `format=json` ou `format=html` (HTML estático autossuficiente com folha de estilo de impressão para PDF). |

---

## 2. Schemas Principais de Request / Response

### 2.1 `GET /api/requirements/in-scope`

**Response `200 OK`**:
```json
{
  "total": 8,
  "scope_rule": "chapter_id == 'V1' and level == 1",
  "items": [
    {
      "req_id": "V1.2.1",
      "chapter_id": "V1",
      "chapter_name": "Encoding and Sanitization",
      "section_id": "V1.2",
      "section_name": "Injection Prevention",
      "req_description": "Verify that output encoding for an HTTP response, HTML document, or XML document is relevant for the context required...",
      "level": 1,
      "in_scope": true,
      "tools": ["semgrep", "zap"],
      "semgrep_rules": ["v1-2-1-jinja2-autoescape-off", "v1-2-1-innerhtml-sink", "v1-2-1-markupsafe-bypass"],
      "zap_plugins": ["40012", "40014", "10038"],
      "asvs_4_0_ref": ["V5.3.1", "V5.3.3"],
      "mapping_status": "a validar"
    }
  ]
}
```

### 2.2 `POST /api/runs` (Criação de Avaliação)

Aceita `multipart/form-data` (quando `source_type = "zip_upload"`) ou `application/json` (quando `source_type = "workspace_path"`).

**Request JSON**:
```json
{
  "source_type": "workspace_path",
  "workspace_subpath": "tests/vulnerable_app",
  "target_url": "http://localhost:8081",
  "zap_authorized": true,
  "zap_mode": "baseline"
}
```

**Regras de Guardrail (`400 Bad Request` / `403 Forbidden`)**:
- Se `target_url` for informado e `zap_authorized != true` → `403 Forbidden` (`"Execução DAST exige confirmação explícita de autorização pelo usuário."`).
- Se `target_url` não pertencer à `allowlist` configurada → `403 Forbidden` (`"URL alvo fora da allowlist autorizada."`).
- Se `workspace_subpath` resolver para fora do workspace ou não existir → `400 Bad Request` (`"Caminho fora do workspace permitido ou inexistente."`).

**Response `202 Accepted`**:
```json
{
  "run_id": 1,
  "status": "PENDING",
  "current_stage": "INIT",
  "events_url": "/api/runs/1/events"
}
```

### 2.3 `GET /api/runs/{run_id}/events` (Contrato SSE)

Stream no formato padrão Server-Sent Events (`event: pipeline_update`).

**Payload de Evento SSE**:
```json
{
  "run_id": 1,
  "status": "RUNNING",
  "stage": "SAST",
  "stage_status": "COMPLETED",
  "progress_percent": 45,
  "message": "SAST Agent finalizou 8 regras Semgrep em 6 arquivos (7 achados detectados).",
  "tool_call_summary": {
    "aci": "semgrep_aci",
    "command": "run_rules",
    "duration_ms": 1420
  },
  "timestamp": "2026-10-12T23:20:00Z"
}
```

### 2.4 `PATCH /api/findings/{finding_id}/triage` (Marcação de Falso Positivo)

**Request JSON**:
```json
{
  "is_false_positive": true,
  "justification": "O valor interpolado vem de constante interna estática validada em tempo de build, sem input do usuário."
}
```

**Response `200 OK`**:
```json
{
  "finding_id": 14,
  "req_id": "V1.2.4",
  "is_false_positive": true,
  "audit_log_id": 3,
  "updated_verdict": {
    "req_id": "V1.2.4",
    "status": "PASS",
    "active_findings_count": 0,
    "coverage_declared": "6 arquivos Python verificados (3 chamadas SQL parametrizadas confirmadas)"
  },
  "updated_run_metrics": {
    "pass_percentage": 62.5,
    "pass_count": 5,
    "fail_count": 2,
    "inconclusive_count": 0,
    "manual_count": 1
  }
}
```

