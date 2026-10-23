# Tasks: 005-production-grade-ui-redesign

**Spec Reference**: [`specs/005-production-grade-ui-redesign/spec.md`](spec.md)  
**Plan Reference**: [`specs/005-production-grade-ui-redesign/plan.md`](plan.md)  
**Status**: Ready for Implementation (TDD Ready)

---

## Phase 1: Setup & Automated TDD Tests (Blocking Prerequisites)

**Purpose**: Criar os testes automatizados que comprovam a ausência de ASVS 4.0 e garantem a integridade dos guardrails antes de qualquer alteração no código.

- [x] T001 Criar suite de testes de apresentação em `tests/test_ui_presentation.py` validando ausência de `"Equivalência ASVS 4.0"` e presença dos guardrails.
- [x] T002 Executar `.venv/bin/pytest tests/test_ui_presentation.py` e certificar que falha nos pontos esperados antes da implementação (TDD).

---

## Phase 2: User Story 1 — Remoção do ASVS 4.0 e Foco no ASVS 5.0 (Priority: P1 🎯 MVP)

**Goal**: Eliminar menções a versões legadas no Catálogo e no Dashboard de Vereditos.  
**Independent Test**: Carregar `#panel-catalog` e `#panel-dashboard` e comprovar zero referências a `ASVS 4.0`.

- [x] T003 [US1] Remover a coluna `<th>Equivalência ASVS 4.0</th>` e subtítulos no template `templates/index.html`.
- [x] T004 [US1] Remover a geração da célula `tdMap` em `renderInScopeCatalog` no script `static/app.js`.
- [x] T005 [US1] Remover a concatenação da descrição secundária `ASVS 4.0: V...` em `renderVerdictsTable` no script `static/app.js`.

**Checkpoint**: User Story 1 completa e testável de forma independente.

---

## Phase 3: User Story 2 — Interface Limpa de Diagnóstico e IA (Priority: P1)

**Goal**: Apresentar resumo executivo e painel de IA corporativo sem jargões de código ou depuração interna.  
**Independent Test**: Inspecionar visualmente o cabeçalho de `#panel-assessment` e `#ai-config-panel`.

- [x] T006 [US2] Substituir concatenação crua de IDs e classes internas por resumo executivo em `templates/index.html`.
- [x] T007 [US2] Reformular os rótulos do painel de IA (`#ai-config-panel`) para *"Motor de Análise Cognitiva de Código"* com foco em privacidade em `templates/index.html`.
- [x] T008 [US2] Compactar o indicador de prontidão de serviço do ZAP (`#zap-status-panel`) em `templates/index.html`.

**Checkpoint**: Formulário limpo e corporativo, pronto para uso em produção.

---

## Phase 4: User Story 3 — Central de Achados com Foco em Remediação (Priority: P2)

**Goal**: Priorizar orientações de mitigação no modal de detalhes do achado.

- [x] T009 [US3] Reorganizar o modal de detalhes (`openFindingDetailsModal` em `static/app.js`) para destacar trecho de código e remediação recomendada.

---

## Phase 5: Verificação, Regressão e Revisão de Segurança

**Purpose**: Garantir que a suíte de testes passa com 100% de sucesso e certificar conformidade com a Constituição v1.3.0.

- [x] T010 Executar suíte completa de testes: `.venv/bin/pytest -q`.
- [x] T011 Acionar `aci-security-reviewer` para atestar que nenhum guardrail foi violado.
- [x] T012 Acionar `constitution-guardian` para emissão do parecer final de conformidade.

