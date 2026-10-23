# Tasks: Compatibilidade Nativa com Azure OpenAI GPT-5.4

**Input**: `specs/011-azure-openai-gpt54-compatibility/spec.md`, `specs/011-azure-openai-gpt54-compatibility/plan.md`

---

## Phase 1: Especificação, Arquitetura e Gate Constitucional (Fases 1 & 2)

- [x] T001 Gerar `spec.md`, `plan.md` e `tasks.md` em `specs/011-azure-openai-gpt54-compatibility/`.
- [x] T002 Validar design e conformidade constitucional (Gates 1 e 2) com `solution-architect` e `constitution-guardian`.

---

## Phase 2: Testes Automatizados TDD (Fase 3 - Red)

- [x] T003 [US1/US2] Adicionar testes em `tests/test_ai_azure_openai.py`:
  - `test_azure_openai_gpt54_uses_max_completion_tokens_in_connectivity_chat_and_eval`
  - `test_azure_openai_auto_fallback_on_unsupported_temperature_or_max_tokens`
  - `test_normalize_azure_settings_extracts_from_full_endpoint_url`
  - `test_azure_openai_400_error_surfaces_sanitized_provider_detail`

---

## Phase 3: Implementação Backend & Frontend (Fase 4 - Green)

- [x] T004 [US1/US2] Implementar `normalize_azure_settings` e `_post_azure_chat_completion` (usando `max_completion_tokens` com fallback transparente) em `app/aci/ai_aci.py`.
- [x] T005 [US2] Integrar `normalize_azure_settings` em `set_ai_config`, `test_ai_connection` e `test_ai_chat` em `app/main.py`.
- [x] T006 [US2] Atualizar defaults na aba 5 (`templates/index.html` com `?v=011`) e auto-extração de URL colada em `static/app.js`.

---

## Phase 4: Revisão de Segurança, Gate Final e Restart (Fase 5)

- [x] T007 Executar suíte de testes `.venv/bin/pytest -q`.
- [x] T008 Executar auditoria com `aci-security-reviewer`, `llm-security-reviewer` e `constitution-guardian` (Gate 3) e reiniciar `asvs-self-assessment-web`.

