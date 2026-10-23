# Feature Specification: 005-production-grade-ui-redesign

**Feature Branch / Directory**: `specs/005-production-grade-ui-redesign`  
**Created**: 2026-10-14  
**Status**: Draft  
**Constitution Reference**: Princípio V (Interface Visual Acessível com Fluent 2) e Princípio I (Especificação Estrita e TDD)

---

## 1. Executive Summary & Objective

Esta especificação transforma a interface do ASVS Self-Assessment Tool de um painel voltado a depuração interna e metadados de desenvolvimento em uma **aplicação corporativa real de auditoria e segurança da informação**.

### Principais Objetivos:
1. **Foco no Usuário e no Negócio**:
   - Eliminar dados irrelevantes para o usuário final, como a menção e correlação cruzada entre o ASVS 5.0 e o legado ASVS 4.0 (`asvs_4_0_refs`, status de equivalência e migração). O usuário avalia sua aplicação contra o padrão vigente (ASVS 5.0).
   - Suprimir jargões de depuração técnica interna (ex.: `Scoper -> SAST -> DAST -> Triage -> Verdict`, `tokens voláteis`, `payloads SARIF`). A aplicação deve se apresentar como um serviço executivo de auditoria de segurança contínua.
2. **Design Corporativo Fluent 2 (Production-Grade)**:
   - Estruturação em painéis claros: **Visão Geral Executiva**, **Execução de Diagnóstico**, **Central de Achados & Remediação**, e **Relatórios Exportáveis**.
   - Separação entre detalhes operacionais imediatos e logs avançados de infraestrutura (colapsados sob demanda).
   - Card de configuração de IA e ferramentas dinâmicas com linguagem de negócio ("Conexão com Motor Cognitivo de Análise" em vez de detalhes de implementação de código).
3. **Preservação dos Guardrails Mandatórios**:
   - Manutenção inegociável do checkbox de autorização legal DAST (`#zap-authorized`) e do AI Gate pré-avaliação (Princípio IV).

---

## 2. User Scenarios & Acceptance Criteria *(mandatory)*

### User Story 1 — Simplificação e Foco no Padrão Vigente (ASVS 5.0) (Priority: P1 🎯 MVP)

Como analista de segurança, desenvolvedor ou auditor,  
Quero visualizar apenas os requisitos vigentes do ASVS 5.0 e o status da minha aplicação,  
Para que eu não seja sobrecarregado com detalhes históricos ou correlações com versões obsoletas como o ASVS 4.0.

**Why this priority**: Experiência do usuário e clareza de produto. O valor central é a conformidade contra o OWASP ASVS 5.0 vigente.

**Independent Test**:
Acessar as abas de Catálogo (`#panel-catalog`) e Dashboard (`#panel-dashboard`) com uma avaliação concluída: comprovar visualmente e via inspeção de DOM que nenhuma coluna, célula, badge ou texto contém `"ASVS 4.0"`, referências a `V5.1.x` legados ou status de equivalência.

**Acceptance Scenarios**:

1. **Cenário 1.1 — Remoção da coluna e badges de ASVS 4.0 no Catálogo**:
   - **Given** que o usuário acessa a aba de Catálogo de Requisitos (`#panel-catalog`),
   - **When** a tabela de requisitos em escopo é renderizada pelo cliente,
   - **Then** a coluna `Equivalência ASVS 4.0` NÃO deve constar no cabeçalho `<thead>`;
   - **And** nenhuma menção a IDs do ASVS 4.0 ou tags de migração (`confirmada`, `pendente`) deve ser renderizada no `<tbody>`;
   - **And** a tabela deve conter apenas: `Req ID (ASVS 5.0)`, `Seção`, `Descrição Normativa` e `Ferramentas Mapeadas`.

2. **Cenário 1.2 — Remoção de referências legadas no Dashboard de Vereditos**:
   - **Given** que uma avaliação concluiu e o usuário visualiza a lista de vereditos por requisito em `#panel-dashboard`,
   - **When** os cards ou linhas da tabela de vereditos são inspecionados,
   - **Then** a primeira coluna exibe exclusivamente o identificador ASVS 5.0 (ex.: `V1.2.1`), a seção temática e o nome da seção;
   - **And** a linha descritiva secundária contendo `ASVS 4.0: V... (status)` é completamente removida.

---

### User Story 2 — Interface Limpa de Diagnóstico e Configuração (Priority: P1)

Como operador da ferramenta,  
Quero configurar uma nova análise através de uma interface profissional e sem ruídos de depuração,  
Para que a experiência seja fluida, elegante e condizente com uma ferramenta corporativa.

**Why this priority**: Usabilidade e apresentação visual corporativa.

**Independent Test**:
Carregar a página inicial `#panel-assessment`: verificar que a descrição do formulário não despeja listas cruas de arrays de código e que o painel de status do ZAP e da IA apresentam textos de alto nível voltados ao negócio.

**Acceptance Scenarios**:

1. **Cenário 2.1 — Simplificação do cabeçalho e termos de execução**:
   - **Given** o formulário de "Nova Avaliação" em `#panel-assessment`,
   - **When** o painel é apresentado ao usuário,
   - **Then** a lista crua de IDs (`{{ in_scope_req_ids | join(', ') }}`) e a sequência de classes internas do pipeline (`Scoper -> SAST -> DAST...`) são substituídas por um resumo executivo: *"Avaliação automatizada de conformidade de segurança de software conforme OWASP ASVS 5.0 (Capítulo V1 — Codificação e Sanitização)"*;
   - **And** o painel de status do ZAP é apresentado como um indicador compacto de prontidão de serviço.

2. **Cenário 2.2 — Central de IA com linguagem de produto**:
   - **Given** o painel de configuração do modelo de linguagem (`#ai-config-panel`),
   - **When** o usuário expande ou visualiza a seção,
   - **Then** a interface apresenta a finalidade como *"Motor de Análise Cognitiva de Código"* com indicativo visual de segurança (*"Credenciais protegidas em memória volátil com isolamento de dados"*);
   - **And** referências diretas a nomes de classes internas como `AIEvaluatorAgent` e `AISecretStore` são suprimidas da interface visível.

---

### User Story 3 — Central de Achados com Foco em Remediação (Priority: P2)

Como engenheiro responsável por corrigir falhas apontadas,  
Quero que os achados apresentem orientações claras de remediação e impacto de segurança,  
Em vez de informações brutas de scanners e metadados de AST internos.

**Acceptance Scenarios**:

1. **Cenário 3.1 — Apresentação contextual de achados**:
   - **Given** um requisito com status `FAIL` ou achados de segurança,
   - **When** o usuário visualiza a evidência e detalhes do achado no modal,
   - **Then** a visualização prioriza o arquivo, linha, trecho de código formatado e a ação recomendada para correção;
   - **And** metadados brutos de scanners e AST são recolhidos em acordeão secundário.

---

## 3. Não-Requisitos e Guardrails Preservados
- **Não alterar o modelo de dados subjacente**: O campo `asvs_4_0_refs` pode continuar existindo no banco de dados SQLite (`asvs.db`), mas a camada de apresentação (HTML/JS) DEVE ocultá-lo do usuário.
- **Guardrails de Segurança Inalterados**:
  - Aceite de consentimento DAST universal obrigatório (`#zap-authorized`).
  - AI Gate obrigatório antes do início da avaliação.
  - Zero-leakage de credenciais mantido rigorosamente em memória.

