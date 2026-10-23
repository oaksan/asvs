# Tarefas de Engenharia (SDD Tasks) — Feature 021: Gestão Completa de Usuários na Aba 5 (Admin)

**Branch**: `021-complete-user-management`  
**Status**: Concluído (100% de Aprovação em Testes, Auditoria ACI e Parecer Constitucional)  

---

## Fase 1 — Setup & Contratos Pydantic
- [x] **T001**: Adicionar schemas de validação em `app/models.py`:
  - `UserResetPasswordRequest(new_password: str)` (mínimo 8, máximo 128 caracteres).
  - `UserRoleUpdateRequest(role: Literal["admin", "user"])`.
  - Exportar schemas em `app/models.py`.

---

## Fase 2 — TDD (Testes Automatizados Pré-Implementação)
- [x] **T002**: Criar arquivo `tests/test_feature_021_user_management.py` com cenários:
  - Teste de troca de própria senha via `POST /api/auth/change-password` (sucesso e falha por senha atual incorreta).
  - Teste de redefinição de senha pelo admin via `POST /api/users/{id}/reset-password`:
    - Deve atualizar o hash.
    - Deve setar `must_change_password = True`.
    - Deve invalidar sessões ativas do usuário alvo.
  - Teste de auto-reset bloqueado: Admin não pode chamar `reset-password` para seu próprio `id`.
  - Teste de alteração de papel via `PATCH /api/users/{id}/role`:
    - Promoção de `user` para `admin`.
    - Rebaixamento de `admin` para `user`.
    - Bloqueio de auto-rebaixamento (`admin.id == target.id`).
    - Bloqueio de rebaixamento do último admin ativo do sistema.
  - Teste de exclusão de usuário via `DELETE /api/users/{id}`:
    - Exclusão bem-sucedida de analista.
    - Remoção em cascata de `UserAIConfig`.
    - Reatribuição de `Run` para preservação do histórico de auditoria.
    - Bloqueio de auto-exclusão (`admin.id == target.id`).
    - Bloqueio de exclusão do último admin ativo do sistema.
  - Teste de RBAC: usuário comum recebe HTTP 403 em todos os endpoints `/api/users/*`.

---

## Fase 3 — Implementação Backend (`app/main.py`)
- [x] **T003**: Implementar endpoint `POST /api/users/{user_id}/reset-password`:
  - Dependência `require_admin`.
  - Checagem `target_user.id != admin.id`.
  - Hash de senha, marcação de `must_change_password=True`.
  - Chamada a `user_session_store.terminate_user_sessions(target_user.id)`.
- [x] **T004**: Implementar endpoint `PATCH /api/users/{user_id}/role`:
  - Dependência `require_admin`.
  - Checagem `target_user.id != admin.id`.
  - Checagem de contagem de admins ativos se rebaixando de admin para user.
  - Chamada a `user_session_store.terminate_user_sessions(target_user.id)`.
- [x] **T005**: Implementar endpoint `DELETE /api/users/{user_id}`:
  - Dependência `require_admin`.
  - Checagem `target_user.id != admin.id`.
  - Checagem de contagem de admins ativos se for admin.
  - Remoção em cascata de `UserAIConfig`.
  - Reatribuição de `Run` ao `admin.id` e `AuditLog.user_id = None`.
  - Exclusão do registro `User`.
  - Chamada a `user_session_store.terminate_user_sessions(target_user.id)`.
- [x] **T006**: Atualizar `APP_UI_VERSION = "021"` em `app/main.py`.

---

## Fase 4 — Implementação Frontend (`templates/index.html` e `static/app.js`)
- [x] **T007**: Adicionar no topo do `#panel-users` em `templates/index.html`:
  - Card "Minha Conta / Alterar Minha Senha" (`#self-change-password-form`) com campos de senha atual, nova senha, confirmação e banner de status acessível.
  - Diálogo modal nativo `<dialog id="reset-user-dialog">` para inserção de nova senha temporária pelo admin.
  - Atualizar referências de assets para `?v=021`.
- [x] **T008**: Implementar lógica em `static/app.js`:
  - Conectar submissão de `#self-change-password-form` ao `POST /api/auth/change-password` com validação de match e feedback visual.
  - Aprimorar `loadUsersList()`:
    - Renderização 100% segura sem `innerHTML` (`el()`, `textContent`).
    - Inclusão do badge `(Você)` no usuário logado.
    - Desabilitação de botões destrutivos na própria linha do usuário ativo com tooltip explicativo.
    - Conectar botão "Desativar/Ativar" ao `PATCH /api/users/{id}/status`.
    - Conectar alteração de papel ao `PATCH /api/users/{id}/role`.
    - Conectar botão "Redefinir Senha" ao modal `#reset-user-dialog` e chamada a `POST /api/users/{id}/reset-password`.
    - Conectar botão "Excluir" com confirmação acessível e chamada a `DELETE /api/users/{id}`.

---

## Fase 5 — Verificação, Testes & Gate Final
- [x] **T009**: Executar suíte de testes pytest direcionada:
  - `.venv/bin/pytest -vv tests/test_feature_021_user_management.py` (15/15 aprovados)
  - `.venv/bin/pytest -q` (163/163 aprovados)
- [x] **T010**: Rebuild dos containers Docker:
  - `docker compose up --build -d web`
  - Validar funcionamento dos containers e status HTTP 200.

---

## Fase 6 — Versionamento & Sincronização Git
- [x] **T011**: Commit semântico dos artefatos:
  - `git add specs/021-complete-user-management/ app/ templates/ static/ tests/`
  - `git commit -m "feat(spec-021): gestao completa de usuarios na aba 5 e troca de senha"`
  - `git tag -a v021 -m "Release v021: Gestão Completa de Usuários e Troca de Senha"`
  - `git push origin main v021`
