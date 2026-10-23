# Tasks: Separação Visual SAST/DAST, Alternância Exclusiva SAST, Active Scan Padrão e Auto-Validação ZAP

**Input**: `specs/012-frontend-sast-dast-split-and-auto-zap/spec.md`, `specs/012-frontend-sast-dast-split-and-auto-zap/plan.md`

---

## Phase 1: Especificação, Arquitetura e Gate Constitucional (Fases 1 & 2)

- [x] T001 Gerar `spec.md`, `plan.md` e `tasks.md` em `specs/012-frontend-sast-dast-split-and-auto-zap/`.
- [x] T002 Validar design e conformidade constitucional (Gates 1 e 2) com `solution-architect` e `constitution-guardian`.

---

## Phase 2: Testes Automatizados TDD (Fase 3 - Red)

- [x] T003 [US1/US2/US3] Adicionar testes em `tests/test_ui_presentation.py`:
  - `test_ui_separates_sast_and_dast_artifact_cards`
  - `test_ui_enforces_hidden_css_rule_and_exclusive_sast_source_toggle`
  - `test_ui_and_api_default_zap_mode_is_always_active_scan`
  - `test_ui_includes_automatic_zap_online_polling_after_startup`

---

## Phase 3: Implementação Frontend & Backend (Fase 4 - Green)

- [x] T004 [US1] Adicionar `[hidden] { display: none !important; }` e estilos `.artifact-split-grid` / `.artifact-section-card` em `static/theme.css`.
- [x] T005 [US1/US2] Reestruturar `#new-run-form` em `templates/index.html` separando os cartões de **Artefato SAST** e **Artefato DAST**, fixando `#zap-mode` em `active`.
- [x] T006 [US1/US2/US3] Implementar `syncSastSourceFields()`, `scheduleZapAutoCheck()` e validação separada de artefatos SAST/DAST em `static/app.js`.
- [x] T007 [US2] Atualizar default `zap_mode="active"` em `app/models.py`, `app/schemas.py` e `app/main.py`.

---

## Phase 4: Revisão de Segurança, Gate Final e Restart (Fase 5)

- [x] T008 Executar suíte de testes `.venv/bin/pytest -q`.
- [x] T009 Executar auditoria com `aci-security-reviewer`, `llm-security-reviewer` e `constitution-guardian` (Gate 3) e reiniciar `asvs-self-assessment-web`.

