# Plano Técnico de Implementação (SDD Plan) — Feature 024: Correção da Autoavaliação e Sincronismo SAST/DAST

**Branch**: `024-fix-self-check-and-dast-orchestrator`  
**Referência da Spec**: [spec.md](file:///home/user/felipe/speckit/asvs/specs/024-fix-self-check-and-dast-orchestrator/spec.md)  
**Status**: Pronto para Execução  
**Versão Alvo**: `v024`  

---

## 1. Mudanças Técnicas

### 1.1 Backend: `app/agents/orchestrator.py`
1. **Elevação de Timeout**:
   - Atualizar `stage_timeout_sec: float = Field(default=180.0, ...)` em `OrchestratorInput`.
2. **Tratamento de Exceções no Bloco Concorrente SAST/DAST**:
   - No bloco `try:` envolvendo `asyncio.gather(_run_sast(), _run_dast())`:
     - Em `except asyncio.TimeoutError:`:
       - Emitir `self._emit(run_id, status=RunStatus.RUNNING.value, stage=PipelineStage.SAST.value, stage_status="FAILED", ...)`
       - Se DAST estava habilitado e com target_url: emitir `self._emit(run_id, status=RunStatus.RUNNING.value, stage=PipelineStage.DAST.value, stage_status="FAILED", ...)`
       - Relançar `TimeoutError(f"Tempo limite ({inp.stage_timeout_sec}s) esgotado...")`
     - Em `except Exception as exc:`:
       - Emitir `FAILED` para `SAST` e `DAST` (se iniciado) com a mensagem de erro.
       - Relançar a exceção.

### 1.2 Frontend: `static/app.js`
1. **Refatoração de `initAssessmentForm()` / `selfCheckBtn`**:
   - Eliminar a lógica que tentava alterar `sourceSelect.value = "workspace_path"` e `#workspace-subpath`.
   - Implementar chamada direta `fetch("/api/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_type: "workspace_path", workspace_subpath: "app", target_url: targetUrl, zap_authorized: true, zap_mode: "active" }) })`.
   - Limpar o stepper com `resetStepper()`, conectar SSE via `connectSSE(payload.run_id)` e redirecionar para a aba de execução (`tab-execution`).

### 1.3 Versão: `app/main.py` e `templates/index.html`
- `APP_UI_VERSION = "024"`.
- `?v=024` nos links de assets em `templates/index.html`.

### 1.4 Testes TDD: `tests/test_feature_024_self_check_and_dast_sync.py`
- Teste unitário e de integração do `OrchestratorAgent` simulando `TimeoutError` no `gather` e verificando que ambos os estágios emitem `FAILED`.
- Teste de regressão para submissão JSON de `workspace_path="app"` com `zap_authorized=True`.
- Teste estático de asset verificando `v=024` e a nova implementação desacoplada em `static/app.js`.

---

## 2. Matriz de Rastreabilidade

| Requisito Spec | Componente Modificado | Teste TDD |
| :--- | :--- | :--- |
| **FR-001** (Self-check desacoplado) | `static/app.js` | `test_self_check_payload_and_ui_handling` |
| **FR-002 / FR-003** (ZAP Online/Offline no self-check) | `static/app.js` | `test_self_check_payload_and_ui_handling` |
| **FR-004** (Timeout 180s) | `app/agents/orchestrator.py` | `test_orchestrator_default_timeout_is_180s` |
| **FR-005** (Sincronismo FAILED SAST/DAST) | `app/agents/orchestrator.py` | `test_orchestrator_timeout_emits_failed_for_both_sast_and_dast` |
| **FR-006** (Versão 024) | `app/main.py`, `templates/index.html` | `test_version_bump_024` |

