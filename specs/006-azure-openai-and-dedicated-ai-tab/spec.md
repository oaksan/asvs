# Feature Specification: 006-azure-openai-and-dedicated-ai-tab

**Feature Branch / Directory**: `specs/006-azure-openai-and-dedicated-ai-tab`  
**Created**: 2026-10-14  
**Status**: Draft  
**Constitution Reference**: Princípio IV (Segurança e Zero-Leakage de Credenciais) e Princípio V (Interface Visual Acessível com Fluent 2)

---

## 1. Executive Summary & Objective

Esta especificação implementa a integração corporativa do modelo de IA via **Azure OpenAI** (compatível com a estrutura de *Inference Service* do Elasticsearch `PUT _inference/chat_completion/azure-gpt5`) e transfere toda a gestão de modelos de IA para uma **aba dedicada na interface** com um **Playground Interativo de Chat**.

### Principais Objetivos:
1. **Suporte Estruturado a Azure OpenAI**:
   - Parametrização completa: `service: "azureopenai"`, `resource_name`, `deployment_id`, `api_version` (padrão: `2024-06-01`) e `api_key`.
   - Compatibilidade mantida com o provedor anterior (**Google Gemini**).
2. **Guia/Aba Dedicada na Interface (`#panel-ai-config`)**:
   - Navegação Fluent 2 expandida para 5 abas: `1. Nova Avaliação`, `2. Dashboard`, `3. Catálogo`, `4. Histórico` e `5. Configuração de IA & Playground`.
   - Limpeza do formulário da Aba 1, que passa a exibir apenas um chip executivo de status da IA (`[✓ Motor Cognitivo Conectado: azure-gpt5 (Azure OpenAI)]` ou indicador de não configurado).
3. **Playground Interativo de Teste (Chat de Diagnóstico)**:
   - Permite que o operador envie qualquer mensagem de teste customizada (ex.: *"Você está operacional para avaliar o ASVS 5.0?"*).
   - Exibe a resposta textual gerada pelo modelo, latência em ms, tokens de uso e status HTTP 200.
4. **Preservação Rígida de Guardrails Inegociáveis (Princípio IV)**:
   - Todas as credenciais de Azure OpenAI residem **estritamente em memória volátil** (`AISecretStore`), jamais gravadas no banco SQLite (`asvs.db`) ou registradas em logs.
   - Respostas de API continuam mascarando a chave como `"••••••••"`.
   - O `AIEvaluatorAgent` consome o provedor ativo (Azure OpenAI ou Gemini) para avaliar o requisito qualitativo V1.3.1.

---

## 2. User Scenarios & Acceptance Criteria *(mandatory)*

### User Story 1 — Configuração Dedicada de Provedor Azure OpenAI (Priority: P1 🎯 MVP)

Como operador de segurança ou auditor da ferramenta,  
Quero configurar meu modelo Azure OpenAI informando `resource_name`, `deployment_id`, `api_version` e `api_key` em uma aba dedicada,  
Para que as análises assistidas por IA utilizem meu cluster corporativo de inteligência artificial de forma segura.

**Why this priority**: Capacidade nuclear da feature para suportar endpoints corporativos de inferência.

**Independent Test**:
Acessar a nova aba "5. Configuração de IA & Playground", preencher os parâmetros do Azure OpenAI e salvar: verificar via `GET /api/ai/status` que o sistema reporta `configured: true`, `provider: "azureopenai"`, `model_name: "azure-gpt5"`, `key_masked: "••••••••"` e que nenhuma chave em texto claro vazou.

**Acceptance Scenarios**:

1. **Cenário 1.1 — Submissão de credenciais Azure OpenAI**:
   - **Given** que o operador preencheu os campos: `service: "azureopenai"`, `resource_name: "my-azure"`, `deployment_id: "azure-gpt5"`, `api_version: "2024-06-01"` e `api_key: "segredo123"`,
   - **When** clica em "Salvar Credenciais",
   - **Then** a requisição `POST /api/ai/config` é enviada com sucesso;
   - **And** a resposta HTTP é 200 OK contendo `configured: true`, `provider: "azureopenai"` e `key_masked: "••••••••"`;
   - **And** o banner de feedback confirma o armazenamento volátil seguro.

2. **Cenário 1.2 — Rejeição de campos vazios ou inválidos**:
   - **Given** uma requisição `POST /api/ai/config` com `service: "azureopenai"` e `resource_name` ou `api_key` em branco,
   - **When** o backend valida o schema,
   - **Then** retorna HTTP 422 Unprocessable Entity com indicação do campo ausente;
   - **And** as credenciais em memória não são corrompidas.

---

### User Story 2 — Playground Interativo de Mensagem e Resposta (Priority: P1)

Como operador,  
Quero enviar uma mensagem de teste no chat da aba de IA e receber a resposta direta do modelo,  
Para validar a conectividade, capacidade de geração e latência antes de rodar o pipeline.

**Why this priority**: Confirmação visual e funcional imediata de que o modelo está operacional.

**Independent Test**:
Digitar uma mensagem no input do playground e clicar em "Enviar Mensagem de Teste": comprovar que um balão de conversa com o texto do usuário é adicionado, seguido pelo balão com a resposta retornada pelo Azure OpenAI e indicadores de latência em milissegundos.

**Acceptance Scenarios**:

1. **Cenário 2.1 — Envio e recepção de mensagem com sucesso**:
   - **Given** que o Azure OpenAI está configurado em memória (ou preenchido na interface),
   - **When** o usuário digita *"Responda com status de prontidão"* e aciona o envio,
   - **Then** uma requisição `POST /api/ai/chat-test` é disparada;
   - **And** o backend envia a mensagem para o endpoint REST do Azure OpenAI (`https://{resource_name}.openai.azure.com/openai/deployments/{deployment_id}/chat/completions?api-version={api_version}`);
   - **And** a resposta do modelo é exibida no chat acompanhada da latência em ms (ex.: `Latência: 182ms • HTTP 200`).

2. **Cenário 2.2 — Falha de comunicação ou chave inválida**:
   - **Given** que a chave informada é inválida ou o recurso não existe,
   - **When** a requisição de teste é enviada,
   - **Then** a interface renderiza o balão de erro informando a falha de autenticação (HTTP 401/404);
   - **And** nenhuma chave ou segredo é exposto na mensagem de erro.

---

### User Story 3 — Aba Separada e Limpeza da Tela de Avaliação (Priority: P2)

Como usuário,  
Quero que o formulário da Aba 1 (Nova Avaliação) fique limpo e exiba apenas o status executivo da IA,  
Para que a tela de início seja focada na auditoria e não na administração de chaves.

**Acceptance Scenarios**:

1. **Cenário 3.1 — Navegação por 5 abas acessíveis**:
   - **Given** a página principal `GET /`,
   - **When** o menu de navegação é inspecionado,
   - **Then** o `<nav class="nav-tabs">` contém exatamente 5 abas: `#tab-assessment`, `#tab-dashboard`, `#tab-catalog`, `#tab-history` e `#tab-ai-config`;
   - **And** todas atendem a acessibilidade WCAG 2.2 AA (navegação por teclado e atributos `aria-selected` / `aria-controls`).

2. **Cenário 3.2 — Status executivo na Aba 1**:
   - **Given** a Aba 1 (`#panel-assessment`),
   - **When** o motor de IA está configurado,
   - **Then** um chip executivo exibe: `✓ Motor Cognitivo: [deployment_id] ([provider]) • Pronto para V1.3.1`;
   - **And** o formulário não contém campos de input de chave de API misturados com o formulário de avaliação.

---

## 3. Não-Requisitos e Guardrails Preservados
- **Não persistência em disco/banco**: As credenciais de Azure OpenAI NUNCA são salvas em SQLite (`asvs.db`).
- **Retrocompatibilidade**: O provedor Gemini continua suportado.
- **AI Gate Universal**: A avaliação só inicia se `AISecretStore.is_configured() == True`, garantindo que o `AIEvaluatorAgent` esteja sempre operacional.

