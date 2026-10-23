# Tasks: 015 — Descrição dos requisitos em Resultado por Verificação

## Fase 1 — TDD (test-author)
- [ ] T001 Teste: `build_full_report_dict` retorna `req_description` e `friendly_title` não vazios para os 8 vereditos (V1.2.1–V1.5.1).
- [ ] T002 Teste: `/api/requirements/in-scope` retorna `friendly_title` para os 8 itens.
- [ ] T003 Teste: `GET /` não contém a coluna "O que foi verificado" e `#verdicts-table` tem 4 colunas; `colspan="4"` nas linhas vazias.
- [ ] T004 Teste: `app.js` referencia `friendly_title`, fallback de catálogo e a mensagem "Descrição normativa indisponível" apenas como último recurso.

## Fase 2 — Backend (backend-implementer)
- [ ] T005 Adicionar `friendly_title` aos 8 requisitos em `config/req_tool_mapping.yaml`.
- [ ] T006 Expor `friendly_title` em `reporter_agent.py` e `/api/requirements/in-scope`.

## Fase 3 — Frontend (frontend-implementer)
- [ ] T007 Remover coluna extra em `templates/index.html`; ajustar colspans.
- [ ] T008 Atualizar `renderVerdictsTable` (título + descrição, `lang="en"`, fallback via catálogo).
- [ ] T009 Ajustar `theme.css` (responsivo, impressão, temas claro/escuro, contraste AA).

## Fase 4 — Revisão e Gate
- [ ] T010 `.venv/bin/pytest -q` verde; verificação visual dos 8 itens em tema claro/escuro e impressão.
- [ ] T011 `constitution-guardian` (gate final).
- [ ] T012 Fase 6: commit semântico `feat(spec-015): ...` e `git push origin main`.
