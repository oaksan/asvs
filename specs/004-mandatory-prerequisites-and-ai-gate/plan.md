# Implementation Plan: 004-mandatory-prerequisites-and-ai-gate

**Branch**: `004-mandatory-prerequisites-and-ai-gate` | **Date**: 2026-10-13 | **Spec**: [specs/004-mandatory-prerequisites-and-ai-gate/spec.md](spec.md)

**Input**: Feature specification from `specs/004-mandatory-prerequisites-and-ai-gate/spec.md`

---

## 1. Summary

A feature **004-mandatory-prerequisites-and-ai-gate** estabelece a obrigatoriedade incondicional de dois pré-requisitos operacionais e de segurança antes de permitir a submissão ou criação de qualquer avaliação (Run) no ASVS-Self-Assesment-Tool:
1. **Autorização DAST Universal**: O aceite explícito do termo de responsabilidade de testes dinâmicos (`zap_authorized=True`) passa a ser mandatório em toda requisição, evitando qualquer execução acidental ou não autorizada.
2. **AI Prerequisite Gate**: A ferramenta exige que o provedor de IA generativa esteja ativamente configurado em memória (`AISecretStore.is_configured() == True`), impedindo o disparo de avaliações que resultariam em omissão não assistida de requisitos qualitativos (como V1.3.1).

---

## 2. Technical Context

- **Language/Version**: Python 3.12 / 3.13
- **Primary Dependencies**: FastAPI, SQLModel, Pydantic v2, HTTPX, Jinja2
- **Storage**: SQLite (`asvs.db`) com armazenamento de segredos estritamente volátil em memória (`app/core/ai_secrets.py`)
- **Testing**: pytest, pytest-asyncio, FastAPI TestClient
- **Target Platform**: Linux (x86_64), container Docker
- **Frontend**: HTML5, Vanilla JavaScript reativo, Design System Fluent 2 Web Components e tokens CSS oficiais
- **Constraints**:
  - Zero-Leakage de credenciais de IA (Write-Only em memória);
  - Preservação estrita dos diretórios de features anteriores (`specs/001-asvs-v1-assessment/`, `specs/002-zap-dast-integration/`, `specs/003-ai-evaluator-and-dast-guardrails/`).

---

## 3. Constitution Check (v1.3.0)

- **Princípio I (Escopo e Domínio Normativo)**: Mantém inalterados os 8 requisitos normativos de V1 L1 e o catálogo completo de 345 requisitos.
- **Princípio II (Modelo de Vereditos e Cobertura)**: O AI Gate garante que o `AIEvaluatorAgent` esteja sempre habilitado para avaliar `V1.3.1`, permitindo atingir 100.0% PASS em alvos seguros.
- **Princípio III (Arquitetura Multiagente)**: Preserva os 8 agentes especializados e as ACIs estruturadas.
- **Princípio IV (Segurança da Própria Ferramenta e Guardrails Operacionais)**:
  - Aceite DAST incondicional validado na UI e no backend com `HTTP 403 Forbidden`;
  - AI Gate validado na UI e no backend com `HTTP 412 Precondition Failed`;
  - Política Write-Only de chaves de API rigorosamente mantida.
- **Princípio V (Stack Técnica e Fluent 2)**: Feedback acessível via `aria-live="polite"`, classes Fluent de contorno e foco em inputs.

---

## 4. Project Structure & Changes Layout

### Documentation & Specs (this feature)
```text
specs/004-mandatory-prerequisites-and-ai-gate/
├── spec.md              # Requisitos e critérios de aceite
├── plan.md              # Este plano técnico de arquitetura
├── research.md          # Decisões arquiteturais e matriz de erros HTTP
├── data-model.md        # Modelos Pydantic e schemas de erro
├── quickstart.md        # Guia rápido de validação manual e cURL
└── contracts/
    └── runs_preconditions_contract.yaml  # Contrato OpenAPI dos pré-requisitos
```

### Source Code Impact
```text
app/
├── main.py              # Atualização de _parse_create_run_payload com validações 403 e 412
templates/
└── index.html           # Ajuste de layout e mensagens dos pré-requisitos
static/
└── app.js               # Validação síncrona pré-submit, expansão de painel IA e foco acessível
tests/
├── test_dast_guardrail.py  # Atualização para validação incondicional DAST
├── test_ai_gate.py         # Novos testes unitários e de contrato do gate de IA (412 vs 202)
└── test_pipeline_integration.py # Alinhamento das fixtures de teste
```

---

## 5. Implementation Phases & Architectural Decisions

### Phase 1: Backend Guardrails (`app/main.py`)
1. Modificar a função `_parse_create_run_payload`:
   - **Validação DAST**: Remover a condicional de `if target_url:`. Avaliar diretamente:
     ```python
     if not req.zap_authorized:
         raise HTTPException(
             status_code=403,
             detail="Guardrail DAST acionado: É obrigatório declarar autorização explícita para testes dinâmicos antes de iniciar qualquer avaliação.",
         )
     ```
   - **Validação AI Gate**:
     ```python
     if not AISecretStore.get_instance().is_configured():
         raise HTTPException(
             status_code=412,
             detail="Pré-requisito de IA não atendido: O provedor de IA generativa deve ser configurado (modelo e API Key em memória) antes de iniciar a avaliação.",
         )
     ```
2. Garantir que a rota de rerun (`/api/runs/{id}/rerun`) execute o mesmo gatekeeper.

### Phase 2: Frontend Reativo e Acessibilidade (`templates/index.html` e `static/app.js`)
1. Em `static/app.js`:
   - Atualizar a função `submitAssessmentForm`:
     - Obter `state.aiConfigured` (atualizado por `refreshAIStatus` e `saveAIConfig`).
     - Se `!state.aiConfigured`:
       - Abrir a seção `<details id="ai-config-details">` (`details.open = true`).
       - Focar o campo `#ai-api-key`.
       - Exibir mensagem no banner `#form-feedback-banner` com destaque Fluent.
       - Interromper a execução (`return`).
     - Se `!zapAuth`:
       - Aplicar classe `.has-error` em `#dast-auth-container`.
       - Focar o checkbox `#zap-authorized`.
       - Exibir mensagem no banner `#form-feedback-banner`.
       - Interromper a execução (`return`).
   - Atualizar a ação de `#self-check-btn`:
     - Marcar `#zap-authorized.checked = true`.
     - Validar `state.aiConfigured`: se falso, abrir o painel de IA e orientar o operador.
   - Em `saveAIConfig`:
     - Ao salvar com sucesso, definir `state.aiConfigured = true` e atualizar o badge.

### Phase 3: Testes Automatizados e Cobertura
1. **`tests/test_dast_guardrail.py`**:
   - Atualizar o teste de SAST-only para validar que mesmo sem `target_url`, requisições com `zap_authorized=False` falham com `HTTP 403`.
   - Validar que com `zap_authorized=True` (e IA mock configurada), a requisição é aceita.
2. **`tests/test_ai_gate.py`**:
   - Teste 1: `POST /api/runs` sem IA configurada retorna `HTTP 412 Precondition Failed`.
   - Teste 2: Configurar IA via `POST /api/ai/config` e comprovar que `POST /api/runs` (com `zap_authorized=True`) responde com `HTTP 202`.
   - Teste 3: Reexecução (`POST /api/runs/{id}/rerun`) falha com 412 se a IA for desconfigurada em memória.
3. **`tests/test_pipeline_integration.py`**:
   - Ajustar as chamadas auxiliares para incluir `zap_authorized=True` e configurar a IA mock antes dos testes de pipeline.

---

## 6. Verification & Quality Gates

1. **Testes Unitários e de Contrato**: `pytest -v tests/test_dast_guardrail.py tests/test_ai_gate.py`.
2. **Testes de Integração Fim a Fim**: `pytest -v tests/test_pipeline_integration.py` confirmando os cenários de 12.5%, 50.0%, 87.5% e 100.0% PASS.
3. **Análise Estática de Código**: `semgrep scan --config config/semgrep_rules app/` com 0 achados.
4. **Verificação de Integridade**: Comprovar que `specs/001-asvs-v1-assessment/`, `specs/002-zap-dast-integration/` e `specs/003-ai-evaluator-and-dast-guardrails/` permanecem intocados.

