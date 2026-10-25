# Especificação de Funcionalidade (SDD Spec) — Feature 024: Correção da Autoavaliação da Ferramenta e Sincronismo SAST/DAST no Orchestrator

**Identificador**: `024-fix-self-check-and-dast-orchestrator`  
**Título**: Correção da Autoavaliação da Própria Ferramenta (`app/`), Elevação do Timeout de Execução e Sincronismo de Estados SSE no Stepper  
**Autor**: `sdd-conductor`  
**Status**: Planejado (Aprovado no Gate 1)  
**Versão Alvo**: `v024` (UI Version `024`)  
**Princípios Constitucionais Aplicáveis**: I (TDD), III (Arquitetura de Agentes e Consistência de Estado), IV (Segurança e Guardrails ACI/DAST), V (Fluent 2 e Acessibilidade).

---

## 1. Contexto e Problema

Ao acionar o botão **"Autoavaliar Própria Ferramenta (app/)"** (`#self-check-btn`), a avaliação falhava na etapa **2. SAST (Semgrep)** e ficava travada em *"Em execução..."* na etapa **3. DAST (OWASP ZAP)**.

### Causas Raízes Identificadas:
1. **Frontend (`static/app.js`)**:
   - Com a implementação da Feature 022 (`directory_upload`), os elementos `<option value="workspace_path">` e o input `#workspace-subpath` foram removidos da interface visual.
   - O botão `selfCheckBtn` tentava definir `sourceSelect.value = "workspace_path"` (inexistente) e `pathInput.value = "app"` (nulo), e em seguida invocava `submitAssessmentForm()`.
   - Como resultado, o formulário executava o fluxo de `directory_upload`, enviando os arquivos que estivessem selecionados no seletor de diretório local (ou falhava caso nada estivesse selecionado), em vez de direcionar a análise para a pasta `app/` do repositório.
2. **Backend (`app/agents/orchestrator.py`)**:
   - As etapas SAST e DAST rodam em concorrência via `asyncio.gather(_run_sast(), _run_dast())` envelopadas por `asyncio.wait_for(..., timeout=inp.stage_timeout_sec)`.
   - O timeout padrão de 90 segundos (`stage_timeout_sec = 90.0`) era insuficiente para varreduras mais densas (Semgrep executando regras em múltiplos arquivos simultaneamente a um Spider + Active Scan no ZAP).
   - Ao ocorrer `TimeoutError` ou exceção dentro do `gather`, o bloco genérico de tratamento capturava o erro e emitia evento SSE de `FAILED` apenas para `current_stage` (que estava registrado como `SAST`). O estágio `DAST` (que já havia emitido `STARTED` / *"Em execução..."*) nunca recebia evento de conclusão ou falha, permanecendo eternamente com spinner ativo no Stepper do Fluent UI.

---

## 2. Requisitos Funcionais (FR)

- **FR-001**: O botão `#self-check-btn` ("Autoavaliar Própria Ferramenta (app/)") DEVE disparar uma requisição assíncrona desacoplada diretamente para `POST /api/runs` com JSON `{ "source_type": "workspace_path", "workspace_subpath": "app", "target_url": <url_ou_null>, "zap_authorized": true, "zap_mode": "active" }`.
- **FR-002**: Se o OWASP ZAP estiver ONLINE, a autoavaliação deve definir `target_url` para a origem local (`window.location.origin || "http://localhost:8000"`) e `zap_mode="active"`.
- **FR-003**: Se o OWASP ZAP estiver OFFLINE, a autoavaliação deve definir `target_url = null` e notificar o usuário de que a avaliação executará em modo SAST + IA, sem tentar submeter varredura dinâmica a um daemon inexistente.
- **FR-004**: O timeout padrão de estágios concorrentes no `OrchestratorAgent` (`stage_timeout_sec`) DEVE ser elevado de 90.0s para 180.0s.
- **FR-005**: Ao ocorrer `TimeoutError` ou qualquer falha não tratada durante `asyncio.gather(_run_sast(), _run_dast())`, o `OrchestratorAgent` DEVE emitir explicitamente eventos de `stage_status="FAILED"` tanto para o `SAST` quanto para o `DAST` (se o DAST tiver sido acionado), garantindo que nenhum nó do Stepper fique preso no estado *"Em execução..."*.
- **FR-006**: A constante de versão visual da aplicação DEVE ser atualizada para `APP_UI_VERSION = "024"`.

---

## 3. Requisitos Não-Funcionais (NFR)

- **NFR-001 (Confinamento e Segurança ACI - Princípio IV)**: A autoavaliação com `workspace_subpath="app"` deve ser confinada à raiz do projeto por `resolve_and_confine_path`.
- **NFR-002 (Consistência de Estado e UX - Princípio III e V)**: O Stepper visual não deve conter etapas órfãs ou estados inconsistentes em caso de erro ou cancelamento.
- **NFR-003 (TDD - Princípio I)**: Todo o comportamento de sincronismo de falhas e disparo direto do self-check deve ser coberto por testes automatizados antes da liberação.

---

## 4. Cenários de Teste (Given / When / Then)

### Cenário 1: Sincronismo de Falha Concorrente no Orchestrator
- **Given** uma execução de avaliação onde SAST e DAST estão ativos,
- **When** o `asyncio.gather` dispara um `TimeoutError` ou falha de execução,
- **Then** eventos SSE de status `FAILED` devem ser emitidos tanto para `SAST` quanto para `DAST`,
- **And** a entidade `Run` deve ser atualizada para `status="FAILED"`.

### Cenário 2: Acionamento da Autoavaliação Desacoplada
- **Given** que o usuário clica no botão `#self-check-btn`,
- **When** a requisição é transmitida,
- **Then** a requisição deve ser enviada como JSON `POST /api/runs` com `source_type="workspace_path"` e `workspace_subpath="app"`,
- **And** não deve ser afetada por arquivos selecionados no componente `#source-directory`.

