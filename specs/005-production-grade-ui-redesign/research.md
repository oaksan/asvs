# Phase 0 Research: 005-production-grade-ui-redesign

## Decisões Técnicas e Arquitetura de Interface

### 1. Desacoplamento entre Modelo de Dados e Camada de Apresentação
- **Problema**: O modelo `Requirement` e os endpoints `GET /api/requirements` e `GET /api/runs/{id}/verdicts` contêm os campos `asvs_4_0_refs` e `mapping_status`.
- **Decisão**: Preservar os campos no banco SQLite (`asvs.db`) e nos schemas Pydantic de resposta (`RequirementRead`, `VerdictRead`), garantindo retrocompatibilidade total da API REST. A supressão é 100% realizada no cliente JavaScript (`static/app.js`) e no template Jinja2 (`templates/index.html`).
- **Benefício**: Zero quebra de contratos de banco ou testes existentes de backend.

### 2. Higienização Visual de Cabeçalhos e Jargões Internos
- **Problema**: O topo do formulário exibe `in_scope_req_ids | join(', ')` e cita nominalmente as classes dos 8 agentes (`Scoper -> SAST -> DAST -> Triage...`).
- **Decisão**: Substituir por uma apresentação corporativa com foco na proposta de valor: *"Auditoria Automatizada de Segurança da Aplicação conforme OWASP ASVS 5.0 (Capítulo V1 — Codificação e Sanitização)"*.
- **Benefício**: Interface elegante, limpa e pronta para demonstração executiva.

### 3. Redesign do Painel de IA (Cognitive Analysis Center)
- **Problema**: O painel expõe termos como `AIEvaluatorAgent`, `V1.3.1` e detalhes internos de classes de armazenamento.
- **Decisão**: Utilizar rótulos profissionais: *"Motor de Análise Cognitiva de Código"* com indicativo visual de segurança (*"Credenciais protegidas em memória volátil com isolamento de dados"*), mantendo o input mascarado e o botão de teste de conexão.
- **Benefício**: Clareza funcional sem expor arquitetura de código.

### 4. Indicador Minimalista de Conexão com ZAP
- **Problema**: O badge e botão do ZAP no topo do formulário geram poluição visual.
- **Decisão**: Transformar em um chip minimalista com ícone de status (`Pronto para varredura passiva` ou `ZAP indisponível`).

