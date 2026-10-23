# Tasks: Avaliador com IA (AI Evaluator Agent), Configuração Segura Write-Only e Guardrail Mandatório de DAST

**Input**: Design documents from `/specs/003-ai-evaluator-and-dast-guardrails/`
**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md) (required for user stories), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/ai-evaluator-and-dast-guardrails-api.md](./contracts/ai-evaluator-and-dast-guardrails-api.md), [quickstart.md](./quickstart.md)

**Tests**: Incluídos para validar o bloqueio mandatório de DAST (UI + HTTP 403), a política de Zero-Leakage das credenciais de IA em memória, os endpoints `/api/ai/*`, a camada ACI do `AIEvaluatorAgent` e a transição para **100.0% PASS** (8/8) na autoavaliação da própria ferramenta.

**Organization**: Tarefas agrupadas rigorosamente por User Story (`US1`, `US2`, `US3`) para permitir implementação, testes e entregas incrementais e independentes, preservando intactas as especificações históricas `specs/001-asvs-v1-assessment/` e `specs/002-zap-dast-integration/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode ser executada em paralelo (arquivos distintos, sem dependências mútuas)
- **[Story]**: Rótulo de rastreabilidade da User Story correspondente (`[US1]`, `[US2]`, `[US3]`)
- Caminhos exatos de arquivos incluídos em todas as tarefas

---

## Phase 1: Setup (Mapeamento Normativo de Ferramentas)

**Purpose**: Atualizar a configuração declarativa de ferramentas para incluir o motor de IA (`ai_evaluator`) nos requisitos aplicáveis do ASVS V1 L1.

- [X] T001 Atualizar `config/req_tool_mapping.yaml` para mapear o requisito `V1.3.1` com `tools: ["semgrep", "ai_evaluator"]`, definindo o identificador de prompt `asvs_v1_3_1_sanitization` e a descrição da análise contextual de sanitização de HTML rico e autoescape

---

## Phase 2: Foundational (Armazenamento Seguro de Segredos em Memória & Modelos Pydantic)

**Purpose**: Implementar a infraestrutura de gerenciamento volátil de credenciais de IA sob política Write-Only e os esquemas Pydantic compartilhados antes da execução das User Stories.

**⚠️ CRITICAL**: As tarefas desta fase bloqueiam a implementação das User Stories 2 e 3.

- [X] T002 Implementar o singleton `AISecretStore` em `app/core/ai_secrets.py` com atributos privados `_api_key` e `_model_name`, inicialização com fallback para variáveis de ambiente (`AI_MODEL_API_KEY` e `AI_MODEL_NAME`), métodos `set_credentials(model_name: str, api_key: str)`, `is_configured() -> bool`, `get_masked_status() -> dict[str, Any]` (retornando `"key_masked": "••••••••"`), `get_api_key_internal() -> str | None`, e sobrescrita de `__repr__` e `__str__` para blindagem contra vazamento em logs e depuradores
- [X] T003 [P] Definir os esquemas Pydantic `AIConfigStatus`, `AIConfigRequest`, `AITestConnectionResponse`, `AIEvaluatorInput` e `AIEvaluatorOutput` em `app/models.py` (ou `app/core/ai_secrets.py`) conforme especificado em `specs/003-ai-evaluator-and-dast-guardrails/data-model.md`
- [X] T004 [P] Implementar a função de verificação de conectividade `check_ai_connectivity(model_name: str, api_key: str, http_client: httpx.AsyncClient | None = None, timeout_sec: float = 5.0) -> dict[str, Any]` em `app/aci/ai_aci.py`, enviando requisição leve de handshake para o modelo, calculando a latência em milissegundos e sanitizando rigorosamente mensagens de erro para impedir reflexão da chave de API

**Checkpoint**: Camada base de segredos e handshake de IA pronta para integração aos endpoints REST e agentes.

---

## Phase 3: User Story 1 - Bloqueio Mandatório de Início de Avaliação sem Aceite Explícito de Autorização DAST (Priority: P1) 🎯 MVP

**Goal**: Garantir que nenhuma avaliação com URL alvo possa ser disparada no cliente ou no backend se o checkbox formal de consentimento (*"Declaro que possuo autorização explícita para executar testes dinâmicos (DAST / OWASP ZAP) contra a URL alvo informada acima"*) não estiver explicitamente marcado, retornando HTTP 403 no servidor e bloqueio com foco acessível na UI.

**Independent Test**: Submeter uma requisição `POST /api/runs` com `target_url` preenchida e `zap_authorized=False` (validando resposta HTTP 403 sem criação de Run), e preencher o formulário na interface web tentando submeter sem marcar o checkbox (validando o bloqueio reativo, contorno vermelho e foco imediato no checkbox).

### Tests for User Story 1

- [X] T005 [P] [US1] Criar testes automatizados em `tests/test_dast_guardrail.py` validando: (a) rejeição com código HTTP 403 e detalhe informativo quando `POST /api/runs` recebe `target_url` com `zap_authorized=False`; (b) aceitação normal (HTTP 200/202) quando `zap_authorized=True`; (c) aceitação normal sem exigir autorização quando `target_url` for omitida ou vazia (modo Somente SAST)

### Implementation for User Story 1

- [X] T006 [US1] Atualizar `_parse_create_run_payload` e a rota `POST /api/runs` em `app/main.py` para inspecionar `req_obj.target_url`: se não-vazio e `req_obj.zap_authorized is False`, lançar imediatamente `HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Guardrail DAST acionado: execução dinâmica bloqueada porque o checkbox de autorização explícita não foi confirmado.")` antes de instanciar a entidade `Run`
- [X] T007 [P] [US1] Atualizar `templates/index.html` adicionando a classe `.dast-auth-container`, rótulo textual formal obrigatório, atributo `aria-required="true"`, indicação de foco com tokens de erro Fluent (`--colorPaletteRedBorderActive`) e suporte a anúncio dinâmico via região `aria-live="polite"`
- [X] T008 [US1] Atualizar os manipuladores de evento de submissão do formulário (`#evaluation-form.onsubmit`, `#start-run-btn.onclick` e evento `keydown` Enter em `#target-url`) e o atalho `#self-check-btn` em `static/app.js`: verificar se `#target-url` possui valor e `#zap-authorized` está desmarcado; em caso positivo, interromper o envio (`event.preventDefault()`), aplicar a classe de destaque de erro, mover o foco com `.focus()` para `#zap-authorized` e disparar o alerta acessível na tela

**Checkpoint**: User Story 1 concluída — o guardrail mandatório de DAST está ativo e validado de ponta a ponta.

---

## Phase 4: User Story 2 - Configuração Segura Write-Only de Modelo de IA e Teste Prévio de Conectividade (Priority: P1)

**Goal**: Permitir que o avaliador configure o modelo de IA e a chave de API na interface web de forma estritamente *write-only*, com teste de conectividade sob demanda exibindo latência em milissegundos e blindagem absoluta contra vazamento de credenciais em endpoints, relatórios, audit logs ou telas.

**Independent Test**: Configurar uma chave de API via `POST /api/ai/config`, consultar `GET /api/ai/status` (confirmando `"key_masked": "••••••••"`), executar `POST /api/ai/test-connection` (confirmando resposta com latência sem vazar a chave) e testar os botões correspondentes na UI verificando que o campo de senha é limpo após salvar.

### Tests for User Story 2

- [X] T009 [P] [US2] Criar testes unitários em `tests/test_ai_secrets.py` validando o singleton `AISecretStore`: armazenamento volátil em memória, mascaramento estrito em `get_masked_status()`, expurgo da chave em `__repr__` e `__str__`, suporte a fallback via variáveis de ambiente e trim automático de espaços
- [X] T010 [P] [US2] Criar testes de contrato e integração em `tests/test_ai_api.py` para as rotas `GET /api/ai/status`, `POST /api/ai/config` e `POST /api/ai/test-connection`, validando códigos de resposta HTTP, sanitização de erros e ausência total da chave de API em payloads de resposta

### Implementation for User Story 2

- [X] T011 [US2] Criar as rotas REST em `app/main.py`: `GET /api/ai/status` (retornando `AIConfigStatus`), `POST /api/ai/config` (recebendo `AIConfigRequest`, salvando em `AISecretStore` e retornando status mascarado) e `POST /api/ai/test-connection` (invocando `check_ai_connectivity` e retornando `AITestConnectionResponse`)
- [X] T012 [P] [US2] Adicionar o Card/Painel colapsável de Configuração do Provedor de IA em `templates/index.html` contendo o badge de status `#ai-status-badge`, campo `#ai-model-name` (default `gemini-2.0-flash`), campo de senha `#ai-api-key` (`type="password"`, `autocomplete="off"`), botões `#ai-test-connection-btn` ("Testar Conexão com IA") e `#ai-save-config-btn` ("Salvar Chave em Memória") e banner de feedback `#ai-feedback-banner` com `aria-live="polite"`
- [X] T013 [US2] Implementar as funções `refreshAIStatus()`, `saveAIConfig()` e `testAIConnection()` em `static/app.js`: consultar status no carregamento da página, enviar credenciais ao salvar e limpar imediatamente o valor digitado no input `#ai-api-key`, e exibir mensagens diagnósticas com latência e status sem expor dados sensíveis

**Checkpoint**: User Story 2 concluída — gerenciamento seguro de credenciais de IA e teste de conexão operacionais.

---

## Phase 5: User Story 3 - Avaliação Automatizada de Requisitos Qualitativos com AI Evaluator Agent (V1.3.1) (Priority: P2)

**Goal**: Integrar o 8º agente nuclear (`AIEvaluatorAgent`) ao pipeline para analisar contextualmente requisitos qualitativos de codificação (notadamente `V1.3.1` referente a sanitização de HTML rico/WYSIWYG e autoescape em templates), transformando `MANUAL_REQUIRED` em `PASS` comprovado e permitindo que alvos seguros alcancem **100.0% PASS** (8/8).

**Independent Test**: Executar uma avaliação completa sobre o código da própria aplicação (`app/`) com modo DAST `active` e motor de IA configurado: comprovar que o requisito `V1.3.1` é avaliado com `PASS` pelo `AIEvaluatorAgent`, que a métrica consolidada atinge `100.0% PASS`, `0 INCONCLUSIVE` e `0 MANUAL_REQUIRED`, e que se a IA for desconfigurada o veredito para `V1.3.1` permanece `MANUAL_REQUIRED`.

### Tests for User Story 3

- [X] T014 [P] [US3] Criar testes unitários em `tests/test_ai_evaluator.py` validando: (a) execução de `run_ai_evaluation` em `app/aci/ai_aci.py` com simulação de resposta estruturada JSON; (b) comportamento do `AIEvaluatorAgent` quando a IA está configurada (emissão de `PASS` com evidências e confiança alta); (c) fallback para `MANUAL_REQUIRED` quando `is_configured() == False`
- [X] T015 [P] [US3] Adicionar testes de integração fim a fim em `tests/test_pipeline_integration.py` validando a matriz completa de vereditos: Somente SAST (`12.5% PASS`), SAST + ZAP Baseline (`50.0% PASS`), SAST + ZAP Active sem IA (`87.5% PASS` / 1 `MANUAL_REQUIRED`) e SAST + ZAP Active com IA habilitada (**`100.0% PASS`** / 8 `PASS`, 0 `INCONCLUSIVE`, 0 `MANUAL_REQUIRED`)

### Implementation for User Story 3

- [X] T016 [US3] Implementar a função ACI `run_ai_evaluation` em `app/aci/ai_aci.py` para inspecionar arquivos de rotas, templates e módulos de segurança no workspace alvo, aplicar truncamento de contexto (máximo 4.000 caracteres conforme o Princípio III SWE-agent), construir prompt estruturado para o ASVS V1.3.1 solicitando retorno estrito em JSON (`verdict`, `confidence`, `rationale`, `evidence_snippets`), e registrar a invocação em `ToolCall` com payload sanitizado
- [X] T017 [US3] Criar a classe `AIEvaluatorAgent` em `app/agents/ai_evaluator_agent.py` herdando da arquitetura de agentes, instanciando `AISecretStore` para obter o modelo e credenciais em memória, delegando a inspeção para `ai_aci.run_ai_evaluation` e gravando o achado em `Finding` com `tool_name="ai_evaluator"`
- [X] T018 [US3] Atualizar `OrchestratorAgent` em `app/agents/orchestrator.py` para incluir a etapa `StepName.AI_EVALUATION`, executando `AIEvaluatorAgent` após a etapa DAST para os requisitos que contêm `"ai_evaluator"` em `config/req_tool_mapping.yaml`, emitindo eventos de progresso via Server-Sent Events (`run_stream`)
- [X] T019 [US3] Atualizar `VerdictAgent` em `app/agents/verdict_agent.py` para processar evidências conjuntas: quando o requisito exigir `ai_evaluator` (ex.: `V1.3.1`) e o `AIEvaluatorAgent` emitir `PASS` sem achados impeditivos do Semgrep, consolidar o veredito final como `PASS` com confiança `HIGH`; caso contrário ou se a IA não estiver configurada, manter o veredito `MANUAL_REQUIRED`
- [X] T020 [P] [US3] Atualizar `templates/index.html` e `static/app.js` para renderizar o indicador da etapa "Avaliação com IA (AI Evaluator)" no painel de progresso e exibir no modal de detalhes do requisito a justificativa emitida pelo agente de IA e os trechos de evidência analisados

**Checkpoint**: User Story 3 concluída — o avaliador com IA resolve requisitos qualitativos e atinge 100.0% PASS em alvo seguro.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verificação integrada de qualidade, testes automatizados, sanitização de segurança e integridade de artefatos.

- [X] T021 Executar a suíte completa de testes automatizados (`pytest -v`) validando cobertura das 3 User Stories, garantindo 100% de testes aprovados sem regressões
- [X] T022 [P] Executar o scanner estático Semgrep (`semgrep scan --config config/semgrep_rules app/`) garantindo 0 achados de segurança no código desenvolvido
- [X] T023 Validar manualmente os cenários do guia rápido [`quickstart.md`](./quickstart.md): bloqueio DAST 403, salvamento de credencial mascarada e execução da autoavaliação 100.0% PASS
- [X] T024 Verificar que os diretórios históricos `specs/001-asvs-v1-assessment/` e `specs/002-zap-dast-integration/` permaneceram rigorosamente intocados e que `.specify/feature.json` aponta para `specs/003-ai-evaluator-and-dast-guardrails`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Inicia imediatamente (`T001`).
- **Foundational (Phase 2)**: Depende da Phase 1 (`T002`–`T004`) — bloqueia o início de US2 e US3.
- **User Story 1 (Phase 3 - P1 🎯 MVP)**: Pode iniciar em paralelo à Phase 2 (`T005`–`T008`) por focar no guardrail DAST (independe de segredos de IA).
- **User Story 2 (Phase 4 - P1)**: Depende da Phase 2 (`T009`–`T013`) — implementa a gestão de credenciais e endpoints de IA.
- **User Story 3 (Phase 5 - P2)**: Depende da Phase 4 (`T014`–`T020`) — integra o agente de IA ao pipeline e vereditos.
- **Polish (Phase 6)**: Depende da conclusão de todas as User Stories (`T021`–`T024`).

### Parallel Opportunities

- `T003` (`models.py`) e `T004` (`ai_aci.py`) podem rodar em paralelo após `T002`.
- `T005` (`tests/test_dast_guardrail.py`) e `T007` (`templates/index.html`) podem rodar em paralelo com `T006`.
- `T009` (`tests/test_ai_secrets.py`) e `T010` (`tests/test_ai_api.py`) podem rodar em paralelo.
- `T014` (`tests/test_ai_evaluator.py`) e `T015` (`tests/test_pipeline_integration.py`) podem rodar em paralelo.

---

## Parallel Example: User Story 1 & User Story 2

```bash
# Paralelizar testes e implementação do Guardrail DAST (US1) e Armazenamento de Segredos (US2):
Task T005: "Criar testes de rejeição HTTP 403 em tests/test_dast_guardrail.py"
Task T009: "Criar testes unitários de zero-leakage em tests/test_ai_secrets.py"

# Paralelizar frontend DAST e frontend Painel de IA:
Task T007: "Atualizar layout e foco acessível do checkbox DAST em templates/index.html"
Task T012: "Adicionar Card de Configuração de IA em templates/index.html"
```

---

## Implementation Strategy

### MVP First (User Story 1 - Guardrail DAST)

1. Concluir Phase 1 (`T001`) e Phase 2 (`T002`–`T004`).
2. Concluir Phase 3 — User Story 1 (`T005`–`T008`).
3. **STOP & VALIDATE**: Testar o bloqueio DAST na UI e via API REST (`HTTP 403`), garantindo conformidade legal e operacional imediata.

### Incremental Delivery

1. **Incremento Guardrail DAST (`Phase 3 - US1`)**: Bloqueio cliente/servidor mandatário sem consentimento.
2. **Incremento Gestão de IA Segura (`Phase 4 - US2`)**: Configuração Write-Only, mascaramento `"••••••••"` e teste prévio de conexão (`POST /api/ai/test-connection`).
3. **Incremento Avaliador com IA (`Phase 5 - US3`)**: Agente `AIEvaluatorAgent`, resolução automatizada de `V1.3.1` e alcance de **`100.0% PASS`** na autoavaliação.
4. **Validação Final (`Phase 6`)**: Testes automatizados completos, Semgrep e preservação histórica dos specs.

