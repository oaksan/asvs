# Especificação de Funcionalidade (SDD): Descrição de cada requisito ASVS em "Resultado por Verificação"

**Feature Branch**: `015-results-requirement-descriptions`
**Created**: 2026-10-22
**Status**: Draft (aguardando Gate 1)
**Input**: *"Em 2. Resultados & Compliance, em Resultado por Verificação, inclua a descrição para cada item do ASVS apresentado, de V1.2.1 até V1.5.1."*

---

## 1. Diagnóstico

| # | Observação | Local |
| :-: | :--- | :--- |
| 1 | A coluna "O que foi verificado" já existe (Feature 014), mas fica separada do identificador, logo à direita do badge de resultado; o usuário lê `V1.2.1` + `Aprovado` sem a descrição ao lado. | `templates/index.html` (`#verdicts-table`), `static/app.js` (`renderVerdictsTable`) |
| 2 | A descrição é em inglês (texto normativo do CSV ASVS 5.0) e não traz um título curto legível. | `Requirement.req_description` |
| 3 | Se a descrição vier vazia, a UI mostra "Descrição normativa indisponível" sem tentar obter do catálogo (`/api/requirements/in-scope`). | `renderVerdictsTable` |
| 4 | Impressão/exportação precisam manter a descrição visível em todos os 8 itens (V1.2.1–V1.2.5, V1.3.1, V1.3.2, V1.5.1). | `reporter_agent`, CSS `@media print` |

## 2. User Scenarios & Testing

### User Story 1 — Descrição junto de cada item (P1)
Como usuário, quero ver, na própria célula do item (ex.: **V1.2.1**), a descrição completa do requisito, para entender o que cada resultado significa sem abrir "Ver Detalhes".

**Acceptance Scenarios**
1. **Given** uma execução concluída com 8 vereditos, **When** a tabela é renderizada, **Then** cada linha, de `V1.2.1` a `V1.5.1`, exibe sob o identificador a descrição completa (`req_description`), sem truncar e com quebra de linha.
2. **Given** `req_description` ausente no relatório, **When** renderizado, **Then** a UI usa a descrição do catálogo em escopo (`/api/requirements/in-scope`); somente se também ausente, exibe "Descrição normativa indisponível".
3. **Given** a tela estreita (≤ 768 px) ou a impressão, **When** renderizada, **Then** a descrição permanece visível (sem depender de hover) e a tabela não gera rolagem horizontal ilegível.
4. **Given** os filtros por resultado/categoria, **When** aplicados, **Then** a descrição acompanha cada linha filtrada.

### User Story 2 — Título curto amigável (P2)
Como usuário, quero um título curto em português acima da descrição normativa (ex.: "Prevenção de injeção de SQL"), para leitura rápida.

**Acceptance Scenarios**
1. **Given** cada um dos 8 requisitos, **When** exibido, **Then** há um título curto vindo de `config/req_tool_mapping.yaml` (campo `friendly_title`) com fallback para `section_name`.
2. **Given** a descrição original em inglês, **When** exibida, **Then** é mantida fiel ao texto normativo (não traduzida automaticamente) e marcada com `lang="en"` para leitores de tela.

## 3. Requisitos Funcionais
- **FR-001**: A UI DEVE exibir `req_id`, título curto e `req_description` completa na primeira coluna de `#verdicts-table` para todos os requisitos avaliados.
- **FR-002**: A coluna separada "O que foi verificado" DEVE ser removida (conteúdo incorporado à primeira coluna), mantendo 4 colunas: Verificação, Resultado, Detalhes técnicos, Ações.
- **FR-003**: O relatório (`build_full_report_dict`) DEVE sempre incluir `req_description` e `friendly_title` por veredito; JSON/HTML exportados DEVEM refletir ambos.
- **FR-004**: Fallback de descrição via catálogo em escopo; sem erro de JavaScript em nenhum caso.
- **FR-005**: Nenhuma alteração no cálculo de vereditos, em guardrails ACI/ZAP/IA ou em endpoints existentes (apenas campo aditivo `friendly_title`).
- **FR-006**: Conformidade WCAG 2.2 AA (contraste, `lang="en"` no texto normativo, sem informação só por cor) e temas claro/escuro.

## 4. Fora de Escopo
Reintroduzir a aba de catálogo; traduzir automaticamente o texto normativo; alterar escopo (V1 L1, 8 requisitos).

## 5. Critérios de Sucesso
- **SC-001**: 100% dos 8 itens (V1.2.1–V1.5.1) exibem descrição na tabela de resultados.
- **SC-002**: Suíte `pytest -q` sem regressões; novos testes cobrem FR-001..FR-004.
