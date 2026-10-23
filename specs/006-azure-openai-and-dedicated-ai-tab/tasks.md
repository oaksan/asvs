# Tasks: 006-azure-openai-and-dedicated-ai-tab

**Spec Reference**: [`specs/006-azure-openai-and-dedicated-ai-tab/spec.md`](spec.md)  
**Plan Reference**: [`specs/006-azure-openai-and-dedicated-ai-tab/plan.md`](plan.md)  
**Status**: Ready for Implementation (TDD Ready)

---

## Phase 1: Setup & Automated TDD Tests (Blocking Prerequisites)

**Purpose**: Escrever testes automatizados que cobrem os modelos Pydantic, o `AISecretStore` estendido e os endpoints de chat antes da implementação.

- [x] T001 Criar suite de testes em `tests/test_ai_azure_openai.py` cobrindo o armazenamento volátil com Azure OpenAI, mascaração de chave e mock do endpoint de chat completions.
- [x] T002 Executar `.venv/bin/pytest tests/test_ai_azure_openai.py` para certificar que os testes falham antes da implementação (TDD).

---

## Phase 2: Foundational & Backend Implementation (Priority: P1 🎯 MVP)

**Goal**: Implementar o suporte a Azure OpenAI no armazenamento volátil e na ACI HTTP.

- [x] T003 Atualizar `AISecretStore` em `app/core/ai_secrets.py` para suportar `resource_name`, `deployment_id`, `api_version` e `provider="azureopenai"`.
- [x] T004 Atualizar os schemas Pydantic em `app/models.py` (`AIConfigRequest`, `AIConfigStatus`, `AIChatTestRequest`, `AIChatTestResponse`).
- [x] T005 Implementar suporte a chamadas REST ao Azure OpenAI em `app/aci/ai_aci.py` (`check_ai_connectivity`, `chat_with_ai`, `run_ai_evaluation`).
- [x] T006 Implementar o endpoint `POST /api/ai/chat-test` em `app/main.py`.

---

## Phase 3: User Story 1 & 2 — Aba Dedicada de IA & Playground no Frontend (Priority: P1)

**Goal**: Criar a 5ª aba no menu Fluent e o playground interativo com formulário de configuração e chat.

- [x] T007 Adicionar o botão da aba `#tab-ai-config` no menu de navegação e criar o container `#panel-ai-config` em `templates/index.html`.
- [x] T008 Remover o formulário inline de credenciais da Aba 1 em `templates/index.html`, substituindo-o por um chip executivo de status da IA.
- [x] T009 Implementar em `static/app.js` a lógica da aba 5: preenchimento dos campos Azure OpenAI, salvar credenciais, e função de chat interativo com renderização de balões e latência.

---

## Phase 4: Verificação, Regressão e Revisão de Segurança

**Purpose**: Garantir que 100% dos testes do projeto passam e que a segurança das credenciais foi preservada.

- [x] T010 Executar suíte completa de testes: `.venv/bin/pytest -q`.
- [x] T011 Auditar conformidade de segurança e Zero-Leakage com `llm-security-reviewer` e `constitution-guardian`.

