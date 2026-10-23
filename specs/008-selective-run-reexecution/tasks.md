# Tasks: 008-selective-run-reexecution

**Spec Reference**: [`specs/008-selective-run-reexecution/spec.md`](spec.md)  
**Plan Reference**: [`specs/008-selective-run-reexecution/plan.md`](plan.md)  
**Status**: Ready for Implementation (TDD Ready)

---

## Phase 1: Setup & Automated TDD Tests (Blocking Prerequisites)

**Purpose**: Escrever testes automatizados que cobrem reexecução seletiva, herança de vereditos/achados, validações de contrato e RBAC antes da codificação.

- [x] T001 Criar suite de testes em `tests/test_selective_rerun.py` cobrindo cenários Given/When/Then:
  - Reexecução seletiva de 1 requisito de IA (`V1.3.1`): pula SAST e DAST, reexecuta IA e herda os outros 7 requisitos com `is_inherited=True`.
  - Reexecução seletiva de 1 requisito SAST (`V1.3.2`): pula DAST e IA, reexecuta Semgrep e herda os outros 7 requisitos.
  - Reexecução seletiva multi-ferramenta (`["V1.2.4", "V1.3.1"]`).
  - Rejeição de `req_ids` inválidos (`["V9.9.9"]`) com `HTTP 400 Bad Request`.
  - Rejeição de `req_ids` vazio (`[]`) com `HTTP 400 Bad Request`.
  - Rejeição de reexecução em execução pai não finalizada (`RUNNING` / `PENDING`) com `HTTP 400 Bad Request`.
  - Prevenção de IDOR: usuário comum tentando reexecutar avaliação de outro usuário recebe `HTTP 403 Forbidden`.
  - Métricas consolidadas: `pass_percentage` calculado sobre todos os 8 requisitos.
- [x] T002 Executar `.venv/bin/pytest tests/test_selective_rerun.py` para certificar que os testes falham antes da implementação (TDD RED).

---

## Phase 2: Core Data Model & SQLite Migration (Priority: P1 🎯 MVP)

**Goal**: Adicionar campos de linhagem e reexecução seletiva nas entidades SQLModel e migrar o banco SQLite de forma idempotente.

- [x] T003 Atualizar `app/models.py`:
  - Enriquecer `Run` com `is_selective: bool = False`, `selected_req_ids_json: str | None = None` e `inherited_from_run_id: int | None = None`.
  - Enriquecer `Verdict` com `is_inherited: bool = False` e `inherited_from_run_id: int | None = None`.
  - Enriquecer `Finding` com `is_inherited: bool = False` e `inherited_from_run_id: int | None = None`.
  - Criar schema Pydantic `SelectiveRerunRequest(req_ids: list[str] | None = None)` com validador estrito contra `IN_SCOPE_REQ_IDS`.
- [x] T004 Atualizar `app/database.py` na função `init_db()` com migração idempotente via `PRAGMA table_info` adicionando as novas colunas nas tabelas `run`, `verdict` e `finding`.

---

## Phase 3: Orchestrator & Selective Execution Engine (Priority: P1 🎯 MVP)

**Goal**: Implementar a lógica de orquestração condicional, pulo de estágios (SKIPPED) e herança de achados/vereditos no backend.

- [x] T005 Atualizar `OrchestratorInput` em `app/agents/orchestrator.py` para receber `selective_req_ids: list[str] | None = None`.
- [x] T006 Implementar no `OrchestratorAgent.execute`:
  - Determinação de ferramentas necessárias (`target_reqs` vs `inherited_reqs`).
  - Pulo dos estágios SAST, DAST e IA com evento `SKIPPED` quando nenhuma regra do estágio for requerida.
  - Clonagem de `Finding` e `Evidence` da `previous_run_id` para requisitos herdados com `is_inherited=True`.
  - Clonagem de `Verdict` para requisitos herdados com `is_inherited=True`.
  - Recálculo das métricas globais (`compute_run_metrics`) cobrindo todos os 8 requisitos.
- [x] T007 Atualizar endpoint `POST /api/runs/{run_id}/rerun` em `app/main.py`:
  - Aceitar corpo opcional `SelectiveRerunRequest`.
  - Validar status da execução pai (deve estar em `COMPLETED`, `FAILED`, `CANCELLED`).
  - Preencher `is_selective`, `selected_req_ids_json` e `inherited_from_run_id` na nova `Run`.
  - Passar `selective_req_ids` ao `OrchestratorInput`.
- [x] T008 Executar `.venv/bin/pytest tests/test_selective_rerun.py` para confirmar que todos os testes da Feature 008 passam (TDD GREEN).

---

## Phase 4: Frontend Fluent 2 & Filtros Multidimensionais (Priority: P2)

**Goal**: Criar diálogo modal acessível com filtros por Seção, ID, Veredito, Confiança e Ferramenta com política estrita de Zero innerHTML.

- [x] T009 Criar modal `<dialog id="selective-rerun-dialog">` em `templates/index.html` com:
  - Filtros: `<select id="filter-section">`, `<select id="filter-id">`, `<select id="filter-verdict">`, `<select id="filter-confidence">`, `<select id="filter-tool">`.
  - Tabela acessível de requisitos com checkboxes individuais e checkbox mestre "Selecionar Todos".
  - Botões "Selecionar Filtrados", "Limpar Seleção" e contador dinâmico `X de 8 requisitos selecionados`.
  - Botão de ação "Disparar Reexecução Seletiva".
- [x] T010 Adicionar botões "Reexecução Seletiva..." no Dashboard (Aba 2) e na tabela do Histórico (Aba 4) em `templates/index.html` e `static/app.js`.
- [x] T011 Implementar controladores de filtragem no DOM, seleção em lote e disparo de `POST /api/runs/{run_id}/rerun` com `req_ids` em `static/app.js` (100% via `document.createElement` e `textContent`).
- [x] T012 Atualizar visualização do Dashboard e Histórico para exibir badge `Reexecução Seletiva (X/8)` e indicar quais requisitos foram recalculados vs herdados.

---

## Phase 5: Homologação, Regressão e Revisão de Segurança (Priority: P1)

**Goal**: Garantir 100% de aprovação na suíte de testes (91 testes legados + novos testes de rerun seletivo), auditar guardrails e obter liberação formal do Gate 3.

- [x] T013 Executar toda a suíte de testes do projeto: `.venv/bin/pytest -q` (garantindo 100% GREEN, zero regressão).
- [x] T014 Auditoria de segurança e guardrails com `aci-security-reviewer`.
- [x] T015 Auditoria constitucional e emissão de parecer do Gate 3 pelo `constitution-guardian`.

