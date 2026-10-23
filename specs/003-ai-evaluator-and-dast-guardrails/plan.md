# Implementation Plan: Avaliador com IA (AI Evaluator Agent), Configuração Segura Write-Only e Guardrail Mandatório de DAST

**Branch**: `003-ai-evaluator-and-dast-guardrails` | **Date**: 2026-10-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-ai-evaluator-and-dast-guardrails/spec.md`

## Summary

Implementar a terceira iteração do pipeline de avaliação de segurança ASVS V1 L1 (`003-ai-evaluator-and-dast-guardrails`) com três objetivos arquiteturais:
1. **Bloqueio Mandatório de Execução DAST sem Autorização**: Impedir preventivamente (na UI via validação com foco e alerta visual acessível, e no backend via HTTP 403 Forbidden em `POST /api/runs`) qualquer disparo de avaliação que informe URL alvo sem a marcação prévia e explícita do termo de autorização legal para testes dinâmicos.
2. **Gerenciamento Seguro de Credenciais de IA (Write-Only & Zero-Leakage)**: Desenvolver o singleton em memória `AISecretStore` (`app/core/ai_secrets.py`) e endpoints de gerenciamento (`GET /api/ai/status`, `POST /api/ai/config`, `POST /api/ai/test-connection`). A chave de API jamais é gravada em banco SQLite (`asvs.db`), audit logs, relatórios JSON/HTML ou retornada em respostas REST (retornando apenas `"key_masked": "••••••••"`).
3. **8º Agente Especializado: `AIEvaluatorAgent` e ACI de IA (`app/aci/ai_aci.py`)**: Integrar um agente especialista assistido por modelo de linguagem para avaliar requisitos qualitativos e contextuais (notadamente `V1.3.1` referente a sanitização de HTML rico/WYSIWYG e autoescape em templates). Com essa integração, projetos seguros (como o próprio `app/`) convertem o veredito de `MANUAL_REQUIRED` em `PASS` fundamentado com evidência técnica, elevando a taxa de conformidade da ferramenta de `87.5%` para **`100.0% PASS`** (`8/8 PASS`).

## Technical Context

**Language/Version**: Python 3.12 + HTML5 / JavaScript (ES2022) / CSS3 (Fluent 2 Design Tokens)

**Primary Dependencies**: `fastapi`, `uvicorn`, `sqlmodel`, `pydantic`, `pandas`, `httpx`, `sse-starlette`, `jinja2` (`autoescape=True`), `pyyaml`, `semgrep` (CLI), OWASP ZAP Daemon REST API (`ghcr.io/zaproxy/zaproxy:stable`), Google Generative AI / Gemini API (`gemini-2.0-flash`, `gemini-1.5-pro` via HTTP REST/httpx), `@fluentui/web-components` & `@fluentui/tokens` (CDN)

**Storage**: SQLite (`asvs.db`) via SQLModel para entidades persistentes (`Run`, `Finding`, `ToolCall`); `AISecretStore` estritamente em memória volátil de processo para credenciais sensíveis (`api_key`), com fallback transparente para variáveis de ambiente (`AI_MODEL_API_KEY`, `AI_MODEL_NAME`)

**Testing**: `pytest`, `pytest-asyncio`, `httpx` (`MockTransport` / `TestClient`)

**Target Platform**: Linux Server + Docker & Docker Compose (`asvs-owasp-zap`)

**Project Type**: Web Application + Multi-Agent Security Verification Pipeline (SAST/DAST/AI)

**Performance Goals**: Teste de conectividade com IA (`POST /api/ai/test-connection`) com timeout de `5.0s` e métrica de latência em milissegundos; análise estática e contextual de `V1.3.1` pelo `AIEvaluatorAgent` em `< 10s`

**Constraints**: Preservar rigorosamente intocados os diretórios `specs/001-asvs-v1-assessment/` e `specs/002-zap-dast-integration/`; conformidade absoluta com a Constituição v1.2.0 (Zero-Leakage de credenciais e autorização obrigatória de DAST)

**Scale/Scope**: 8 requisitos avaliáveis de `V1 L1`, 6 requisitos integrados SAST+DAST (`V1.2.1`–`V1.2.5`, `V1.5.1`), 1 requisito SAST puro (`V1.3.2`), 1 requisito assistido por IA (`V1.3.1`)

## Constitution Check

*GATE: Verificação em relação à Constituição v1.2.0 do projeto ASVS-Self-Assesment-Tool.*

| Princípio Constitucional (`v1.2.0`) | Status Pré-Pesquisa | Status Pós-Design (Fase 1) | Evidência no Plano / Artefatos |
| :--- | :---: | :---: | :--- |
| **I. Domínio Normativo, Escopo Restrito (V1 L1) e Referências** | ✅ PASS | ✅ PASS | O escopo permanece restrito aos 8 requisitos avaliáveis de `V1 L1`, e o catálogo de 345 requisitos permanece intacto e somente leitura. |
| **II. Modelo de Veredito Baseado em Evidência Positiva e Cobertura Obrigatória** | ✅ PASS | ✅ PASS | O `AIEvaluatorAgent` emite veredito fundamentado com trechos de código e justificativa técnica para `V1.3.1`. Se a IA estiver desconfigurada, preserva-se estritamente `MANUAL_REQUIRED`. |
| **III. Arquitetura Multiagente Orientada a ACI (SWE-agent)** | ✅ PASS | ✅ PASS | O 8º agente especializado (`AIEvaluatorAgent`) opera via ACI estruturada (`app/aci/ai_aci.py`), com truncamento estrito de contexto (máx. 4.000 chars), registro em `ToolCall` e retorno tipado `ACIResponse`. |
| **IV. Segurança da Própria Ferramenta (INEGOCIÁVEL)** | ✅ PASS | ✅ PASS | **Write-Only**: `AISecretStore` mantém credenciais apenas em memória volátil; chaves nunca aparecem em respostas JSON, audit logs ou HTML exportado. **DAST Guardrail**: rejeição com HTTP 403 no backend e bloqueio visual acessível na UI para URLs sem autorização explícita. |
| **V. Stack Técnica Padronizada e Design System Fluent 2** | ✅ PASS | ✅ PASS | Novo painel colapsável de IA estilizado com Fluent 2 Tokens, feedback reativo de latência/status e acessibilidade WCAG 2.2 AA (`aria-live="polite"`). |
| **VI. Seeds Normativos e Mapeamento Versionado de Regras** | ✅ PASS | ✅ PASS | Atualização declarativa em `config/req_tool_mapping.yaml` associando a ferramenta `ai_evaluator` ao requisito `V1.3.1`. |

## Design Técnico Detalhado (`003-ai-evaluator-and-dast-guardrails`)

### 1. Camada de Segurança de Segredos em Memória (`app/core/ai_secrets.py`)

- **Classe Singleton `AISecretStore`**:
  - Armazena `_api_key: str | None` e `_model_name: str | None` exclusivamente em variáveis privadas na memória do processo.
  - Inicialização com leitura opcional de fallback de variáveis de ambiente:
    - `os.environ.get("AI_MODEL_API_KEY")`
    - `os.environ.get("AI_MODEL_NAME", "gemini-2.0-flash")`
  - Método `set_credentials(model_name: str, api_key: str) -> None`:
    - Valida comprimentos mínimos e atualiza as variáveis voláteis.
  - Método `is_configured() -> bool`:
    - Retorna `True` se `bool(self._api_key and self._model_name)`.
  - Método `get_masked_status() -> dict[str, Any]`:
    - Retorna `{"configured": bool, "model_name": str | None, "key_masked": "••••••••" if configured else None, "provider": "gemini"}`.
    - **Garantia**: sob nenhuma circunstância a chave real é incluída neste retorno.
  - Método `get_api_key_internal() -> str | None`:
    - Método interno restrito ao cliente HTTP/ACI de IA.
  - Proteção de `__repr__` e `__str__`:
    - Sobrescritos para retornar `<AISecretStore configured=... model=...>` evitando vazamento acidental em depuradores ou logs.

### 2. ACI de IA e Agente Avaliador (`app/aci/ai_aci.py` e `app/agents/ai_evaluator_agent.py`)

- **Camada ACI (`app/aci/ai_aci.py`)**:
  - `check_ai_connectivity(model_name, api_key, http_client, timeout_sec=5.0) -> dict[str, Any]`:
    - Envia requisição POST leve para o endpoint de inferência (`generateContent` da API do Gemini ou similar) com prompt trivial (`"Respond with OK"`).
    - Retorna `{ok: bool, model_name: str, latency_ms: int, message: str}` sanitizando qualquer detalhe que possa conter a chave.
  - `run_ai_evaluation(session, run_id, req_id, source_path, model_name, api_key, http_client, timeout_sec=20.0) -> ACIResponse[dict]`:
    - Coleta os arquivos de código relevantes do workspace (rotas Jinja2, inicialização FastAPI, dependências em `pyproject.toml` ou `requirements.txt`).
    - Aplica truncamento rígido (SWE-agent context budget) limitando o contexto a 4.000 caracteres.
    - Envia prompt estruturado com instruções normativas de ASVS V1.3.1 (verificar se há sanitização de HTML rico/WYSIWYG e autoescape habilitado).
    - Exige retorno em formato JSON estrito:
      ```json
      {
        "verdict": "PASS" | "FAIL" | "INCONCLUSIVE",
        "confidence": "HIGH" | "MEDIUM" | "LOW",
        "rationale": "...",
        "evidence_snippets": ["..."]
      }
      ```
    - Registra a invocação no banco de dados como `ToolCall` (com payload sanitizado sem a chave de API) e retorna `ACIResponse`.

- **Agente `AIEvaluatorAgent` (`app/agents/ai_evaluator_agent.py`)**:
  - Implementa a interface padrão de agentes do pipeline (`evaluate_requirement(session, run_id, req_id, source_path)`).
  - Verifica se o modelo está configurado via `AISecretStore`.
  - Se configurado:
    - Executa `ai_aci.run_ai_evaluation(...)`.
    - Persiste o achado estruturado em `Finding` com `tool_name="ai_evaluator"` e o veredito emitido.
  - Se não configurado:
    - Registra `Finding` com veredito `MANUAL_REQUIRED` e justificativa: *"Provedor de IA não configurado para avaliação automatizada de V1.3.1. Requer inspeção humana ou configuração do modelo de IA."*

### 3. Integração no Pipeline (`OrchestratorAgent`, `VerdictAgent` e `config/req_tool_mapping.yaml`)

- Em `config/req_tool_mapping.yaml`:
  - Atualizar o mapeamento de `V1.3.1`:
    ```yaml
    - req_id: "V1.3.1"
      tools: ["semgrep", "ai_evaluator"]
      semgrep_rules:
        - "asvs-v1-3-1-html-sanitization"
      ai_evaluation_prompt: "asvs_v1_3_1_sanitization"
      description: "Verificação de sanitização contextual de HTML rico / autoescape em templates"
    ```
- Em `app/agents/orchestrator.py`:
  - Adicionar a etapa `AI_EVALUATION` ao ciclo de vida da execução (`StepName.AI_EVALUATION`), disparada após SAST e DAST para requisitos que exigem `ai_evaluator`.
  - Notificar progresso via Server-Sent Events (`run_stream`).
- Em `app/agents/verdict_agent.py`:
  - Avaliar evidências conjuntas:
    - Para `V1.3.1`, se `AIEvaluatorAgent` reportar `PASS` e `semgrep` não encontrar violações, o veredito consolidado de `V1.3.1` passa a ser **`PASS`** (confiança `HIGH`), com `MANUAL_REQUIRED` zerado.
    - Se a IA não estiver configurada, o veredito consolida em `MANUAL_REQUIRED`.
  - Resultado na autoavaliação da própria ferramenta (`app/`):
    - SAST (1/8 PASS) + DAST Active (6/8 PASS) + AI Evaluator (1/8 PASS) = **8/8 PASS (`100.0%`)**.

### 4. Endpoints REST e Guardrail de DAST (`app/main.py`)

- **Endpoints de IA**:
  - `GET /api/ai/status`: Invoca `AISecretStore.get_instance().get_masked_status()`.
  - `POST /api/ai/config`: Recebe `AIConfigRequest(model_name, api_key)` e armazena em `AISecretStore`. Retorna status mascarado.
  - `POST /api/ai/test-connection`: Recebe payload opcional com credenciais ou utiliza as já armazenadas em `AISecretStore`. Executa teste via `ai_aci.check_ai_connectivity` e retorna `AITestConnectionResponse`.
- **Guardrail de DAST em `POST /api/runs`**:
  - Validar no parser do payload de criação de Run:
    ```python
    if req_obj.target_url and not req_obj.zap_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guardrail DAST acionado: execução dinâmica bloqueada porque o checkbox de autorização explícita não foi confirmado."
        )
    ```

### 5. Interface do Usuário (`templates/index.html` e `static/app.js`)

- Em `templates/index.html`:
  - **Painel de Configuração de IA**:
    - Seção colapsável ou card "Assistente de IA para Requisitos Qualitativos (V1.3.1)" contendo:
      - Badge de status (`#ai-status-badge`: "Não Configurado" / "Configurado: gemini-2.0-flash");
      - Campo de entrada `#ai-model-name` (default `"gemini-2.0-flash"`);
      - Campo sensível `#ai-api-key` (`type="password"`, com `autocomplete="off"` e `placeholder="Cole a chave de API..."`);
      - Botão `#ai-save-config-btn` ("Salvar Chave em Memória");
      - Botão `#ai-test-connection-btn` ("Testar Conexão com IA");
      - Banner de feedback `#ai-feedback-banner` com anúncio via `aria-live="polite"`.
    - Garantia: assim que a chave for salva, o campo de input tem seu valor limpo ou substituído por placeholder mascarado, impedindo que qualquer usuário resgate a chave.
  - **Guardrail DAST no Formulário**:
    - Adicionar `class="dast-auth-wrapper"` e estilos visuais de destaque (borda de foco vermelha dos tokens Fluent) para `#zap-authorized`.
- Em `static/app.js`:
  - Funções de gerenciamento de IA:
    - `refreshAIStatus()`: consome `GET /api/ai/status` na inicialização e atualiza o badge e labels;
    - `saveAIConfig()`: envia `POST /api/ai/config` e limpa o campo `#ai-api-key`;
    - `testAIConnection()`: envia `POST /api/ai/test-connection` e exibe latência e mensagem sanitizada no banner;
  - Bloqueio estrito no envio do formulário (`#evaluation-form.onsubmit` e `#start-run-btn.onclick`):
    - Se `#target-url` estiver preenchida e `#zap-authorized` não estiver marcado:
      - Interrompe a submissão imediatamente (`event.preventDefault()`);
      - Adiciona classe de destaque de erro e executa `.focus()` no checkbox `#zap-authorized`;
      - Exibe notificação de erro no topo da tela: *"Bloqueio de Segurança: É obrigatório aceitar o termo de autorização explícita para testes dinâmicos (DAST)."*;
  - Atualização do botão `#self-check-btn` ("Autoavaliar Própria Ferramenta"):
    - Se o daemon ZAP estiver `ONLINE`, preenche `http://localhost:8000`, marca `#zap-authorized = true` e seleciona `zap-mode = "active"`. Se estiver `OFFLINE`, desmarca e orienta o usuário.

## Project Structure

### Documentation (this feature)

```text
specs/003-ai-evaluator-and-dast-guardrails/
├── plan.md              # Este documento consolidado (/speckit.plan)
├── research.md          # Pesquisa técnica de segurança de chaves em memória e ACI de IA (Fase 0)
├── data-model.md        # Modelos Pydantic, transição de vereditos e diagrama de estados (Fase 1)
├── quickstart.md        # Roteiro de testes de bloqueio DAST e autoavaliação 100% PASS (Fase 1)
├── checklists/
│   └── requirements.md  # Checklist de conformidade da especificação (16/16 PASS)
├── contracts/
│   └── ai-evaluator-and-dast-guardrails-api.md # Contratos REST e ACI de IA e DAST Guardrails (Fase 1)
└── tasks.md             # Plano de tarefas estruturado (/speckit.tasks)
```

### Source Code (repository root)

```text
config/
└── req_tool_mapping.yaml       # Mapeamento do requisito V1.3.1 associando ["semgrep", "ai_evaluator"]
app/
├── main.py                     # Endpoints /api/ai/* e validação HTTP 403 de DAST guardrail em /api/runs
├── core/
│   └── ai_secrets.py           # Singleton AISecretStore (gestão volátil Write-Only sem vazamento)
├── aci/
│   └── ai_aci.py               # run_ai_evaluation e check_ai_connectivity com truncamento ACI
└── agents/
    ├── ai_evaluator_agent.py   # 8º agente nuclear AIEvaluatorAgent para requisitos qualitativos
    ├── orchestrator.py         # Inclusão da etapa AI_EVALUATION no fluxo do pipeline
    └── verdict_agent.py        # Consolidação de V1.3.1 como PASS baseado em evidência da IA
templates/
└── index.html                  # Painel de configuração de IA, botões de teste e destaque visual do checkbox DAST
static/
└── app.js                      # Validação de bloqueio DAST, gerenciamento seguro de chave e refresh de status de IA
tests/
├── test_ai_secrets.py          # Testes unitários de zero-leakage, mascaramento e isolamento de chaves
├── test_ai_evaluator.py        # Testes unitários do AIEvaluatorAgent e ai_aci com mock de LLM
└── test_pipeline_integration.py # Testes de integração validando bloqueio 403 e autoavaliação 100.0% PASS
```

## Complexity Tracking

Nenhuma violação à Constituição (`v1.2.0`). O armazenamento em memória atende estritamente à política de Zero-Leakage (Princípio IV), a ACI de IA preserva a arquitetura multiagente (Princípio III), e a exigência de autorização DAST reforça a segurança operacional da ferramenta (Princípio IV).
