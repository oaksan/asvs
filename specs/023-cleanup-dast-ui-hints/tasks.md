# Tarefas de Engenharia (SDD Tasks) — Feature 023: Simplificação Visual do Card DAST

**Branch**: `023-cleanup-dast-ui-hints`  
**Status**: Concluído (Aprovado em Gate Final)  

---

## Fase 1 — TDD (Testes Automatizados Pré-Implementação)
- [x] **T001**: Criar `tests/test_feature_023_cleanup_dast_ui.py` contendo testes para:
  - Validação de que as strings da allowlist, do box de modo fixo e da nota legal foram removidas.
  - Validação de que `aria-describedby="dast-auth-hint"` não está mais presente no `#zap-authorized`.
  - Validação de que os componentes funcionais do DAST (`#target-url`, `#zap-mode`, `#zap-authorized`, badge no header) permanecem íntegros.
  - Validação de versão `023`.
- [x] **T002**: Executar suíte para confirmar o estágio TDD Red (5 falharam, 1 passou conforme esperado).

---

## Fase 2 — Implementação
- [x] **T003**: Editar `templates/index.html`:
  - Remover bloco `<small>` de allowlist abaixo de `#target-url`.
  - Remover caixa descritiva de modo fixo de varredura.
  - Remover `<div id="dast-auth-hint">` e o atributo `aria-describedby="dast-auth-hint"` do checkbox `#zap-authorized`.
  - Atualizar cache-busting para `?v=023`.
- [x] **T004**: Atualizar `APP_UI_VERSION = "023"` em `app/main.py`.

---

## Fase 3 — Verificação e Docker
- [x] **T005**: Executar `pytest tests/test_feature_023_cleanup_dast_ui.py` (estágio TDD Green - 6/6 passaram).
- [x] **T006**: Executar suíte completa de testes do projeto para garantir zero regressão (19/19 passaram nos módulos UI).
- [x] **T007**: Reconstruir e subir os containers Docker (`docker compose up --build -d web`).
- [x] **T008**: Verificar HTTP 200 e resposta limpa em `http://localhost:8000` (Versão 023 ativa).

---

## Fase 4 — Revisão e Versionamento Git
- [x] **T009**: Auditoria de segurança e acessibilidade (`constitution-guardian` - Aprovado com 0 violações).
- [x] **T010**: Commit semântico `feat(spec-023): simplificacao visual dos textos informativos do card DAST`.
- [x] **T011**: Tag `v023` e `git push origin main v023`.


