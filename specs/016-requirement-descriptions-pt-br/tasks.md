# Tasks: 016 — Descrições dos requisitos em português

## Fase 1 — TDD (test-author)
- [ ] T001 Teste: mapping tem `description_pt` não vazio para V1.2.1–V1.5.1 (8 itens).
- [ ] T002 Teste: `/api/requirements/in-scope` retorna `description_pt` e `req_description` (inglês) inalterado em relação ao CSV.
- [ ] T003 Teste: `build_full_report_dict` inclui `description_pt` por veredito.
- [ ] T004 Teste: `app.js` referencia `description_pt`, `lang: "pt-BR"`, "Texto original" e fallback para `req_description`.
- [ ] T005 Teste: `Requirement.req_description` no banco permanece igual ao CSV (FR-004).

## Fase 2 — Backend (backend-implementer)
- [ ] T006 Adicionar `description_pt` aos 8 requisitos em `config/req_tool_mapping.yaml`.
- [ ] T007 Expor `description_pt` em `reporter_agent.py` e `/api/requirements/in-scope`.

## Fase 3 — Frontend (frontend-implementer)
- [ ] T008 Atualizar `renderVerdictsTable` e `openRequirementModal` (PT principal, `<details>` com original em inglês, fallback).
- [ ] T009 Ajustar `theme.css` e bump `?v=016` em `index.html` e testes de cache.

## Fase 4 — Revisão e Gate
- [ ] T010 `.venv/bin/pytest -q` sem novas regressões; verificação visual dos 8 itens (claro/escuro, impressão).
- [ ] T011 `constitution-guardian` (gate final).
- [ ] T012 Fase 6: commit `feat(spec-016): ...`, `git push origin main` e tag `v016`.
