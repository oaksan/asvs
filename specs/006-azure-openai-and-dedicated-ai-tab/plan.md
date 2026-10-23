# Implementation Plan: 006-azure-openai-and-dedicated-ai-tab

**Branch**: `006-azure-openai-and-dedicated-ai-tab`  
**Spec Reference**: [`specs/006-azure-openai-and-dedicated-ai-tab/spec.md`](spec.md)  
**Status**: Ready for Tasks / TDD  
**Constitution Reference**: Princípio IV (Segurança e Isolamento de Chaves) e Princípio V (Fluent 2)

---

## 1. Technical Context & Scope

- **Linguagens e Tecnologias**: Python 3.12, FastAPI, Pydantic v2, HTTPX assíncrono, HTML5, Jinja2, JavaScript ES6, Microsoft Fluent 2 Web Components.
- **Arquivos Afetados**:
  1. `app/core/ai_secrets.py`: Suporte a `resource_name`, `deployment_id`, `api_version` e `provider="azureopenai"`.
  2. `app/aci/ai_aci.py`: Implementação do client HTTP para Azure OpenAI (healthcheck, chat playground e avaliação V1.3.1).
  3. `app/models.py`: Novos schemas `AIChatTestRequest`, `AIChatTestResponse` e extensão de `AIConfigRequest`.
  4. `app/main.py`: Novo endpoint `POST /api/ai/chat-test` e atualização de `POST /api/ai/config`.
  5. `templates/index.html`: Adição da aba `#tab-ai-config`, remoção do formulário inline da Aba 1 e inserção da nova seção `#panel-ai-config`.
  6. `static/app.js`: Lógica de alternância de abas, formulário do Azure OpenAI e envio/renderização de mensagens do playground.
  7. `tests/test_ai_azure_openai.py`: Novos testes automatizados com mocks de Azure OpenAI.

---

## 2. Constitution Check (Princípios I a VI)

| Princípio | Avaliação de Impacto | Status |
| :--- | :--- | :---: |
| **I. Especificação e TDD** | Spec formal criada com cenários Given/When/Then; testes pytest escritos antes da implementação. | **CONFORME** |
| **II. Automação ASVS 5.0** | O modelo Azure OpenAI será utilizado pelo `AIEvaluatorAgent` para avaliar o requisito V1.3.1. | **CONFORME** |
| **III. Arquitetura e Contratos** | Contratos de API tipados via Pydantic; persistência inalterada no SQLite (`asvs.db`). | **CONFORME** |
| **IV. Guardrails e Segurança** | Chaves do Azure OpenAI tratadas sob política de Zero-Leakage (somente em memória volátil, mascaradas com `"••••••••"`). | **CONFORME** |
| **V. Fluent 2 e Acessibilidade** | A nova aba respeita as diretrizes do Fluent 2, suporte a tema claro e escuro e acessibilidade WCAG 2.2 AA. | **CONFORME** |
| **VI. Seeds e Mapeamento** | Mapeamento declarativo mantido intacto em `config/req_tool_mapping.yaml`. | **CONFORME** |

*Veredito do Constitution Guardian*: **APROVADO SEM RESSALVAS**.

---

## 3. Detailed Architecture & Design

### 3.1 Camada de Armazenamento Volátil (`app/core/ai_secrets.py`)
```python
def set_credentials(
    self,
    model_name: str,
    api_key: str,
    provider: str = "azureopenai",
    resource_name: str | None = None,
    deployment_id: str | None = None,
    api_version: str = "2024-06-01",
) -> None:
```

### 3.2 Camada de Interface com o Modelo (`app/aci/ai_aci.py`)
- Suporte para construção dinâmica do endpoint:
  ```python
  if provider == "azureopenai":
      url = f"https://{resource_name}.openai.azure.com/openai/deployments/{deployment_id}/chat/completions?api-version={api_version}"
      headers = {"api-key": api_key, "Content-Type": "application/json"}
      payload = {"messages": [{"role": "user", "content": message}], "temperature": 0.0}
  ```

### 3.3 Endpoint de Playground (`POST /api/ai/chat-test`)
- Recebe a mensagem do usuário.
- Comunica com o modelo configurado em memória.
- Retorna `{"ok": true, "response_text": "...", "latency_ms": 178, "model": "azure-gpt5"}`.

### 3.4 Interface do Usuário (`templates/index.html` e `static/app.js`)
- Nova aba no menu principal (`5. Configuração de IA & Playground`).
- Grid de 2 colunas:
  - Esquerda: Formulário de configuração do Azure OpenAI com validação de campos.
  - Direita: Chat interativo com balões de diálogo e scroll automático.
