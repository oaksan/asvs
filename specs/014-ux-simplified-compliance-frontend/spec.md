# Especificação de Funcionalidade (SDD): Experiência do Usuário Simplificada e Foco em Percentual de Compliance

**Feature Branch**: `014-ux-simplified-compliance-frontend`
**Created**: 2026-10-21
**Status**: Draft (aguardando Gate 1)
**Input**: *"crie o sdd para melhorar a interface gráfica (frontend) como um todo voltado à experiência do usuário. Por exemplo, o usuário não precisa conhecer que estamos avaliando 8 itens dos 345 do ASVS, ele apenas quer testar a aplicação e verificar o percentual de compliance, portanto, remova a lapela 3. Catálogo ASVS 5.0 (8 / 345) e inclua os campos de descrição na lapela 2. Dashboard & Vereditos (8 Req)."*

---

## 1. Diagnóstico da Interface Atual (`templates/index.html` + `static/app.js`)

| # | Problema de UX | Local | Impacto |
| :-: | :--- | :--- | :--- |
| 1 | Jargão interno exposto: "8 Req", "8 / 345", "V1 L1", "Capítulo V1 Level 1 — 8 Requisitos", "SSE" | Cabeçalho, abas, títulos de cartões | Usuário precisa entender o ASVS para usar a ferramenta |
| 2 | Aba **3. Catálogo ASVS 5.0 (8 / 345)** (`#tab-catalog`, `#panel-catalog`) com 345 requisitos fora do escopo avaliativo | Navegação | Ruído; o usuário quer apenas testar a aplicação e ver o % de compliance |
| 3 | Descrição normativa de cada requisito só existe no catálogo, não junto ao veredito | Aba 2 (tabela `#verdicts-table`) | Usuário vê `V1.2.4: PASS` sem saber o que isso significa |
| 4 | Vereditos técnicos em inglês/identificadores (`PASS`, `FAIL`, `INCONCLUSIVE`, `MANUAL_REQUIRED`) e métrica "% Conformidade PASS (Sobre 8)" | Cartões de métricas, badges, filtros | Linguagem pouco amigável; o número principal (% de compliance) não é o herói da tela |
| 5 | Tabela de vereditos com 7 colunas densas (ferramentas, regras, cobertura, justificativa, limitações) sempre visíveis | Aba 2 | Sobrecarga de informação para o usuário final |
| 6 | Numeração de abas ("1.", "2.", "3.", "4.") quebra ao remover uma aba | Navegação | Inconsistência |

---

## 2. User Scenarios & Testing *(mandatory)*

### User Story 1 — Remover a aba Catálogo e simplificar a navegação (Priority: P1)

Como usuário final, quero uma navegação enxuta (**Nova Avaliação**, **Resultados**, **Histórico**, **Configuração de IA**, **Usuários** quando administrador), sem a aba de catálogo ASVS e sem referências a "8 / 345".

**Independent Test**: Renderizar `GET /` e verificar que não existem `#tab-catalog`, `#panel-catalog`, `#in-scope-catalog-tbody`, `#full-catalog-tbody`, `#catalog-*`, nem os textos `345` e `8 / 345`; as abas restantes são renumeradas sem lacunas.

**Acceptance Scenarios**:

1. **Given** a página inicial, **When** carregada, **Then** a barra de abas contém apenas: `1. Nova Avaliação`, `2. Resultados & Compliance`, `3. Histórico & Comparação`, `4. Configuração de IA` (+ `5. Usuários` para `admin`), e nenhuma aba de catálogo.
2. **Given** o JavaScript carregado, **When** `init` executa, **Then** NÃO são feitas chamadas a `/api/requirements` nem a `/api/requirements/in-scope` apenas para popular o catálogo (as rotas permanecem disponíveis no backend por compatibilidade e testes).
3. **Given** a navegação por teclado, **When** o usuário usa setas ←/→ entre abas, **Then** o foco percorre somente as abas existentes (WCAG 2.2 AA preservado).

### User Story 2 — Descrição de cada requisito na aba de resultados (Priority: P1)

Como usuário, quero ver, junto de cada veredito na aba **Resultados & Compliance**, o **título/descrição em linguagem clara do que foi verificado** e a **descrição normativa ASVS** do requisito, para entender o resultado sem consultar outra tela.

**Independent Test**: Com uma execução concluída, cada linha de `#verdicts-table` exibe `req_id`, a seção e a descrição (`req_description`) já fornecida em `report.verdicts[].req_description` por `reporter_agent.build_full_report_dict`.

**Acceptance Scenarios**:

1. **Given** uma execução com 8 vereditos, **When** a tabela é renderizada, **Then** cada requisito mostra uma coluna **"O que foi verificado"** com `req_description` completo (quebra de linha, sem truncar), além de `req_id` e nome da seção.
2. **Given** um `req_description` vazio (dado ausente), **When** renderizado, **Then** a UI exibe "Descrição normativa indisponível" sem erro de JavaScript.
3. **Given** a exportação HTML estática/JSON, **When** gerada, **Then** a descrição continua presente (sem regressão em `reporter_agent`).
4. **Given** o modal "Ver Detalhes" (`openRequirementModal`), **When** aberto, **Then** exibe também a descrição normativa completa.

### User Story 3 — Percentual de compliance como destaque central (Priority: P1)

Como usuário, quero ver logo no topo dos resultados um indicador grande **"Compliance: NN%"** com uma frase de resumo (ex.: "6 de 8 verificações aprovadas; 1 reprovada; 1 requer atenção"), em vez de métricas técnicas "Sobre 8".

**Acceptance Scenarios**:

1. **Given** uma execução concluída, **When** a aba Resultados é exibida, **Then** um cartão-herói mostra `pass_percentage` formatado (ex.: `75%`) com barra/anel de progresso acessível (`role="progressbar"`, `aria-valuenow`) e a frase de resumo calculada com `pass_count`, `fail_count`, `inconclusive_count`, `manual_count` e total.
2. **Given** a execução com verificações pendentes (`INCONCLUSIVE`/`MANUAL_REQUIRED`), **When** o resumo é exibido, **Then** o texto informa honestamente que essas verificações **não** entraram como aprovadas (preserva o Princípio II — o percentual continua sendo `PASS / total`, sem alteração de cálculo no backend).
3. **Given** nenhuma execução carregada, **When** a aba é aberta, **Then** é mostrado um estado vazio orientativo com botão "Iniciar nova avaliação".

### User Story 4 — Linguagem amigável e divulgação progressiva de detalhes técnicos (Priority: P2)

Como usuário, quero rótulos em português claro (**Aprovado**, **Reprovado**, **Inconclusivo**, **Revisão manual**), e que detalhes técnicos (ferramentas, regras executadas, cobertura, limitações) fiquem recolhidos em "Detalhes técnicos".

**Acceptance Scenarios**:

1. **Given** a tabela de resultados, **When** renderizada, **Then** os badges exibem os rótulos amigáveis, mantendo o valor técnico no `title`/`aria-label` e nas classes CSS (`badge-PASS` etc.) e nos dados exportados (JSON/HTML permanecem com os códigos originais).
2. **Given** cada requisito, **When** exibido, **Then** colunas **Confiança**, **Ferramentas & Regras**, **Cobertura & Evidência Positiva** e **Justificativa & Limitações** ficam dentro de um bloco recolhível `<details>` "Detalhes técnicos" (fechado por padrão; aberto na impressão/PDF via `@media print`).
3. **Given** o cabeçalho, **When** renderizado, **Then** o selo "Escopo: V1 (Encoding & Sanitization) • Level 1 • 8 Requisitos" é substituído por um texto neutro (ex.: "Avaliação de segurança de aplicações — OWASP ASVS 5.0") e títulos como "Vereditos por Requisito (Capítulo V1 Level 1 — 8 Requisitos)" viram "Resultado por verificação".

### User Story 5 — Polimento geral de UX, acessibilidade e responsividade (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a aba Nova Avaliação, **When** uma execução é iniciada com sucesso, **Then** a UI navega automaticamente para **Resultados & Compliance** ao concluir (comportamento atual preservado) e exibe mensagens de erro/validação inline com `role="alert"`.
2. **Given** viewport ≤ 768 px, **When** a página é exibida, **Then** as abas fazem scroll horizontal, cartões empilham em 1 coluna e tabelas permitem rolagem horizontal sem quebrar o layout.
3. **Given** tema claro e escuro, **When** alternados, **Then** o novo cartão-herói e os badges mantêm contraste mínimo WCAG 2.2 AA (≥ 4.5:1 para texto).
4. **Given** o botão primário "Iniciar Avaliação V1 L1", **When** renderizado, **Then** o rótulo é "Iniciar Avaliação".

---

## 3. Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Remover de `templates/index.html` o botão `#tab-catalog` e a seção `#panel-catalog` (tabelas `#in-scope-catalog-tbody` e `#full-catalog-tbody`, filtros e paginação `#catalog-*`) e de `static/app.js` as funções `loadInScopeCatalog`, `loadFullCatalog`, `initCatalogControls`, o estado `catalogPage/catalogTotalPages` e as chamadas correspondentes em `init`.
- **FR-002**: Renumerar as abas restantes sem lacunas e remover toda menção textual a "8 Req", "8 / 345", "345 requisitos", "V1 L1" e "Capítulo V1 Level 1" da interface visível ao usuário (cabeçalho, abas, títulos, `aria-label`s e rótulos de botão). Termos técnicos permanecem em dados exportados e no backend.
- **FR-003**: Em `renderVerdictsTable` (`static/app.js`), exibir `v.req_description` em coluna **"O que foi verificado"** (com tratamento de valor vazio) e incluí-la no modal `openRequirementModal`.
- **FR-004**: Criar cartão-herói de compliance (`#compliance-hero`) em `#panel-dashboard`, alimentado por `report.metrics`/`compute_run_metrics` (já existente), com `role="progressbar"`, frase de resumo e estado vazio orientativo. Substituir os cinco cartões atuais por contadores compactos com rótulos amigáveis (Aprovadas, Reprovadas, Inconclusivas, Revisão manual).
- **FR-005**: Mapear rótulos amigáveis de veredito exclusivamente na camada de apresentação (`createVerdictBadge`, filtros `#filter-verdict-status`, legendas dos gráficos), sem alterar valores persistidos, API, JSON/HTML exportados ou classes CSS de status.
- **FR-006**: Agrupar colunas técnicas em `<details class="tech-details">` por requisito, fechado por padrão e forçado aberto em `@media print`.
- **FR-007**: Ajustes de CSS (`static/theme.css`) para cartão-herói, `tech-details`, abas roláveis em telas pequenas, contraste em tema claro/escuro e incremento do cache-busting (`?v=014`) em `theme.css` e `app.js`.
- **FR-008 (Preservação Backend/Constituição)**: NÃO alterar `app/verdict.py`, regras SAST/DAST, `req_tool_mapping.yaml`, seed do catálogo (345 requisitos no SQLite) nem os endpoints `GET /api/requirements` e `GET /api/requirements/in-scope`. O cálculo `pass_percentage = PASS / total_in_scope` permanece inalterado (Princípio II).
- **FR-009 (Emenda Documental)**: Registrar que esta feature **substitui o requisito de tela de catálogo da Feature 001 (US3 / FR-001)**: a consulta aos 345 requisitos deixa de ter UI dedicada, permanecendo disponível via API somente leitura. Submeter a emenda ao `constitution-guardian` (Gate 1) para confirmar que o catálogo continua exigido apenas como **dado/seed e API** (Constituição, Catálogo de Dados), não como tela.

### Key Entities
- Nenhuma nova entidade, tabela ou coluna. Mudança restrita a `templates/`, `static/` e testes de apresentação.

---

## 4. Success Criteria *(mandatory)*

- **SC-001**: `GET /` não contém `tab-catalog`, `panel-catalog`, `8 / 345`, `345` nem `8 Req` no HTML renderizado.
- **SC-002**: Para uma execução com 8 vereditos, 100% das linhas da tabela exibem a descrição do requisito (nenhum `undefined`/vazio sem fallback).
- **SC-003**: O percentual de compliance aparece no primeiro viewport da aba Resultados, com valor idêntico a `report.metrics.pass_percentage`.
- **SC-004**: Nenhuma regressão: suíte `.venv/bin/pytest -q` (121 testes atuais) continua passando; JSON/HTML exportados permanecem com códigos de veredito originais.
- **SC-005**: Conformidade WCAG 2.2 AA mantida (navegação por teclado, `role="progressbar"`, contraste, `lang="pt-BR"`).

## 5. Fora de Escopo
- Alterar escopo avaliativo (continua V1 L1), lógica de veredito, pipeline, autenticação/RBAC ou armazenamento de segredos.
- Remover endpoints de catálogo do backend ou o seed dos 345 requisitos.

