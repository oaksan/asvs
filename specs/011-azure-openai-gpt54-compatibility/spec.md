# Feature Specification: Compatibilidade Nativa com Azure OpenAI GPT-5.4 (`max_completion_tokens` e Normalização de Endpoint)

**Feature Branch**: `011-azure-openai-gpt54-compatibility`  
**Created**: 2026-10-20  
**Status**: Approved  
**Input**: Suporte nativo ao modelo Azure OpenAI `gpt-5.4` (`api-version=2024-12-01-preview`), substituição de `max_tokens` por `max_completion_tokens` com fallback transparente, extração automática de parâmetros caso o usuário cole a URL completa do Azure OpenAI no campo `resource_name`, e detalhamento sanitizado de erros `HTTP 400`.

---

## 1. Contexto e Problema

Ao conectar a ferramenta ao deployment Azure OpenAI `gpt-5.4` (`https://cog-fcb-generai-poc01.openai.azure.com/openai/deployments/gpt-5.4/chat/completions?api-version=2024-12-01-preview`):

1. **Incompatibilidade de `max_tokens` no `gpt-5.4` (`HTTP 400`)**:
   - O modelo `gpt-5.4` (`gpt-5.4-2026-03-05`) rejeita o parâmetro legado `"max_tokens"` com `HTTP 400 Bad Request`:
     `{"error": {"message": "Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.", "param": "max_tokens", "code": "unsupported_parameter"}}`
   - As 3 funções de `app/aci/ai_aci.py` (`check_ai_connectivity`, `chat_with_ai` e `run_ai_evaluation`) enviavam `"max_tokens"` fixo (e `"temperature": 0.0`), provocando falha tanto no teste de conexão quanto no Playground e na avaliação do requisito `V1.3.1`.
2. **Mascaramento indevido de `HTTP 400` como falha de autenticação**:
   - Em `check_ai_connectivity`, o status `400` caía no mesmo bloco de `(400, 401, 403, 404)` exibindo `"Falha de autenticação com azureopenai (HTTP 400)"` sem informar o motivo técnico retornado pelo Azure.
3. **Usabilidade ao colar URL completa do Azure OpenAI**:
   - Analistas frequentemente copiam a URL completa do Azure AI Foundry (`https://{resource}.openai.azure.com/openai/deployments/{deployment}/chat/completions?api-version={version}`). Se colada no campo `resource_name`, a interpolação gerava uma URL inválida.

---

## 2. User Scenarios & Testing

### User Story 1 - Conexão, Chat e Avaliação `V1.3.1` com `gpt-5.4` (`max_completion_tokens`) (Priority: P1)

Como analista de segurança utilizando o deployment `gpt-5.4` no Azure OpenAI (`2024-12-01-preview`), quero testar a conexão, conversar no Playground e avaliar o requisito `V1.3.1` sem erro `HTTP 400 Unsupported parameter: 'max_tokens'`.

**Acceptance Scenarios**:

1. **Given** que o provedor é `azureopenai` com deployment `gpt-5.4` e `api_version="2024-12-01-preview"`, **When** `check_ai_connectivity`, `chat_with_ai` ou `run_ai_evaluation` enviam requisição ao Azure OpenAI, **Then** o payload utiliza `"max_completion_tokens"` por padrão (e realiza fallback automático caso um modelo legado exija `"max_tokens"` ou rejeite `"temperature"`).
2. **Given** que o Azure OpenAI retorna `HTTP 400` por parâmetro inválido, **When** `check_ai_connectivity` processa a resposta, **Then** a mensagem retornada distingue erro de parâmetro (`HTTP 400`) de falha de autenticação (`HTTP 401/403`) e inclui o detalhe técnico sanitizado (Zero-Leakage).

---

### User Story 2 - Normalização Automática de URL Completa do Azure OpenAI (Priority: P1)

Como analista de segurança, quero poder informar tanto apenas o nome do recurso (`cog-fcb-generai-poc01`) quanto colar a URL completa do endpoint Azure OpenAI (`https://cog-fcb-generai-poc01.openai.azure.com/openai/deployments/gpt-5.4/chat/completions?api-version=2024-12-01-preview`), tendo `resource_name`, `deployment_id` e `api_version` extraídos automaticamente.

**Acceptance Scenarios**:

1. **Given** que o usuário envia `resource_name="https://cog-fcb-generai-poc01.openai.azure.com/openai/deployments/gpt-5.4/chat/completions?api-version=2024-12-01-preview"`, **When** `normalize_azure_settings` processa os parâmetros, **Then** extrai `resource_name="cog-fcb-generai-poc01"`, `deployment_id="gpt-5.4"` e `api_version="2024-12-01-preview"`.

---

## 3. Requirements

- **FR-001**: `app/aci/ai_aci.py` DEVE usar `"max_completion_tokens"` como parâmetro padrão nas chamadas Azure OpenAI em `check_ai_connectivity`, `chat_with_ai` e `run_ai_evaluation`, com fallback automático caso o endpoint legado solicite `"max_tokens"` ou rejeite `"temperature"`.
- **FR-002**: `app/aci/ai_aci.py` DEVE disponibilizar `normalize_azure_settings(resource_name, deployment_id, api_version)` para extrair `resource_name`, `deployment_id` e `api_version` caso uma URL completa ou parcial `https://*.openai.azure.com/...` seja fornecida, aplicando-a também em `POST /api/ai/config`, `POST /api/ai/test-connection` e `POST /api/ai/chat-test`.
- **FR-003**: `templates/index.html` e `static/app.js` DEVEM atualizar os valores padrão sugeridos na aba de IA para `gpt-5.4` e `2024-12-01-preview`, além de preencher automaticamente os campos `resource_name`, `deployment_id` e `api_version` quando o usuário colar uma URL completa do Azure OpenAI.
- **FR-004**: Nenhuma chave de API (`api-key`) pode ser exposta em logs, mensagens de erro ou banco em texto claro (Princípio IV — Zero-Leakage).

