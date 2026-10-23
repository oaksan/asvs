# Research & Architectural Decisions: 004-mandatory-prerequisites-and-ai-gate

## 1. Context & Problem Statement

Na iteração `003-ai-evaluator-and-dast-guardrails`, foram introduzidos:
1. O guardrail DAST condicional: bloqueava o início de runs apenas se houvesse `target_url` preenchida sem o flag `zap_authorized=True`.
2. O 8º agente nuclear `AIEvaluatorAgent` e a gestão segura em memória volátil de credenciais de IA (`AISecretStore`), permitindo que alvos seguros atinjam 100.0% PASS. No entanto, se o operador não configurasse a IA, a ferramenta continuava permitindo o início da avaliação e caía silenciosamente no fallback `MANUAL_REQUIRED` para requisitos qualitativos como V1.3.1.

A Emenda Constitucional v1.3.0 estabeleceu dois guardrails operacionais inegociáveis adicionais:
- **Guardrail de Autorização DAST Incondicional**: O operador DEVE obrigatoriamente assinar o termo de responsabilidade de testes dinâmicos antes de qualquer execução (com ou sem URL inicial).
- **AI Prerequisite Gate**: Nenhuma avaliação pode ser iniciada se a IA não estiver configurada em memória (`is_configured() == True`), garantindo que o `AIEvaluatorAgent` nunca seja omitido por descuido.

---

## 2. Decision Matrix: Status HTTP e Códigos de Erro

| Cenário de Violação | Código HTTP | Justificativa Técnica |
| :--- | :--- | :--- |
| **Tentativa sem aceite DAST** (`zap_authorized=False`) | `403 Forbidden` | Bloqueio de autorização legal / guardrail operacional inegociável. O cliente não tem permissão para disparar o pipeline sem consentimento. |
| **Tentativa sem IA configurada** (`is_configured()=False`) | `412 Precondition Failed` | A pré-condição operacional de negócio ("Provedor de IA em memória") necessária para o pipeline multiagente não foi satisfeita. |
| **Tentativa com URL fora da allowlist** | `403 Forbidden` | Bloqueio de SSRF e segurança de rede contra alvos externos não autorizados. |
| **Tentativa com caminho fora do workspace** | `400 Bad Request` | Bloqueio de path traversal pelo guardrail de confinamento de arquivo. |

---

## 3. Arquitetura da Validação de Pré-requisitos

### 3.1 Backend (`app/main.py`)

A função `_parse_create_run_payload` atua como o **Gatekeeper** central de todas as rotas de criação de avaliação (`POST /api/runs` e `POST /api/runs/{id}/rerun`):
1. **Verificação de Autorização DAST (Incondicional)**:
   ```python
   if not req.zap_authorized:
       raise HTTPException(
           status_code=403,
           detail="Guardrail DAST acionado: É obrigatório declarar autorização explícita para testes dinâmicos antes de iniciar qualquer avaliação.",
       )
   ```
2. **Verificação do AI Prerequisite Gate**:
   ```python
   if not AISecretStore.get_instance().is_configured():
       raise HTTPException(
           status_code=412,
           detail="Pré-requisito de IA não atendido: O provedor de IA generativa deve ser configurado (modelo e API Key em memória) antes de iniciar a avaliação.",
       )
   ```
3. Apenas após a passagem por esses dois gates e validação de paths e allowlist, a entidade `Run` é persistida no banco SQLite e a tarefa assíncrona do `OrchestratorAgent` é disparada.

### 3.2 Frontend Reativo (`static/app.js` e `templates/index.html`)

1. **Rastreamento de Estado da IA**:
   - `state.aiConfigured` é mantido como booleano reativo.
   - No carregamento inicial da página (`refreshAIStatus`), consulta `GET /api/ai/status`.
   - Se `configured == true`: atualiza badge `#ai-status-badge` para "IA CONFIGURADA" e `state.aiConfigured = true`.
   - Se `configured == false`: `state.aiConfigured = false`.
   - Ao salvar (`saveAIConfig`): atualiza imediatamente `state.aiConfigured = true` e limpa mensagens de bloqueio.
2. **Interceptação no Submit (`submitAssessmentForm`)**:
   - Verifica `!state.aiConfigured`:
     - Se falso: cancela submissão, abre `<details id="ai-config-details">`, posiciona foco em `#ai-api-key`, e exibe aviso enfático com token Fluent no banner de feedback.
   - Verifica `!zapAuth`:
     - Se falso: cancela submissão, adiciona `.has-error` em `#dast-auth-container`, foca `#zap-authorized` e anuncia via `aria-live="polite"`.
3. **Autoavaliação da Própria Ferramenta (`#self-check-btn`)**:
   - Marca automaticamente `#zap-authorized = true` e preenche `app` e URL do daemon.
   - Verifica se a IA está configurada: se não estiver, expande o painel de IA, foca a chave e solicita ao usuário que salve a chave antes de prosseguir com a autoavaliação.

