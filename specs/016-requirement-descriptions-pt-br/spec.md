# Especificação de Funcionalidade (SDD): Descrição dos requisitos V1.2.1 a V1.5.1 em português (pt-BR)

**Feature Branch**: `016-requirement-descriptions-pt-br`
**Created**: 2026-10-22
**Status**: Draft (aguardando Gate 1)
**Input**: *"Gere o SDD para deixar do V1.2.1 a V1.5.1 com a descrição do item em português."*

---

## 1. Diagnóstico

| # | Observação | Local |
| :-: | :--- | :--- |
| 1 | Após a Feature 015, "Resultado por Verificação" mostra a descrição normativa em **inglês** (`Requirement.req_description`, vinda do CSV oficial ASVS 5.0). | `static/app.js` (`renderVerdictsTable`, `openRequirementModal`) |
| 2 | A interface, o título curto (`friendly_title`) e os rótulos já estão em português; só a descrição ficou em inglês. | UI |
| 3 | O CSV oficial é a **fonte normativa única** (Constituição, Princípio I) e NÃO pode ser alterado nem sobrescrito no banco. | `docs/*.csv`, `app/database.py` |

**Decisão de design**: a tradução é uma **camada de apresentação** em `config/req_tool_mapping.yaml` (campo `description_pt`), mantendo `req_description` (inglês, normativo) intacto e disponível como "Texto original (ASVS 5.0)".

## 2. User Scenarios & Testing

### User Story 1 — Descrição em português em cada um dos 8 itens (P1)
Como usuário brasileiro, quero ler a descrição de cada verificação (V1.2.1, V1.2.2, V1.2.3, V1.2.4, V1.2.5, V1.3.1, V1.3.2, V1.5.1) em português claro, para entender o que foi avaliado.

**Acceptance Scenarios**
1. **Given** uma execução concluída, **When** a tabela "Resultado por Verificação" é renderizada, **Then** cada um dos 8 itens exibe `description_pt` como descrição principal, com `lang="pt-BR"`.
2. **Given** o modal "Ver Detalhes", **When** aberto, **Then** exibe a descrição em português.
3. **Given** `description_pt` ausente para um requisito, **When** renderizado, **Then** a UI usa `req_description` (inglês, `lang="en"`) como fallback, sem erro.
4. **Given** impressão/exportação HTML/JSON do relatório, **When** gerada, **Then** contém `description_pt` e `req_description`.

### User Story 2 — Rastreabilidade ao texto normativo (P1)
Como auditor, quero acessar o texto original em inglês de cada requisito, para conferir a fidelidade da tradução.

**Acceptance Scenarios**
1. **Given** cada item, **When** exibido, **Then** há um controle recolhível `<details>` "Texto original (ASVS 5.0, inglês)" com `req_description` literal do CSV (`lang="en"`), aberto automaticamente na impressão.
2. **Given** o banco de dados, **When** inspecionado, **Then** `Requirement.req_description` permanece idêntico ao CSV (sem tradução gravada no SQLite).

## 3. Textos em português propostos (a validar no Gate 1)

| Req | `description_pt` |
| :-- | :--- |
| V1.2.1 | Verificar se a codificação de saída de respostas HTTP, documentos HTML ou XML é adequada ao contexto, codificando os caracteres relevantes para elementos, atributos e comentários HTML, CSS ou cabeçalhos HTTP, de modo a não alterar a estrutura da mensagem ou do documento. |
| V1.2.2 | Verificar se, ao montar URLs dinamicamente, os dados não confiáveis são codificados conforme o contexto (ex.: codificação de URL ou base64url em parâmetros de consulta ou de caminho) e se apenas protocolos de URL seguros são permitidos (ex.: bloquear `javascript:` e `data:`). |
| V1.2.3 | Verificar se codificação ou escape é aplicado ao montar conteúdo JavaScript dinamicamente (incluindo JSON), evitando alterar a estrutura da mensagem ou do documento (injeção de JavaScript e de JSON). |
| V1.2.4 | Verificar se seleções de dados e consultas ao banco (ex.: SQL, HQL, NoSQL, Cypher) usam consultas parametrizadas, ORMs ou frameworks de entidades, ou estão protegidas de outro modo contra injeção de SQL e demais injeções em bancos de dados. Também vale para a escrita de stored procedures. |
| V1.2.5 | Verificar se a aplicação protege contra injeção de comandos do sistema operacional e se as chamadas ao SO usam consultas parametrizadas ou codificação contextual da linha de comando. |
| V1.3.1 | Verificar se toda entrada HTML não confiável, vinda de editores WYSIWYG ou similares, é sanitizada com uma biblioteca ou recurso de framework de sanitização de HTML conhecido e seguro. |
| V1.3.2 | Verificar se a aplicação evita `eval()` ou outros recursos de execução dinâmica de código, como Spring Expression Language (SpEL). Quando não houver alternativa, toda entrada do usuário incluída deve ser sanitizada antes da execução. |
| V1.5.1 | Verificar se a aplicação configura os parsers XML de forma restritiva e desabilita recursos inseguros, como a resolução de entidades externas, para prevenir ataques XXE (XML eXternal Entity). |

## 4. Requisitos Funcionais
- **FR-001**: `config/req_tool_mapping.yaml` DEVE conter `description_pt` não vazio para os 8 requisitos em escopo.
- **FR-002**: `build_full_report_dict` e `/api/requirements/in-scope` DEVEM expor `description_pt` (campo aditivo) mantendo `req_description` inalterado.
- **FR-003**: A UI DEVE exibir `description_pt` como descrição principal, com fallback para `req_description`, e o texto original recolhível (US2).
- **FR-004**: `Requirement.req_description` no SQLite e o CSV normativo NÃO DEVEM ser modificados.
- **FR-005**: Nenhuma alteração em vereditos, guardrails ACI/ZAP/IA, schema do banco ou escopo (V1 L1, 8 requisitos).
- **FR-006**: WCAG 2.2 AA: `lang` correto por trecho (`pt-BR`/`en`), contraste, temas claro/escuro.

## 5. Fora de Escopo
Tradução automática por IA em runtime; internacionalização completa (i18n); tradução dos demais 337 requisitos.

## 6. Critérios de Sucesso
- **SC-001**: 100% dos 8 itens exibem descrição em português na tabela e no modal.
- **SC-002**: Texto original em inglês acessível em todos os 8 itens; CSV e banco inalterados.
- **SC-003**: `pytest -q` sem novas regressões (falhas pré-existentes do Semgrep em `test_aci.py` e `test_pipeline_integration.py` ficam fora do critério).
