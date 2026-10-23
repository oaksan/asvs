# Especificação de Funcionalidade (SDD): Descrição Completa em Bloco Recolhível para V1.2.1 a V1.5.1

**Feature Branch**: `019-collapsible-requirement-descriptions`
**Created**: 2026-10-22
**Status**: Draft (aguardando aprovação para execução)
**Input**: *"crie um sdd para adicionar a descricao completa de V1.2.1 a V1.5.1 em bloco recolhível. por exemplo V1.2.1, seria apenas colocar em um bloco recolhível a descricao completa: Verificar se a codificação de saída de respostas HTTP, documentos HTML ou XML é adequada ao contexto, codificando os caracteres relevantes para elementos, atributos e comentários HTML, CSS ou cabeçalhos HTTP, de modo a não alterar a estrutura da mensagem ou do documento."*

---

## 1. Contexto e Diagnóstico

Na Feature 018, as descrições dos requisitos V1.2.1 a V1.5.1 foram convertidas exclusivamente para o texto completo em português. No entanto, por serem parágrafos normativos densos (de 3 a 6 linhas cada), a exibição aberta de todas as descrições simultaneamente aumenta a altura vertical das linhas da tabela "Resultado por Verificação", dificultando a visualização rápida dos resultados de conformidade.

### Objetivo da Feature 019:
1. **Adicionar a descrição completa em português em um bloco recolhível (`<details class="req-desc-details">`)** para cada item de V1.2.1 a V1.5.1 na tabela "Resultado por Verificação".
2. **Compactar a visualização padrão**: O usuário visualiza imediatamente o identificador (ex.: `V1.2.1`), o título em português (ex.: `Codificação de saída por contexto (HTTP, HTML e XML)`) e a seção (ex.: `V1.2 — Prevenção de Injeção`), com um controle expansível claro como `"Descrição completa"` ou `"Ver descrição"`.
3. **Expansão sob demanda**: Ao clicar no bloco recolhível, o texto completo em português é revelado de forma fluida.
4. **Comportamento de Impressão (`@media print`)**: Na impressão do relatório ou exportação para PDF, o bloco recolhível deve ser expandido automaticamente, garantindo que o relatório físico/impresso contenha a íntegra das descrições normativas.
5. **Modal "Ver Detalhes"**: Mantém a descrição completa em português em destaque para consulta rápida no diálogo modal.

---

## 2. Textos Completos dos Blocos Recolhíveis (V1.2.1 a V1.5.1)

Cada item terá exatamente seu texto normativo completo em português encapsulado dentro do bloco recolhível:

| ID | Título Amigável (Sempre Visível) | Conteúdo do Bloco Recolhível (`<details>`) |
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

### User Story 1 — Tabela Compacta com Descrição Recolhível (P1)
Como usuário da ferramenta,  
quero que a tabela de resultados apresente as linhas compactas com a descrição completa em um bloco expansível,  
para que eu possa escanear todos os resultados com rapidez e expandir a descrição apenas quando necessário.

#### Acceptance Scenarios:
1. **Given** a tabela "Resultado por Verificação" carregada na tela,  
   **When** visualizada pelo usuário,  
   **Then** cada linha referente a `V1.2.1` até `V1.5.1` exibe o identificador, o título amigável e um bloco recolhível rotulado `"Descrição completa"`.
2. **Given** o bloco recolhível `"Descrição completa"`,  
   **When** fechado (estado inicial padrão),  
   **Then** o texto completo não ocupa espaço vertical na linha da tabela.
3. **Given** o bloco recolhível `"Descrição completa"`,  
   **When** clicado pelo usuário (ou acionado via teclado Enter/Espaço),  
   **Then** ele se abre revelando a íntegra da descrição em português.
4. **Given** o diálogo modal "Ver Detalhes",  
   **When** aberto pelo botão de ações,  
   **Then** a descrição completa em português é apresentada diretamente para leitura detalhada.

### User Story 2 — Fidelidade na Impressão e Relatórios (P2)
Como auditor ou desenvolvedor gerando relatório impresso/PDF,  
quero que todas as descrições recolhíveis apareçam expandidas na impressão,  
para que o documento contenha o registro completo das verificações sem exigir cliques manuais prévios.

#### Acceptance Scenarios:
1. **Given** a folha de estilos de impressão (`@media print`),  
   **When** o documento é impresso ou visualizado em prévia de impressão,  
   **Then** todos os elementos recolhíveis de descrição (`details.req-desc-details`) são exibidos abertos e formatados com contraste adequado.

---

## 4. Requisitos Funcionais

- **FR-001**: A função `appendRequirementDescription` em `static/app.js` DEVE encapsular a descrição completa em português dentro de um elemento `<details class="req-desc-details">` com um `<summary>` amigável (ex.: `"Descrição completa"`).
- **FR-002**: O conteúdo interno do bloco recolhível DEVE utilizar `<div class="req-description-body" lang="pt-BR">` contendo o texto completo em português.
- **FR-003**: O componente DEVE respeitar acessibilidade WCAG 2.2 AA (foco visível no summary, suporte a navegação por teclado, estados nativos de acessibilidade).
- **FR-004**: O arquivo `static/theme.css` DEVE definir estilos modernos com base no Microsoft Fluent 2 (cursor pointer, espaçamentos sutis, cor secundária no summary e abertura automática em `@media print`).
- **FR-005**: Atualizar o bump de versão para `?v=019` em `app/main.py` e `templates/index.html`.

---

## 5. Critérios de Sucesso

- **SC-001**: Todos os 8 requisitos (V1.2.1 a V1.5.1) possuem bloco recolhível funcional na tabela "Resultado por Verificação".
- **SC-002**: A altura padrão das linhas da tabela é reduzida, melhorando a escaneabilidade do dashboard.
- **SC-003**: Todos os testes automatizados da suíte executam com sucesso.
