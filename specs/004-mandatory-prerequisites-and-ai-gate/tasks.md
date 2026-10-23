---
description: "Task list for feature 004-mandatory-prerequisites-and-ai-gate"
---

# Tasks: 004-mandatory-prerequisites-and-ai-gate

**Input**: Design documents from `/specs/004-mandatory-prerequisites-and-ai-gate/` (`spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`)

**Prerequisites**:
- `specs/004-mandatory-prerequisites-and-ai-gate/spec.md`
- `specs/004-mandatory-prerequisites-and-ai-gate/plan.md`
- `.specify/memory/constitution.md` (v1.3.0)

**Organization**: Tarefas agrupadas por fases e User Stories para implementação e testes independentes de cada guardrail.

---

## Phase 1: Setup & Shared Foundations

**Purpose**: Verificação das estruturas base e modelos compartilhados.

- [X] T001 Revisar e garantir que `CreateRunRequest` em `app/models.py` contenha o campo `zap_authorized: bool = False` e tipagem estrita
- [X] T002 [P] Validar que o singleton `AISecretStore` em `app/core/ai_secrets.py` expõe adequadamente `is_configured() -> bool` e métodos Write-Only

---

## Phase 2: User Story 1 - Bloqueio Mandatório Geral de Autorização DAST (Priority: P1 🎯 MVP)

**Goal**: Exigir incondicionalmente o aceite do termo de autorização DAST para qualquer execução de avaliação (manual ou autoavaliação, com ou sem URL alvo).

**Independent Test**: Enviar requisição a `POST /api/runs` com `zap_authorized=False`: comprovar retorno `HTTP 403 Forbidden` com mensagem de guardrail DAST. No frontend, tentar submeter formulário com checkbox desmarcado e comprovar bloqueio no cliente, destaque visual em vermelho Fluent e foco imediato no checkbox `#zap-authorized`.

### Tests for User Story 1

- [X] T003 [P] [US1] Atualizar testes em `tests/test_dast_guardrail.py` cobrindo: (a) rejeição HTTP 403 para requisição com `target_url` e `zap_authorized=False`; (b) rejeição HTTP 403 para requisição SAST-only (sem `target_url`) com `zap_authorized=False`; (c) aceitação quando `zap_authorized=True` (com IA mock configurada)

### Implementation for User Story 1

- [X] T004 [US1] Atualizar `_parse_create_run_payload` em `app/main.py` para validar incondicionalmente `if not req.zap_authorized: raise HTTPException(status_code=403, detail="Guardrail DAST acionado: É obrigatório declarar autorização explícita para testes dinâmicos antes de iniciar qualquer avaliação.")`
- [X] T005 [P] [US1] Atualizar `submitAssessmentForm` em `static/app.js` para validar incondicionalmente `zapAuthCheckbox.checked`: se False, interromper envio, adicionar classe `.has-error` em `#dast-auth-container`, focar `#zap-authorized` e anunciar bloqueio no banner `#form-feedback-banner` com `role="alert"` e `aria-live="polite"`

**Checkpoint**: User Story 1 concluída — o guardrail DAST é universalmente incondicional no frontend e backend.

---

## Phase 3: User Story 2 - Gate Mandatório de Configuração de IA (AI Gate) (Priority: P1)

**Goal**: Bloquear incondicionalmente o início de qualquer avaliação caso o provedor de IA generativa não esteja previamente configurado em memória volátil (`AISecretStore.is_configured() == True`).

**Independent Test**: Tentar iniciar uma avaliação sem ter configurado modelo e chave de IA: no backend comprovar resposta `HTTP 412 Precondition Failed`; no frontend comprovar que a submissão é bloqueada, a seção colapsável `#ai-config-details` é expandida automaticamente e o foco é posicionado no input `#ai-api-key`.

### Tests for User Story 2

- [X] T006 [P] [US2] Criar arquivo de testes `tests/test_ai_gate.py` validando: (a) rejeição de `POST /api/runs` com `HTTP 412 Precondition Failed` quando `AISecretStore.is_configured() == False`; (b) aceitação com `HTTP 202` quando IA é configurada via `POST /api/ai/config` e `zap_authorized=True`; (c) rejeição da rota de reexecução `POST /api/runs/{id}/rerun` com `HTTP 412` se a IA for desconfigurada

### Implementation for User Story 2

- [X] T007 [US2] Atualizar `_parse_create_run_payload` em `app/main.py` para validar o AI Gate: se `not AISecretStore.get_instance().is_configured()`, levantar `HTTPException(status_code=412, detail="Pré-requisito de IA não atendido: O provedor de IA generativa deve ser configurado (modelo e API Key em memória) antes de iniciar a avaliação.")`
- [X] T008 [P] [US2] Implementar interceptação de AI Gate no frontend em `static/app.js`: rastrear estado reativo `state.aiConfigured`; em `submitAssessmentForm`, se `!state.aiConfigured`, cancelar envio, abrir `<details id="ai-config-details">` (`details.open = true`), posicionar foco no input `#ai-api-key` e exibir aviso com token Fluent no `#form-feedback-banner`; atualizar o botão `#self-check-btn` para validar `state.aiConfigured` antes de disparar

**Checkpoint**: User Story 2 concluída — o gate de IA impede execuções não assistidas e orienta o operador a configurar a chave.

---

## Phase 4: User Story 3 - Gestão Segura de Credenciais, Teste de Conexão e Liberação Reativa (Priority: P2)

**Goal**: Garantir experiência fluida de configuração, validação prévia de conectividade com a IA e liberação reativa imediata dos controles da interface após salvamento da credencial em memória sob política Write-Only.

**Independent Test**: Digitar modelo e chave no painel de IA, testar a conexão com sucesso via `#ai-test-connection-btn`, clicar em `#ai-save-config-btn`: verificar que `state.aiConfigured` se torna `true`, o input de senha é limpo e mascarado, e o formulário de avaliação é liberado para submissão imediata.

### Implementation for User Story 3

- [X] T009 [US3] Atualizar `saveAIConfig` em `static/app.js` para atualizar `state.aiConfigured = true`, atualizar o badge `#ai-status-badge` para "IA CONFIGURADA" com token verde Fluent, limpar o valor digitado no DOM (`keyInput.value = ""`) mantendo placeholder mascarado, e limpar mensagens de erro prévias do formulário
- [X] T010 [P] [US3] Atualizar `templates/index.html` e `static/theme.css` refinando o layout do banner de feedback `#form-feedback-banner` e containers de pré-requisitos para acessibilidade WCAG 2.2 AA

**Checkpoint**: User Story 3 concluída — o fluxo de configuração de IA e liberação do formulário funciona perfeitamente de ponta a ponta.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Alinhamento de fixtures de testes de integração, verificação completa de regressões e auditoria estática com Semgrep.

- [X] T011 Atualizar fixtures e chamadas em `tests/test_pipeline_integration.py` para garantir que todas as invocações a `POST /api/runs` forneçam `zap_authorized=True` e configurem credenciais mock de IA previamente em memória antes dos testes da matriz de vereditos
- [X] T012 Executar a suíte completa de testes automatizados (`pytest -v`) validando cobertura das 3 User Stories com 100% de testes aprovados
- [X] T013 [P] Executar o scanner estático Semgrep (`/home/user/.local/bin/semgrep scan --config config/semgrep_rules app/`) garantindo 0 achados de segurança no código desenvolvido
- [X] T014 Validar manualmente os cenários do guia rápido [`quickstart.md`](./quickstart.md): bloqueio 403 sem DAST, bloqueio 412 sem IA, salvamento de credencial mascarada e execução bem-sucedida
- [X] T015 Verificar que os diretórios históricos `specs/001-asvs-v1-assessment/`, `specs/002-zap-dast-integration/` e `specs/003-ai-evaluator-and-dast-guardrails/` permaneceram rigorosamente intocados e que `.specify/feature.json` aponta para `specs/004-mandatory-prerequisites-and-ai-gate`

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: `T001` e `T002` preparam a base.
- **User Story 1 (Phase 2 - P1 🎯 MVP)**: `T003` (testes DAST 403) precede `T004` (backend) e `T005` (frontend).
- **User Story 2 (Phase 3 - P1)**: `T006` (testes AI Gate 412) precede `T007` (backend) e `T008` (frontend).
- **User Story 3 (Phase 4 - P2)**: `T009` e `T010` refinam a UX reativa e estilos.
- **Polish (Phase 5)**: `T011` a `T015` executam a verificação integrada fim a fim.
