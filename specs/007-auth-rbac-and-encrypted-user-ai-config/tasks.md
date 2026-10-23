# Tasks: 007-auth-rbac-and-encrypted-user-ai-config

**Spec Reference**: [`specs/007-auth-rbac-and-encrypted-user-ai-config/spec.md`](spec.md)  
**Plan Reference**: [`specs/007-auth-rbac-and-encrypted-user-ai-config/plan.md`](plan.md)  
**Status**: Ready for Implementation (TDD Ready / RED Confirmed)

---

## Phase 1: Setup & Automated TDD Tests (Blocking Prerequisites)

**Purpose**: Escrever testes automatizados que cobrem criptografia em repouso, autenticação, RBAC, proteção de IDOR e ciclo de vida de credenciais antes da implementação.

- [x] T001 Atualizar `tests/conftest.py` com fixtures de cliente autenticado (`auth_admin_client`, `auth_user_client`) e inicialização limpa de banco SQLite com conta padrão `admin`.
- [x] T002 Criar suite de testes em `tests/test_auth_rbac.py` cobrindo cenários Given/When/Then da especificação (login com admin/admin, bloqueio de 401 não autenticado, troca mandatória de senha inicial com 403 em outras rotas, gestão de usuários por admin, bloqueio 403 para usuário comum, prevenção de IDOR em runs/export/SSE e actor imutável na triagem).
- [x] T003 Criar suite de testes em `tests/test_encrypted_user_ai_secrets.py` cobrindo: primitivas de cifra/decifra AES-256-GCM com HKDF e PBKDF2-HMAC-SHA256, persistência criptografada em repouso no SQLite (sem texto claro), decifragem automática no login populando a sessão e expurgo seguro em memória no logout.
- [x] T004 Executar `.venv/bin/pytest tests/test_auth_rbac.py tests/test_encrypted_user_ai_secrets.py` para certificar que os testes falham antes da implementação (TDD RED).

---

## Phase 2: Core Cryptography & Data Model (Priority: P1 🎯 MVP)

**Goal**: Implementar primitivas de criptografia simétrica AES-256-GCM, hash seguro de senhas, novas entidades SQLModel e migração idempotente do SQLite.

- [x] T005 Criar `app/core/crypto.py` com funções `encrypt_secret`, `decrypt_secret`, `hash_password`, `verify_password` utilizando `cryptography.hazmat.primitives.ciphers.aead.AESGCM` e `hashlib.pbkdf2_hmac`.
- [x] T006 Atualizar `app/models.py` com `UserRole`, `User`, `UserAIConfig`, schemas de autenticação Pydantic (`LoginRequest`, `LoginResponse`, `UserCreateRequest`, `UserResponse`, `UserStatusUpdateRequest`, `ChangePasswordRequest`, `SessionUser`), enriquecendo `Run` com `user_id` e `owner_username`, e `AuditLog` com `user_id`.
- [x] T007 Atualizar `app/database.py` com migração idempotente do SQLite (`ALTER TABLE run ADD COLUMN user_id ...`) e seed automático da conta inicial `admin / admin` com `must_change_password=True`.

---

## Phase 3: Auth Layer, RBAC & Endpoints (Priority: P1 🎯 MVP)

**Goal**: Implementar middleware/dependências de sessão segura, endpoints de autenticação e gestão de usuários, e proteção RBAC contra IDOR nas rotas existentes.

- [x] T008 Criar `app/core/auth.py` com `UserSessionStore` em memória para credenciais ativas, dependências FastAPI `get_current_user`, `require_admin`, `verify_run_access`, emissão de cookie `HttpOnly; SameSite=Lax` e expurgo de sessão no logout.
- [x] T009 Implementar endpoints de autenticação em `app/main.py`: `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, `POST /api/auth/change-password`.
- [x] T010 Implementar endpoints de gestão de usuários em `app/main.py`: `GET /api/users`, `POST /api/users`, `PATCH /api/users/{id}/status` com validação contra lockout do último admin.
- [x] T011 Aplicar controle de acesso RBAC nas rotas existentes do ASVS em `app/main.py`:
  - `GET /api/runs`: admins recebem todas as avaliações; usuários comuns recebem apenas `user_id == current_user.id`.
  - `POST /api/runs`: vincula automaticamente `user_id` e `owner_username`.
  - `GET /api/runs/{id}`, `/findings`, `/evidence`, `/export`, SSE `/events`, `cancel`, `rerun`: protegidos com `verify_run_access` (403 para não-donos).
  - `PATCH /api/findings/{id}/triage`: força `actor = current_user.username` no `AuditLog`.
- [x] T012 Atualizar `POST /api/ai/config`, `GET /api/ai/status` e `POST /api/ai/chat-test` para associar as configurações ao usuário autenticado, persistindo no `UserAIConfig` criptografado em repouso e abastecendo o `UserSessionStore`.

---

## Phase 4: Frontend Fluent 2 & Acessibilidade (Priority: P2)

**Goal**: Criar interface de autenticação, modal de troca mandatória de senha e Guia 6 de Gestão de Usuários no frontend Fluent 2 com conformidade WCAG 2.2 AA e Zero innerHTML.

- [x] T013 Implementar diálogo de login e modal de troca obrigatória de senha em `templates/index.html` e `static/app.js` usando componentes Fluent 2 e manipulação estrita via `textContent`.
- [x] T014 Atualizar cabeçalho da aplicação para exibir perfil do usuário autenticado `[👤 <username> (<role>) | Sair]` e suporte contínuo a temas claro e escuro.
- [x] T015 Implementar a Guia 6 (Gestão de Usuários) em `templates/index.html` e `static/app.js` com formulário de cadastro e tabela de contas acessível com alternância de status ativo/inativo.
- [x] T016 Aplicar controle de visibilidade no frontend: ocultar a Guia 6 para usuários comuns (`role == 'user'`) e filtrar o histórico e dashboard para exibir apenas suas próprias avaliações.

---

## Phase 5: Homologação, Regressão e Revisão de Segurança (Priority: P1)

**Purpose**: Garantir 100% de aprovação nos testes automatizados, zero regressões na suíte ASVS legada e auditar os guardrails de segurança.

- [x] T017 Executar toda a suíte de testes do projeto: `.venv/bin/pytest -q` (garantindo que os 53 testes existentes + novos testes de auth/crypto passem com 100% GREEN).
- [x] T018 Executar auditoria de segurança paralela com `llm-security-reviewer` e `aci-security-reviewer`.
- [x] T019 Obter parecer formal de liberação final do `constitution-guardian` (Gate 3).
