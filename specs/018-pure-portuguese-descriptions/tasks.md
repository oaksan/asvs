# Tarefas de Implementação: 018 — Descrição Exclusiva em Português para V1.2.1 a V1.5.1

## Fase 1 — TDD & Preparação de Testes
- [ ] T001: Criar suíte de testes `tests/test_feature_018_pure_portuguese.py` validando que `static/app.js` não contém o texto `"Texto original (ASVS 5.0, inglês)"` e que os 8 itens possuem descrição em português completa.
- [ ] T002: Atualizar testes de versão e cache-busting existentes para a versão `018` (`tests/test_ui_presentation.py` e `tests/test_zip_upload_run.py`).

## Fase 2 — Frontend & Apresentação
- [ ] T003: Editar `static/app.js` na função `appendRequirementDescription`: remover a criação do elemento `<details class="req-original">` e exibir unicamente a descrição em português.
- [ ] T004: Atualizar `templates/index.html` com o bump de versão `?v=018`.
- [ ] T005: Atualizar `APP_UI_VERSION = "018"` em `app/main.py`.

## Fase 3 — Verificação & Container
- [ ] T006: Executar a suíte de testes pytest direcionada e garantir 100% de aprovação.
- [ ] T007: Reconstruir o container Docker (`docker compose up --build -d web`) e verificar se a versão 018 está ativa via curl.

## Fase 4 — Versionamento & Sincronização GitHub
- [ ] T008: Marcar todas as tarefas como concluídas em `tasks.md`.
- [ ] T009: Executar commit semântico `feat(spec-018): descrição exclusiva em português de V1.2.1 a V1.5.1`.
- [ ] T010: Criar tag semântica `v018` e enviar via `git push origin main v018`.
