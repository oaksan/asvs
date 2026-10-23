# Tasks: 017 — Correção do payload de vereditos e descrições em português

## Fase 1 — TDD (test-author)
- [ ] T001 Teste de contrato: `GET /api/runs/{id}` com 8 vereditos semeados retorna `section_id`, `section_name`, `req_description` (= CSV), `friendly_title`, `description_pt` para V1.2.1–V1.5.1.
- [ ] T002 Teste de contrato: `GET /api/runs/{id}/verdicts` retorna os mesmos campos; RBAC preservado (usuário sem acesso recebe 403/404).
- [ ] T003 Teste estático: `app.js` não concatena campos sem `safeText`/fallback (`v.section_id + " — "` ausente) e usa derivação por `req_id`.
- [ ] T004 Teste: rodapé/health expõem a versão `017`.

## Fase 2 — Backend (backend-implementer)
- [ ] T005 Enriquecer `list_run_verdicts` (FR-001) sem alterar `Requirement` nem o CSV.
- [ ] T006 Expor `version` (health/rodapé).

## Fase 3 — Frontend (frontend-implementer)
- [ ] T007 `safeText()`, derivação de seção e omissão de linhas vazias (FR-003/FR-004).
- [ ] T008 Rodapé com versão; bump `?v=017` em `index.html` e nos testes de cache.

## Fase 4 — Docs e Revisão
- [ ] T009 README: rebuild/restart após mudanças em Python (FR-006).
- [ ] T010 `docker compose up --build -d` e verificação visual dos 8 itens em português, sem `undefined` (claro/escuro, impressão).
- [ ] T011 `.venv/bin/pytest -q` sem novas regressões; `constitution-guardian` (gate final).
- [ ] T012 Fase 6: commit `fix(spec-017): ...`, `git push origin main` e tag `v017`.
