# Phase 0 Research: 006-azure-openai-and-dedicated-ai-tab

## Decisões Técnicas e Integração com Azure OpenAI

### 1. Formato de Chamada ao Azure OpenAI
- **Endpoint Padrão REST**:
  `https://{resource_name}.openai.azure.com/openai/deployments/{deployment_id}/chat/completions?api-version={api_version}`
- **Headers HTTP**:
  - `api-key: {api_key}`
  - `Content-Type: application/json`
- **Payload de Chat Completions**:
  ```json
  {
    "messages": [
      {"role": "system", "content": "..."},
      {"role": "user", "content": "..."}
    ],
    "temperature": 0.0,
    "max_tokens": 1000
  }
  ```
- **Extração da Resposta**:
  `resp_json["choices"][0]["message"]["content"]`

### 2. Extensão do `AISecretStore` (Memória Volátil)
- Suporte aos parâmetros do Azure OpenAI:
  - `_resource_name: str | None`
  - `_deployment_id: str | None`
  - `_api_version: str` (padrão: `"2024-06-01"`)
  - `_provider: Literal["azureopenai", "gemini"]`
- `get_masked_status()` passa a retornar:
  ```json
  {
    "configured": true,
    "provider": "azureopenai",
    "resource_name": "my-resource",
    "deployment_id": "azure-gpt5",
    "api_version": "2024-06-01",
    "model_name": "azure-gpt5",
    "key_masked": "••••••••"
  }
  ```

### 3. Novo Endpoint de Chat Playground (`POST /api/ai/chat-test`)
- Permite enviar uma mensagem aberta e receber a resposta direta do modelo ativo.
- Suporta testes tanto com credenciais já gravadas em memória quanto enviadas pontualmente no corpo da requisição.

### 4. Layout da Nova Aba 5 (`#panel-ai-config`)
- Dividida em duas colunas responsivas com tokens Fluent 2:
  - **Coluna Esquerda**: Formulário de Credenciais (Azure OpenAI / Gemini) com botão "Salvar em Memória" e "Limpar".
  - **Coluna Direita**: Chat Playground interativo com histórico de balões, campo de texto, botão de envio e indicadores de latência em milissegundos.

