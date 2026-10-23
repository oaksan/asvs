# Especificação de Funcionalidade (SDD): Descrição Exclusiva em Português para V1.2.1 a V1.5.1 (Remoção do Texto Original em Inglês)

**Feature Branch**: `018-pure-portuguese-descriptions`
**Created**: 2026-10-22
**Status**: Draft (aguardando aprovação para execução)
**Input**: *"crie um sdd para alterar apenas os itens V1.2.1 a V1.5.1. Exemplo para V1.2.1, onde está o Texto original (ASVS 5.0, inglês) coloque o Texto completo em Portugues: Verificar se a codificação de saída de respostas HTTP, documentos HTML ou XML é adequada ao contexto, codificando os caracteres relevantes para elementos, atributos e comentários HTML, CSS ou cabeçalhos HTTP, de modo a não alterar a estrutura da mensagem ou do documento. Remova o Texto original (ASVS 5.0, inglês)"*

---

## 1. Contexto e Diagnóstico

Na Feature 016 e Feature 017 foi introduzida a tradução em português (`description_pt`), porém a interface manteve um bloco recolhível `<details>` rotulado como `"Texto original (ASVS 5.0, inglês)"` contendo a descrição em inglês.

### Problema Identificado:
- **Poluição visual e redundância**: Para o usuário final e auditores brasileiros, ter o expansor "Texto original (ASVS 5.0, inglês)" logo abaixo da descrição gera ruído visual desnecessário.
- **Objetivo da Feature 018**:
  1. Remover por completo a exibição do bloco recolhível `"Texto original (ASVS 5.0, inglês)"` da tabela "Resultado por Verificação" e do modal "Ver Detalhes".
  2. Apresentar de forma direta, clara e única o **Texto completo em Português** para cada um dos 8 itens avaliados (`V1.2.1` a `V1.5.1`).
  3. Manter a integridade normativa do banco SQLite e do CSV oficial em inglês (Princípio I da Constituição), alterando puramente a camada de renderização frontend para exibir estritamente o português.

---

## 2. Textos Oficiais em Português para os Itens V1.2.1 a V1.5.1

Cada um dos 8 requisitos de escopo terá seu texto exibido com clareza e fidelidade técnica:

| ID Requisito | Título Amigável | Descrição Completa em Português (Exibição Única) |
| :--- | :--- | :--- |
| **V1.2.1** | Codificação de saída por contexto (HTTP, HTML e XML) | **Verificar se a codificação de saída de respostas HTTP, documentos HTML ou XML é adequada ao contexto, codificando os caracteres relevantes para elementos, atributos e comentários HTML, CSS ou cabeçalhos HTTP, de modo a não alterar a estrutura da mensagem ou do documento.** |
| **V1.2.2** | Codificação de URLs dinâmicas e protocolos permitidos | **Verificar se, ao montar URLs dinamicamente, os dados não confiáveis são codificados conforme o contexto (ex.: codificação de URL ou base64url em parâmetros de consulta ou de caminho) e se apenas protocolos de URL seguros são permitidos (ex.: bloquear `javascript:` e `data:`).** |
| **V1.2.3** | Escape em JavaScript e JSON gerados dinamicamente | **Verificar se codificação ou escape é aplicado ao montar conteúdo JavaScript dinamicamente (incluindo JSON), evitando alterar a estrutura da mensagem ou do documento (injeção de JavaScript e de JSON).** |
| **V1.2.4** | Consultas parametrizadas ao banco de dados | **Verificar se seleções de dados e consultas ao banco (ex.: SQL, HQL, NoSQL, Cypher) usam consultas parametrizadas, ORMs ou frameworks de entidades, ou estão protegidas de outro modo contra injeção de SQL e demais injeções em bancos de dados. Também vale para a escrita de stored procedures.** |
| **V1.2.5** | Prevenção de injeção de comandos do sistema operacional | **Verificar se a aplicação protege contra injeção de comandos do sistema operacional e se as chamadas ao SO usam consultas parametrizadas ou codificação contextual da linha de comando.** |
| **V1.3.1** | Sanitização de HTML enviado pelo usuário | **Verificar se toda entrada HTML não confiável, vinda de editores WYSIWYG ou similares, é sanitizada com uma biblioteca ou recurso de framework de sanitização de HTML conhecido e seguro.** |
| **V1.3.2** | Não uso de eval() e execução dinâmica de código | **Verificar se a aplicação evita `eval()` ou outros recursos de execução dinâmica de código, como Spring Expression Language (SpEL). Quando não houver alternativa, toda entrada do usuário incluída deve ser sanitizada antes da execução.** |
| **V1.5.1** | Parser XML restritivo (prevenção de XXE) | **Verificar se a aplicação configura os parsers XML de forma restritiva e desabilita recursos inseguros, como a resolução de entidades externas, para prevenir ataques XXE (XML eXternal Entity).** |

---

## 3. User Scenarios & Acceptance Criteria

### User Story 1 — Visualização Direta em Português sem Inglês Residual (P1)
Como usuário da plataforma de autoavaliação ASVS,  
quero ver a descrição completa dos requisitos V1.2.1 a V1.5.1 diretamente em português,  
para que eu compreenda imediatamente a verificação de segurança sem termos em inglês repetidos ou blocos recolhíveis secundários.

#### Acceptance Scenarios:
1. **Given** uma execução de avaliação carregada no dashboard,  
   **When** o usuário examinar a tabela "Resultado por Verificação",  
   **Then** cada linha referente a `V1.2.1` até `V1.5.1` exibe o texto completo em português definido na tabela da Seção 2.
2. **Given** a tabela "Resultado por Verificação",  
   **When** renderizada na interface,  
   **Then** NÃO deve existir nenhum elemento `<details class="req-original">` ou texto `"Texto original (ASVS 5.0, inglês)"`.
3. **Given** o modal "Ver Detalhes" de qualquer um dos 8 requisitos,  
   **When** aberto pelo usuário clicando no botão "Ver Detalhes",  
   **Then** o modal exibe o texto completo em português na seção "O que foi verificado", sem exibir o bloco de texto em inglês.
4. **Given** a geração de relatórios exportados (HTML ou impressão),  
   **When** impressos ou salvos,  
   **Then** a descrição exibida é puramente o texto completo em português.

---

## 4. Requisitos Funcionais

- **FR-001**: A função de renderização `appendRequirementDescription` em `static/app.js` DEVE renderizar exclusivamente o texto em português (`description_pt`), utilizando o elemento `<div class="req-description" lang="pt-BR">`.
- **FR-002**: O código frontend DEVE remover a criação do elemento `<details class="req-original">` e a exibição do texto `"Texto original (ASVS 5.0, inglês)"`.
- **FR-003**: Se porventura `description_pt` não estiver preenchido para algum item, o sistema deve usar a descrição existente como fallback seguro sem lançar exceções JavaScript.
- **FR-004**: O backend (`list_run_verdicts`, `get_run_details`, `get_in_scope_requirements`) e `config/req_tool_mapping.yaml` DEVEM manter as strings oficiais completas em português para os 8 requisitos.
- **FR-005**: O arquivo normativo CSV `docs/OWASP_Application_Security_Verification_Standard_5.0.0_en.csv` e os registros originais da tabela `Requirement` no SQLite NÃO DEVEM ser modificados, garantindo 100% de conformidade com o Princípio I da Constituição.
- **FR-006**: O número de versão de cache-busting DEVE ser incrementado para `?v=018` em `templates/index.html` e nos testes de integração UI.

---

## 5. Critérios de Sucesso

- **SC-001**: 100% dos 8 requisitos (V1.2.1 a V1.5.1) exibem seu texto completo em português tanto na tabela quanto no modal.
- **SC-002**: Zero ocorrências de `"Texto original (ASVS 5.0, inglês)"` no DOM renderizado.
- **SC-003**: A suíte de testes automatizados pytest executa sem novas falhas e valida a ausência de texto em inglês residual na camada de apresentação.

