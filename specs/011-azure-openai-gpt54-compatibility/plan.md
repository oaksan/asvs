# Implementation Plan: Compatibilidade Nativa com Azure OpenAI GPT-5.4

**Branch**: `011-azure-openai-gpt54-compatibility` | **Date**: 2026-10-20 | **Spec**: [spec.md](file:///home/user/felipe/speckit/asvs/specs/011-azure-openai-gpt54-compatibility/spec.md)

---

## 1. Summary

Atualizar a integração Azure OpenAI em `app/aci/ai_aci.py`, `app/main.py`, `templates/index.html` e `static/app.js` para:
1. Enviar `"max_completion_tokens"` por padrão nas chamadas Azure OpenAI (`check_ai_connectivity`, `chat_with_ai`, `run_ai_evaluation`), com helper `_post_azure_chat_completion` que faz fallback automático se um modelo legado exigir `"max_tokens"` ou se um modelo reasoning/`gpt-5.4` rejeitar `"temperature"`.
2. Normalizar entradas de `resource_name` via `normalize_azure_settings(...)` para suportar tanto o nome do recurso (`cog-fcb-generai-poc01`) quanto a URL completa (`https://cog-fcb-generai-poc01.openai.azure.com/openai/deployments/gpt-5.4/chat/completions?api-version=2024-12-01-preview`).
3. Exibir mensagens de erro `HTTP 400` / `HTTP 404` com o detalhe técnico sanitizado retornado pelo Azure OpenAI, separando de `HTTP 401` / `HTTP 403` (falha de autenticação).
4. Atualizar os defaults da aba de IA (`templates/index.html` e `static/app.js`) com auto-parse de URL colada e cache-busting `?v=011`.

---

## 2. Arquitetura e Componentes Modificados

### 2.1. `app/aci/ai_aci.py`
- **`normalize_azure_settings(resource_name, deployment_id, api_version)`**:
  - Se `resource_name` contiver `https://` ou `.openai.azure.com`, extrai via regex/URL parser:
    - `host` -> subdomínio antes de `.openai.azure.com` (ex.: `cog-fcb-generai-poc01`).
    - `/openai/deployments/{dep}/` -> se presente na URL, usa `{dep}` quando `deployment_id` estiver vazio ou ainda no valor default (`azure-gpt5`), ou se a URL completa tiver sido colada.
    - `api-version={ver}` -> se presente na query string, usa `{ver}` quando `api_version` estiver vazio ou no default `2024-06-01`.
- **`_post_azure_chat_completion(client, url, headers, messages, max_tokens, temperature=None)`**:
  - Monta o payload com `"max_completion_tokens": max_tokens` (e inclui `"temperature"` apenas quando `temperature is not None`).
  - Em `check_ai_connectivity`, envia `max_completion_tokens=20` sem `temperature` (exatamente como validado com `HTTP 200` no `gpt-5.4`).
  - Se a resposta for `HTTP 400` e o corpo mencionar `'max_completion_tokens'` como não suportado (modelos muito antigos), reexecuta automaticamente trocando por `'max_tokens'`.
  - Se a resposta for `HTTP 400` e o corpo mencionar `'temperature'` como não suportado, reexecuta automaticamente removendo `'temperature'`.
- **Extração de erro sanitizado (`_extract_provider_error_detail`)**:
  - Extrai `error.message` do JSON de erro (sanitizado por `_sanitize_error_message`), diferenciando `401/403` (autenticação) de `400/404` (parâmetro, deployment ou versão da API).

### 2.2. `app/main.py`
- Aplicar `normalize_azure_settings` em `POST /api/ai/config`, `POST /api/ai/test-connection` e `POST /api/ai/chat-test` para que os valores normalizados (`resource_name="cog-fcb-generai-poc01"`, `deployment_id="gpt-5.4"`, `api_version="2024-12-01-preview"`) sejam salvos e refletidos na sessão e no banco.

### 2.3. `templates/index.html` e `static/app.js`
- Atualizar os valores default na aba 5 (`templates/index.html`) para `deployment_id="gpt-5.4"` e `api_version="2024-12-01-preview"`, e placeholder de `resource_name` para `Ex.: cog-fcb-generai-poc01 (ou cole a URL completa do endpoint)`.
- Em `static/app.js`, adicionar listener `input`/`change` no campo `azure-resource-name`: se o usuário colar uma URL completa `https://{res}.openai.azure.com/openai/deployments/{dep}/chat/completions?api-version={ver}`, decompõe automaticamente nos 3 campos (`azure-resource-name`, `azure-deployment-id`, `azure-api-version`).
- Atualizar `?v=011` em `templates/index.html`.

