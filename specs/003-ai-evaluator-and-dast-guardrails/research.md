# Phase 0 Research: Avaliador com IA (AI Evaluator Agent), Configuração Segura Write-Only e Guardrail DAST

**Feature**: [spec.md](./spec.md)  
**Date**: 2026-10-13  
**Status**: Completed

---

## 1. Armazenamento Volátil e Seguro de Credenciais de IA (Write-Only & Zero-Leakage)

### Contexto e Problema
A introdução do `AIEvaluatorAgent` requer uma chave de API (`api-key`) e o identificador do modelo (ex.: `gemini-1.5-pro`, `gemini-2.0-flash`). De acordo com o Princípio IV da Constituição (`v1.2.0`), chaves de API não podem ser gravadas em repositórios, banco de dados relacional (`asvs.db`), audit logs, relatórios JSON/HTML ou expostas por respostas REST.

### Decisões Técnicas

1. **Singleton `AISecretStore` em `app/core/ai_secrets.py`**:
   - As credenciais são armazenadas exclusivamente em variáveis privadas de instância na memória volátil do processo backend:
     ```python
     class AISecretStore:
         _instance = None
         def __init__(self):
             self._api_key: str | None = os.environ.get("AI_MODEL_API_KEY")
             self._model_name: str | None = os.environ.get("AI_MODEL_NAME", "gemini-2.0-flash")
     ```
   - **Prevenção de Vazamento em `__repr__` e `__str__`**:
     A classe sobrescreve representações textuais para que `print()`, `logger` ou depuradores nunca exibam a chave:
     ```python
     def __repr__(self) -> str:
         return f"<AISecretStore configured={self.is_configured()} model={self.get_model_name()}>"
     ```
   - **Método de Consulta Pública Mascarada**:
     `get_masked_status() -> dict[str, Any]` retorna:
     ```json
     {
       "configured": true,
       "model_name": "gemini-2.0-flash",
       "key_masked": "••••••••"
     }
     ```
     A chave real só é acessível via método interno protegido `get_api_key_internal()`, consumido estritamente pelo cliente HTTP/ACI de IA.

---

## 2. Teste de Conexão com Provedor de IA (`POST /api/ai/test-connection`)

### Contexto e Problema
O usuário precisa validar se a chave inserida e o modelo especificado estão operacionais antes de disparar o pipeline, sem que mensagens de erro ou logs vazem a chave de API na resposta.

### Decisões Técnicas

1. **Handshake Leve e Timeout Controlado**:
   - Endpoint: `POST /api/ai/test-connection`.
   - Se payload contiver `{model_name, api_key}`, testa as credenciais fornecidas; se payload for vazio, testa as credenciais já salvas em `AISecretStore`.
   - Dispara uma requisição de teste com prompt mínimo (`"Respond with OK"`) e `timeout=5.0s`.
   - Calcula a latência em milissegundos (`latency_ms = int((t1 - t0) * 1000)`).
   - Sanitização de Erros: em caso de exceção (`HTTPStatusError`, `ConnectError`), captura o código HTTP e a mensagem genérica sanitizada (ex.: `"Falha de autenticação (HTTP 401): verifique a chave informada."`), garantindo que URLs com query parameters ou headers que contenham a chave sejam totalmente expurgados da mensagem devolvida ao cliente.

---

## 3. Arquitetura do `AIEvaluatorAgent` e ACI de IA (`app/aci/ai_aci.py`)

### Contexto e Problema
O requisito `V1.3.1` (*Sanitização de HTML rico/WYSIWYG e políticas de renderização*) recebia `MANUAL_REQUIRED` no analisador estático por demandar julgamento contextual sobre o código. Com a IA generativa, podemos transformar essa verificação em uma decisão automatizada auditável.

### Decisões Técnicas

1. **Contrato de Entrada e Saída do Agente (`Pydantic`)**:
   - `AIEvaluatorInput`: `run_id: int`, `req_id: str` (default `"V1.3.1"`), `source_path: str`.
   - `AIEvaluatorOutput`: `run_id: int`, `req_id: str`, `verdict: Literal["PASS", "FAIL", "INCONCLUSIVE", "MANUAL_REQUIRED"]`, `confidence: Literal["HIGH", "MEDIUM", "LOW"]`, `rationale: str`, `model_used: str | None`, `evidence_snippets: list[str]`.
2. **Camada ACI (`app/aci/ai_aci.py`)**:
   - Coleta os arquivos relevantes do workspace (rotas Jinja2, módulos de sanitização, `main.py`, bibliotecas em `requirements.txt`/`pyproject.toml`).
   - Aplica truncamento rígido via `workspace_aci` (máximo 4.000 caracteres de contexto total) para preservar os princípios de ACI (SWE-agent).
   - Monta um prompt com instruções determinísticas para o modelo responder estritamente no formato JSON:
     ```json
     {
       "verdict": "PASS",
       "confidence": "HIGH",
       "rationale": "A aplicação utiliza templates Jinja2 com autoescape habilitado por padrão e não expõe endpoints de entrada de HTML rico/WYSIWYG.",
       "evidence": ["app/main.py: autoescape=True"]
     }
     ```
3. **Integração no `OrchestratorAgent` e `VerdictAgent`**:
   - No `OrchestratorAgent`, executa o `AIEvaluatorAgent` após a etapa DAST/SAST.
   - No `VerdictAgent`, para requisitos mapeados com assistência de IA (`V1.3.1`), se `AIEvaluatorAgent` reportar `PASS`, o veredito final é consolidado como `PASS` (confiança `HIGH`), elevando o veredito geral da ferramenta de `87.5% PASS` para **`100.0% PASS`**. Caso a IA não esteja configurada, mantém-se o veredito `MANUAL_REQUIRED`.

---

## 4. Bloqueio Mandatório de Início sem Autorização DAST

### Contexto e Problema
O usuário não pode ser capaz de disparar uma avaliação dinâmica sem confirmar expressamente a autorização, prevenindo ataques não intencionais contra terceiros.

### Decisões Técnicas

1. **Validação Reativa no Frontend (`static/app.js` & `templates/index.html`)**:
   - O botão `#start-run-btn` e o submit do formulário inspecionam:
     ```javascript
     if (targetUrl.length > 0 && !zapAuthCheckbox.checked) {
       ev.preventDefault();
       zapAuthCheckbox.classList.add("input-error-highlight");
       zapAuthCheckbox.focus();
       showAlert("Bloqueio de Segurança: É obrigatório aceitar o termo de autorização explícita para testes dinâmicos (DAST).", true);
       return;
     }
     ```
   - O atalho `#self-check-btn` ("Autoavaliar Própria Ferramenta") continua preenchendo os campos automaticamente e, ao definir a URL, marca explicitamente `#zap-authorized = true` apenas quando o ZAP estiver online e com consentimento, ou alerta antes da submissão.
2. **Validação Estrita no Backend (`app/main.py`)**:
   - Em `_parse_create_run_payload`:
     ```python
     if req_obj.target_url and not req_obj.zap_authorized:
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="Guardrail DAST acionado: execução dinâmica bloqueada porque o checkbox de autorização explícita não foi confirmado."
         )
     ```

