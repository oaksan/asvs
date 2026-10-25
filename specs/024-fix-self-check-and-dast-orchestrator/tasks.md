# Tarefas de Engenharia (SDD Tasks) — Feature 024: Correção da Autoavaliação e Sincronismo SAST/DAST

**Branch**: `024-fix-self-check-and-dast-orchestrator`  
**Status**: Ready for Execution  

---

## Fase 1 — TDD (Testes Automatizados Pré-Implementação)
- [x] **T001**: Criar `tests/test_feature_024_self_check_and_dast_sync.py` com:
  - Teste de timeout do Orchestrator garantindo emissão de `FAILED` para `SAST` e `DAST`.
  - Teste de valor padrão de `stage_timeout_sec == 180.0`.
  - Teste de integração do endpoint `/api/runs` com `workspace_subpath="app"` e `target_url="http://localhost:8000"`.
  - Teste estático de assets (`v=024` e desacoplamento do `selfCheckBtn`).
- [x] **T002**: Executar suíte para confirmar o estágio TDD Red.

---

## Fase 2 — Implementação
- [x] **T003**: Atualizar `app/agents/orchestrator.py`:
  - `stage_timeout_sec: float = 180.0`.
  - Bloco de tratamento de exceções no `asyncio.gather(_run_sast(), _run_dast())` com emissão simultânea de `FAILED` para SAST e DAST.
- [x] **T004**: Atualizar `static/app.js`:
  - Refatorar `selfCheckBtn` para chamada direta `POST /api/runs` com JSON `{ source_type: "workspace_path", workspace_subpath: "app", ... }`.
- [x] **T005**: Atualizar versão:
  - `APP_UI_VERSION = "024"` em `app/main.py`.
  - `?v=024` em `templates/index.html`.

---

## Fase 3 — Verificação e Docker
- [x] **T006**: Executar `pytest tests/test_feature_024_self_check_and_dast_sync.py` (estágio TDD Green).
- [x] **T007**: Executar suíte de testes de regressão.
- [x] **T008**: Reconstruir containers Docker (`docker compose up --build -d web`).
- [x] **T009**: Testar autoavaliação real via HTTP / SSE na aplicação em execução.

---

## Fase 4 — Revisão e Versionamento Git
- [x] **T010**: Auditoria constitucional final (`constitution-guardian`).
- [x] **T011**: Commit semântico `feat(spec-024): correcao da autoavaliacao app e sincronismo sast dast no orchestrator`.
- [x] **T012**: Tag `v024` e `git push origin main v024`.

