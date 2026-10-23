# Tarefas de Implementação: 019 — Descrição Completa em Bloco Recolhível para V1.2.1 a V1.5.1

## Fase 1 — TDD & Preparação de Testes
- [ ] T001: Criar suíte de testes `tests/test_feature_019_collapsible_descriptions.py` validando que `static/app.js` encapsula a descrição completa em português em elemento recolhível com summary `"Descrição completa"`.
- [ ] T002: Atualizar testes existentes de regressão para checar a versão `019` (`tests/test_ui_presentation.py` e `tests/test_zip_upload_run.py`).

## Fase 2 — Implementação Frontend & CSS
- [ ] T003: Editar `static/app.js` na função `appendRequirementDescription`: criar `<details class="req-desc-details">` contendo o summary `"Descrição completa"` e o corpo da descrição completa em português.
- [ ] T004: Adicionar regras de estilização em `static/theme.css` para `.req-desc-details` (tipografia, espaçamento, cursor pointer e abertura para impressão em `@media print`).
- [ ] T005: Atualizar `APP_UI_VERSION = "019"` em `app/main.py`.
- [ ] T006: Atualizar `templates/index.html` com o bump de versão `?v=019`.

## Fase 3 — Verificação & Container
- [ ] T007: Executar a suíte de testes pytest direcionada e garantir aprovação total.
- [ ] T008: Reconstruir o container Docker (`docker compose up --build -d web`) e verificar via curl a resposta da versão 019.

## Fase 4 — Versionamento & Sincronização GitHub
- [ ] T009: Marcar todas as tarefas em `tasks.md` como concluídas.
- [ ] T010: Executar commit semântico `feat(spec-019): descrição completa em bloco recolhível para V1.2.1 a V1.5.1`.
- [ ] T011: Criar tag semântica `v019` e enviar ao GitHub via `git push origin main v019`.
