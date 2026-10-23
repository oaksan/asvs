# Feature Specification: 004-mandatory-prerequisites-and-ai-gate

**Feature Branch / Directory**: `specs/004-mandatory-prerequisites-and-ai-gate`

**Created**: 2026-10-13

**Status**: Draft

**Constitution Reference**: ASVS-Self-Assesment-Tool Constitution v1.3.0 (Princípio IV: Segurança da Própria Ferramenta e Guardrails Operacionais)

---

## 1. Executive Summary & Objective

Esta especificação define os guardrails mandatórios e inegociáveis de inicialização do pipeline de avaliação de segurança ASVS 5.0 V1 L1:
1. **Autorização DAST Universal Incondicional**: Tornar obrigatório o aceite prévio do termo de responsabilidade de testes dinâmicos (*"Declaro que possuo autorização explícita para executar testes dinâmicos (DAST / OWASP ZAP) contra a URL alvo informada acima."*) para a submissão de **qualquer** avaliação (manual ou autoavaliação).
2. **AI Prerequisite Gate**: Bloquear incondicionalmente o início de qualquer avaliação caso o modelo de IA generativa não esteja previamente configurado em memória volátil (`AISecretStore.is_configured() == True`), garantindo que o `AIEvaluatorAgent` esteja sempre operacional para analisar contextualmente requisitos qualitativos de codificação e sanitização (V1.3.1) sem degradação para omissão humana não intencional.
3. **Preservação Zero-Leakage & Write-Only**: Garantir que as credenciais permaneçam estritamente protegidas em memória volátil, mascaradas em `"••••••••"` e jamais expostas em respostas de API REST, logs, banco SQLite ou relatórios.

---

## 2. User Scenarios & Acceptance Criteria *(mandatory)*

### User Story 1 — Bloqueio Mandatório Geral de Autorização DAST (Priority: P1 🎯 MVP)

Como operador de segurança ou auditor da ferramenta,  
Quero que o sistema exija expressamente o aceite do termo de responsabilidade de testes dinâmicos (DAST / OWASP ZAP) antes de disparar qualquer execução,  
Para que nenhuma avaliação seja iniciada sem consentimento legal formal, evitando incidentes operacionais de varredura ativa ou passiva não autorizada.

**Why this priority**: Conformidade legal e segurança operacional inegociável (Princípio IV da Constituição v1.3.0). Nenhum teste de segurança ofensivo/dinâmico pode ser acionado sem declaração explícita de autorização.

**Independent Test**:
Submeter o formulário de avaliação (com ou sem URL preenchida, via botão de início ou atalho de autoavaliação) com o checkbox `#zap-authorized` desmarcado: comprovar que a interface bloqueia o submit no cliente, destaca o container com contorno vermelho Fluent, foca o checkbox e anuncia o erro via `aria-live="polite"`. No backend, comprovar que requisição direta a `POST /api/runs` com `zap_authorized=False` é imediatamente rejeitada com `HTTP 403 Forbidden` sem criar nenhuma Run.

**Acceptance Scenarios**:

1. **Cenário 1.1 — Tentativa de submissão sem autorização DAST na UI**:
   - **Given** que o operador preencheu o formulário de Nova Avaliação ou clicou em "Autoavaliar Própria Ferramenta",
   - **And** o checkbox `#zap-authorized` está desmarcado (`checked == False`),
   - **When** o operador clica em "Iniciar Avaliação V1 L1", "Autoavaliar Própria Ferramenta" ou pressiona Enter em um input,
   - **Then** a submissão é bloqueada no cliente;
   - **And** a classe `.has-error` é aplicada ao elemento `#dast-auth-container`;
   - **And** o foco do navegador é transferido para o checkbox `#zap-authorized`;
   - **And** uma mensagem explicativa de erro é anunciada no banner `#form-feedback-banner` com `role="alert"` e `aria-live="polite"`.

2. **Cenário 1.2 — Rejeição no Backend via API REST (POST /api/runs)**:
   - **Given** uma requisição `POST /api/runs` com payload JSON contendo `zap_authorized: false` (ou ausente),
   - **When** o endpoint processa a requisição,
   - **Then** o backend responde com status `HTTP 403 Forbidden`;
   - **And** o corpo da resposta contém `detail: "Guardrail DAST acionado: É obrigatório declarar autorização explícita para testes dinâmicos antes de iniciar qualquer avaliação."`;
   - **And** nenhum registro de `Run` é persistido no banco de dados SQLite (`asvs.db`).

3. **Cenário 1.3 — Aceite do termo DAST desbloqueia a submissão**:
   - **Given** que o operador marcou o checkbox `#zap-authorized` (`checked == True`),
   - **When** o formulário é validado,
   - **Then** o guardrail DAST é satisfeito, removendo a classe `.has-error` e prosseguindo para a validação do gate de IA.

---

### User Story 2 — Gate Mandatório de Configuração de IA (AI Gate) (Priority: P1)

Como engenheiro de segurança avaliando um alvo contra o ASVS V1 L1,  
Quero que o sistema impeça o disparo do pipeline caso o provedor de IA não esteja previamente configurado com modelo e API Key válidos,  
Para que a ferramenta nunca execute avaliações incompletas onde requisitos qualitativos (como V1.3.1) fiquem órfãos de avaliação automatizada.

**Why this priority**: A integração do 8º agente (`AIEvaluatorAgent`) é nuclear para o ASVS V1 L1 (Princípio II e III). Iniciar o pipeline sem IA configurada resulta em vereditos degradados (`MANUAL_REQUIRED`), frustrando a meta de automação segura e 100% PASS.

**Independent Test**:
Acessar a ferramenta com `AISecretStore` não configurado (`is_configured() == False`). Tentar iniciar a avaliação: comprovar que o cliente impede o disparo, expande a seção de configuração de IA e posiciona o foco no input `#ai-api-key`. No backend, comprovar que requisições a `POST /api/runs` são rejeitadas com `HTTP 412 Precondition Failed` quando a IA não estiver configurada.

**Acceptance Scenarios**:

1. **Cenário 2.1 — Bloqueio no cliente quando IA não está configurada**:
   - **Given** que o endpoint `GET /api/ai/status` retornou `{configured: false}`,
   - **When** o usuário tenta submeter o formulário de avaliação,
   - **Then** a submissão é interceptada e cancelada;
   - **And** o painel colapsável `#ai-config-details` é automaticamente expandido (`open = true`);
   - **And** o campo `#ai-api-key` recebe foco visual;
   - **And** o banner `#form-feedback-banner` exibe em destaque o aviso: *"Configuração de IA obrigatória: informe o modelo e salve a API Key em memória antes de iniciar a avaliação."*.

2. **Cenário 2.2 — Rejeição no Backend com HTTP 412 Precondition Failed**:
   - **Given** que `AISecretStore.get_instance().is_configured() == False`,
   - **When** uma requisição `POST /api/runs` é enviada (mesmo com `zap_authorized: true`),
   - **Then** o backend responde com status `HTTP 412 Precondition Failed`;
   - **And** o payload JSON contém `detail: "Pré-requisito de IA não atendido: O provedor de IA generativa deve ser configurado (modelo e API Key em memória) antes de iniciar a avaliação."`;
   - **And** nenhum registro de `Run` é criado.

3. **Cenário 2.3 — Salvar a chave de IA desbloqueia o gate**:
   - **Given** que o usuário preenche `#ai-model-name` e `#ai-api-key`,
   - **When** clica em "Salvar Chave em Memória" (`POST /api/ai/config`) e a operação é bem-sucedida,
   - **Then** o status local é atualizado para `configured = true`;
   - **And** o badge `#ai-status-badge` passa a exibir `IA CONFIGURADA` com token verde Fluent;
   - **And** o gate de IA é imediatamente liberado, permitindo a submissão do formulário.

---

### User Story 3 — Gestão Segura de Credenciais, Teste de Conexão e UX Integrada (Priority: P2)

Como operador configurando o provedor de IA generativa,  
Quero poder validar a chave por meio de um teste de conexão leve antes de salvar, limpando o campo de texto puro imediatamente após o salvamento,  
Para que minhas credenciais permaneçam seguras sob a política Write-Only e eu tenha certeza da operacionalidade do modelo.

**Why this priority**: Atende aos requisitos de Zero-Leakage e usabilidade (Princípio IV da Constituição v1.3.0).

**Independent Test**:
Inserir modelo e chave no painel de IA, clicar em "Testar Conexão com IA" (verificar mensagem de latência sem expor a chave), clicar em "Salvar Chave em Memória" (verificar que o valor do input é zerado no DOM e substituído por placeholder mascarado) e comprovar que `GET /api/ai/config` ou `GET /api/ai/status` nunca expõem a chave real.

**Acceptance Scenarios**:

1. **Cenário 3.1 — Teste de conexão prévio com feedback claro**:
   - **Given** um modelo informado (`gemini-2.0-flash`) e uma chave digitada no campo `#ai-api-key`,
   - **When** o usuário clica em `#ai-test-connection-btn`,
   - **Then** uma requisição é enviada para `POST /api/ai/test-connection`;
   - **And** o banner `#ai-feedback-banner` exibe o resultado do handshake (sucesso com latência ou erro técnico higienizado) sem expor a chave em texto plano.

2. **Cenário 3.2 — Limpeza imediata no cliente pós-salvamento (Write-Only UX)**:
   - **Given** uma chave digitada no input `#ai-api-key`,
   - **When** o usuário clica em `#ai-save-config-btn`,
   - **Then** a chave é enviada com segurança via `POST /api/ai/config`;
   - **And** o valor em memória no DOM do input é imediatamente limpo (`input.value = ""`);
   - **And** o placeholder é alterado para `"•••••••• (Chave salva em memória)"`;
   - **And** o status é persistido unicamente no singleton volátil do processo backend.

---

## 3. Edge Cases & Boundary Conditions

1. **Autoavaliação da Própria Ferramenta via Botão de Atalho**:
   - O botão `#self-check-btn` ("Autoavaliar Própria Ferramenta") preenche automaticamente `app` e URL, mas DEVE respeitar rigorosamente os dois guardrails: marcar `#zap-authorized` e exigir IA previamente configurada. Se a IA não estiver configurada, o atalho abre o painel de IA e impede o início.
2. **Reinicialização do Servidor Backend**:
   - Como o armazenamento de segredos é estritamente volátil em memória (`AISecretStore`), ao reiniciar o processo, `is_configured()` volta a ser `False` (a menos que existam variáveis de ambiente `AI_MODEL_API_KEY` e `AI_MODEL_NAME`). O frontend deve detectar a desconfiguração via `GET /api/ai/status` no carregamento e bloquear a inicialização até nova configuração.
3. **Tentativa de Burlar a UI via cURL ou scripts**:
   - A validação no backend em `POST /api/runs` garante proteção incondicional: mesmo ignorando a interface web, qualquer chamada sem `zap_authorized=True` recebe `HTTP 403`, e sem IA configurada recebe `HTTP 412`.
4. **Reexecução de Avaliação Anterior (`/api/runs/{id}/rerun`)**:
   - A rota de rerun deve herdar e validar as mesmas pré-condições: a run original deve ter sido autorizada e a IA deve estar configurada no momento da reexecução.

---

## 4. Functional Requirements

- **FR-001**: O backend (`POST /api/runs`) DEVE validar que `zap_authorized == True` em toda e qualquer requisição de criação de Run, rejeitando com `HTTP 403 Forbidden` caso o flag seja `False`.
- **FR-002**: O backend (`POST /api/runs`) DEVE validar que `AISecretStore.get_instance().is_configured() == True` antes de criar a Run, rejeitando com `HTTP 412 Precondition Failed` caso a IA não esteja configurada.
- **FR-003**: O formulário web (`templates/index.html` e `static/app.js`) DEVE interceptar tentativas de submissão quando `#zap-authorized` estiver desmarcado, destacando visualmente o checkbox, transferindo o foco e anunciando o bloqueio via `aria-live="polite"`.
- **FR-004**: O formulário web DEVE interceptar tentativas de submissão quando a IA não estiver configurada, expandindo a seção colapsável de IA, focando o input de API Key e exibindo mensagem explicativa.
- **FR-005**: A função `saveAIConfig()` DEVE atualizar reativamente o estado local da aplicação e desobstruir os botões de início da avaliação imediatamente após a confirmação de sucesso do endpoint `POST /api/ai/config`.
- **FR-006**: A API Key da IA NUNCA PODE ser retornada em texto puro em endpoints REST, respostas SSE, relatórios JSON/HTML ou tabelas do banco de dados SQLite.
- **FR-007**: A suite de testes de integração (`tests/test_dast_guardrail.py`, `tests/test_ai_gate.py` e `tests/test_pipeline_integration.py`) DEVE cobrir exaustivamente as respostas `HTTP 403`, `HTTP 412` e o fluxo bem-sucedido quando ambos os pré-requisitos forem satisfeitos.

---

## 5. Measurable Success Criteria

- **SC-001**: **100% de Bloqueio sem Autorização**: Zero execuções iniciadas sem `zap_authorized=True`, tanto na UI quanto no backend.
- **SC-002**: **100% de Bloqueio sem IA**: Zero execuções iniciadas sem provedor de IA configurado em memória.
- **SC-003**: **Zero Vazamento de Credenciais**: A API Key da IA nunca aparece em respostas de rede, logs de execução ou registros do banco de dados.
- **SC-004**: **100% de Testes Aprovados**: Todos os testes automatizados da suíte (`pytest -v`) aprovados sem regressões.
- **SC-005**: **Zero Alertas no Scanner Estático**: `semgrep scan --config config/semgrep_rules app/` executado com 0 achados de segurança.

