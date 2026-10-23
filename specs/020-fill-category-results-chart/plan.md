# Plano de Implementação: 020 — Preenchimento Correto de "Resultados por Categoria"

## 1. Resumo Executivo
Corrigir a renderização das barras horizontais em "Resultados por Categoria", que permanecem cinzas por ausência da chave `section_breakdown` no retorno do endpoint `GET /api/runs/{run_id}`.

## 2. Análise Técnica e Arquitetural
- **Backend (`app/main.py`)**:
  - Importar `build_section_breakdown` de `app.agents.reporter_agent`.
  - Na função `get_run_details(run_id, ...)`:
    - Recuperar a lista de `Verdict` da execução.
    - Chamar `build_section_breakdown(raw_verdicts)` e incluir no dicionário de resposta como `"section_breakdown": section_breakdown`.
- **Frontend (`static/app.js`)**:
  - Em `renderCharts(report)`:
    - Implementar computação defensiva de fallback: se `report.section_breakdown` não existir, calcular a partir de `report.verdicts`.
    - Garantir que cada segmento preenchido receba a cor correta (`PASS` verde, `FAIL` vermelho, etc.) e que um rótulo com a contagem seja posicionado à direita da barra ou sobre ela para clareza imediata.
- **Cache-Busting & Versão**:
  - Atualizar `APP_UI_VERSION = "020"` em `app/main.py`.
  - Atualizar referências de assets para `?v=020` em `templates/index.html`.
- **Testes Automatizados (`tests/test_feature_020_section_breakdown.py`)**:
  - Testar que `GET /api/runs/{run_id}` contém `section_breakdown` com chaves `V1.2`, `V1.3`, `V1.5`.
  - Testar que os contadores refletem fielmente os vereditos da execução.
  - Testar que `static/app.js` possui o fallback defensivo.

## 3. Mapeamento de Mudanças por Arquivo

| Arquivo | Componente | Descrição da Modificação |
| :--- | :--- | :--- |
| `specs/020-fill-category-results-chart/` | SDD | Documentação da feature (spec, plan, tasks). |
| `app/main.py` | Backend | Inclusão de `section_breakdown` em `get_run_details` e versão 020. |
| `static/app.js` | UI Logic | Fallback e refinamento visual de `section-bars-svg`. |
| `templates/index.html` | Template | Atualização de cache-busting `?v=020`. |
| `tests/test_feature_020_section_breakdown.py` | TDD | Testes de contrato de `section_breakdown`. |
| `tests/test_ui_presentation.py` e `tests/test_zip_upload_run.py` | Regressão | Atualização de versão `020`. |
