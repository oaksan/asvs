# Tarefas de Implementação: 020 — Preenchimento Correto de "Resultados por Categoria"

## Fase 1 — TDD & Preparação de Testes
- [ ] T001: Criar teste de contrato `tests/test_feature_020_section_breakdown.py` validando que `GET /api/runs/{run_id}` retorna o dicionário `section_breakdown` com as 3 seções e seus respectivos contadores.
- [ ] T002: Atualizar testes de versão e cache-busting existentes para a versão `020` (`tests/test_ui_presentation.py` e `tests/test_zip_upload_run.py`).

## Fase 2 — Backend & Frontend
- [ ] T003: Em `app/main.py`, importar `build_section_breakdown` e incluir o campo `"section_breakdown"` na resposta de `get_run_details`.
- [ ] T004: Atualizar `APP_UI_VERSION = "020"` em `app/main.py`.
- [ ] T005: Em `static/app.js`, implementar fallback defensivo em `renderCharts` e melhorar apresentação visual das barras com contadores/porcentagens.
- [ ] T006: Atualizar `templates/index.html` com o bump de versão `?v=020`.

## Fase 3 — Verificação & Container
- [ ] T007: Executar a suíte de testes pytest direcionada e garantir 100% de aprovação.
- [ ] T008: Reconstruir o container Docker (`docker compose up --build -d web`) e verificar via curl a resposta da versão 020 e a chave `section_breakdown`.

## Fase 4 — Versionamento & Sincronização GitHub
- [ ] T009: Marcar todas as tarefas em `tasks.md` como concluídas.
- [ ] T010: Executar commit semântico `fix(spec-020): preenchimento correto das barras de Resultados por Categoria`.
- [ ] T011: Criar tag semântica `v020` e enviar ao GitHub via `git push origin main v020`.
