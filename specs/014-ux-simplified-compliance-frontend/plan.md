# Plano de Implementação (SDD): UX Simplificada e Foco em Compliance

**Branch**: `014-ux-simplified-compliance-frontend` | **Date**: 2026-10-21 | **Spec**: [spec.md](file:///home/user/felipe/speckit/asvs/specs/014-ux-simplified-compliance-frontend/spec.md)

---

## 1. Resumo Arquitetural

Mudança **100% de apresentação** (frontend), sem alteração de modelo de dados, contratos Pydantic, pipeline ou veredito.

1. **Navegação**: remover `#tab-catalog`/`#panel-catalog` em `templates/index.html`; renumerar abas (Nova Avaliação, Resultados & Compliance, Histórico & Comparação, Configuração de IA, Usuários). Verificar a lógica de `activateTab`/navegação por setas em `static/app.js` para que não dependa de índice fixo ou do id removido.
2. **Remoção de código morto JS**: `loadInScopeCatalog`, `loadFullCatalog`, `initCatalogControls`, `state.catalogPage/catalogTotalPages` e chamadas em `init` (linhas ~2135–2250 e ~2863–2873 de `static/app.js`). Backend mantém `/api/requirements` e `/api/requirements/in-scope` (usados por `tests/test_pipeline_integration.py`).
3. **Descrição nos resultados**: `report.verdicts[].req_description` já é entregue por `reporter_agent.build_full_report_dict` (linha ~118). Nenhuma mudança de backend: `renderVerdictsTable` passa a renderizar a coluna **"O que foi verificado"** e `openRequirementModal` mostra a descrição completa; fallback "Descrição normativa indisponível".
4. **Cartão-herói de compliance** (`#compliance-hero`): usa `report.metrics` existente (`pass_percentage`, `pass_count`, `fail_count`, `inconclusive_count`, `manual_count`). Frase de resumo gerada em JS (`buildComplianceSummary(metrics)`), com `role="progressbar"`, `aria-valuenow`, estado vazio com CTA para a aba Nova Avaliação.
5. **Rótulos amigáveis**: dicionário `VERDICT_LABELS_PT = {PASS:"Aprovado", FAIL:"Reprovado", INCONCLUSIVE:"Inconclusivo", MANUAL_REQUIRED:"Revisão manual"}` aplicado somente em `createVerdictBadge`, filtro de status, legendas dos gráficos e cartões; valores/classes/dados exportados permanecem técnicos.
6. **Divulgação progressiva**: colunas técnicas (confiança, ferramentas/regras, cobertura/evidência positiva, justificativa/limitações) dentro de `<details class="tech-details">`; `@media print { .tech-details { display:block } .tech-details > *{display:block} }` + abrir via CSS/JS no `beforeprint` para o PDF/HTML estático permanecerem completos.
7. **Texto/UX geral**: substituir jargão em cabeçalho (`.scope-pill`), títulos, `aria-label`s e botão "Iniciar Avaliação"; abas com `overflow-x:auto` em ≤ 768 px; bump de cache-busting `?v=014`.

## 2. Constituição Check (Gate Validation)

- **Princípio I (Escopo V1 L1)**: avaliação inalterada; apenas a *comunicação* deixa de citar "8/345". Seed e API do catálogo preservados → conformidade mantida. **Pendência de Gate 1**: Feature 001 US3/FR-001 previa tela de catálogo; esta feature emenda esse requisito de UI (FR-009) — `constitution-guardian` deve confirmar que a Constituição exige o catálogo apenas como dado/seed/API.
- **Princípio II (Honestidade Epistêmica)**: `pass_percentage` continua `PASS/total`; resumo informa explicitamente verificações Inconclusivas/Revisão manual como não aprovadas. Rótulos amigáveis não ocultam o código técnico (`title`/`aria-label`).
- **Princípio III**: sem alteração de persistência/orquestração.
- **Princípio IV (Guardrails)**: sem novas execuções de comandos, arquivos ou credenciais; renderização apenas via `textContent`/`el()` (sem `innerHTML` com dados) para manter XSS-safe e CSP (`script-src 'self' https://unpkg.com`) da Feature 013.
- **Princípio V (Fluent 2 / WCAG 2.2 AA)**: progressbar acessível, contraste claro/escuro, navegação por teclado.
- **Princípio VI (SDD/TDD)**: testes de apresentação escritos antes (Red → Green).

## 3. Arquivos Modificados

1. [templates/index.html](file:///home/user/felipe/speckit/asvs/templates/index.html) — remoção da aba/painel de catálogo, renumeração, cartão-herói, textos, `?v=014`.
2. [static/app.js](file:///home/user/felipe/speckit/asvs/static/app.js) — remoção do catálogo, `renderVerdictsTable`, `openRequirementModal`, `renderMetricCards`, `createVerdictBadge`, `buildComplianceSummary`, `VERDICT_LABELS_PT`.
3. [static/theme.css](file:///home/user/felipe/speckit/asvs/static/theme.css) — `.compliance-hero`, `.tech-details`, abas roláveis, contraste, regras de impressão.
4. [tests/test_ui_presentation.py](file:///home/user/felipe/speckit/asvs/tests/test_ui_presentation.py) — novos testes (abaixo) e ajuste de eventuais asserções que referenciem o catálogo.
5. `specs/001-asvs-v1-assessment/spec.md` — nota de emenda (US3 passa a ser atendida somente via API).

## 4. Estratégia de Testes (TDD)

- `test_ui_has_no_catalog_tab_or_catalog_jargon`: `GET /` sem `tab-catalog`, `panel-catalog`, `8 / 345`, `345 Requisitos`, `8 Req`.
- `test_ui_navigation_tabs_renumbered_without_gaps`.
- `test_app_js_has_no_catalog_loaders_and_keeps_requirements_api`: `app.js` sem `loadFullCatalog`/`loadInScopeCatalog`; `GET /api/requirements/in-scope` ainda retorna 8 itens.
- `test_verdicts_table_renders_requirement_description_column` (inspeção de `app.js`: `req_description` + fallback) e `test_report_verdicts_include_req_description` (API de relatório).
- `test_ui_includes_compliance_hero_with_progressbar` e `test_ui_friendly_verdict_labels_do_not_change_exported_codes`.
- Regressão: `.venv/bin/pytest -q` completo.

