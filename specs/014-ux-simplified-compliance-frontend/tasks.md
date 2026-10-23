# Tasks (SDD): UX Simplificada e Foco em Compliance (`014-ux-simplified-compliance-frontend`)

**Input**: `spec.md`, `plan.md`

## Phase 1: Specify & Plan (Gates 1 e 2)
- [ ] T001 Gerar `spec.md`, `plan.md` e `tasks.md` em `specs/014-ux-simplified-compliance-frontend/`.
- [ ] T002 `solution-architect`: validar que `report.verdicts[].req_description` e `report.metrics` cobrem os dados necessários sem mudar backend.
- [ ] T003 `constitution-guardian`: auditar Gates 1 e 2, confirmando a emenda FR-009 (catálogo mantido como seed/API, sem tela) e o Princípio II (percentual e rótulos).

## Phase 2: Testes (TDD — Red)
- [ ] T004 `test-author`: adicionar em `tests/test_ui_presentation.py` os testes listados em `plan.md` §4 e confirmar falha inicial.

## Phase 3: Implementação (Green)
- [ ] T005 `frontend-implementer`: remover aba/painel de catálogo e renumerar abas em `templates/index.html`; remover código de catálogo em `static/app.js`.
- [ ] T006 `frontend-implementer`: coluna "O que foi verificado" (`req_description` + fallback) em `renderVerdictsTable` e `openRequirementModal`.
- [ ] T007 `frontend-implementer`: cartão-herói `#compliance-hero` (progressbar acessível + resumo + estado vazio) e contadores amigáveis.
- [ ] T008 `frontend-implementer`: `VERDICT_LABELS_PT` na camada de apresentação e `<details class="tech-details">` (aberto na impressão).
- [ ] T009 `frontend-implementer`: limpar jargão ("8 Req", "8 / 345", "V1 L1"), botão "Iniciar Avaliação", CSS responsivo/contraste, cache-busting `?v=014`.
- [ ] T010 Nota de emenda em `specs/001-asvs-v1-assessment/spec.md` (US3/FR-001).

## Phase 4: Verificação, Revisão e Deploy
- [ ] T011 `.venv/bin/pytest -q` (sem regressões) e verificação visual/a11y via navegador (claro/escuro, mobile).
- [ ] T012 `aci-security-reviewer`, `llm-security-reviewer` (XSS/CSP: sem `innerHTML` com dados) e `constitution-guardian` (Gate 3 Final).
- [ ] T013 `docker build -t asvs-web:latest . && docker compose restart web`.

