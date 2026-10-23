# Implementation Plan: Autenticação Local, RBAC e Criptografia em Repouso de IA

**Branch**: `007-auth-rbac-and-encrypted-user-ai-config` | **Date**: 2026-10-15 | **Spec**: [`specs/007-auth-rbac-and-encrypted-user-ai-config/spec.md`](spec.md)  
**Input**: Especificação formal da Feature 007 derivada de solicitação de usuário e modelagem STRIDE.

---

## Summary

Esta feature introduz autenticação local de usuários com conta padrão `admin / admin` e troca forçada de senha no primeiro acesso; controle de acesso baseado em papéis (RBAC) com segregação de avaliações (administradores possuem visão e auditoria global; usuários comuns operam estritamente sobre suas próprias execuções); e persistência profissional em repouso de credenciais de IA (AES-256-GCM autenticado no SQLite), eliminando a necessidade de re-digitação de chaves a cada sessão e garantindo estrita conformidade com o Princípio IV (Zero-Leakage).

---

## Technical Context

**Language/Version**: Python 3.12 / 3.13  
**Primary Dependencies**: FastAPI 0.143+, SQLModel 0.0.48+, Pydantic v2, `cryptography` 50.0+ (AESGCM, HKDF), Jinja2, Microsoft Fluent 2 Web Components.  
**Storage**: SQLite (`asvs.db`) com tabelas relacionais `user`, `user_ai_config`, `run` (enriquecida com `user_id`), `finding`, `evidence`, `audit_log`.  
**Testing**: `pytest` 9.1+, `pytest-asyncio`, `httpx` (FastAPI TestClient).  
**Target Platform**: Linux / Container Docker / Web Browser com WCAG 2.2 AA.  
**Project Type**: Web Service Assíncrono com Interface HTML5 Server-Rendered + Componentes Web.  
**Performance Goals**: Tempo de resposta de autenticação < 100ms; decifragem de credenciais em memória pós-login < 50ms; zero impacto no streaming SSE de avaliações.  
**Constraints**:
- Princípio IV inegociável: zero vazamento de chaves de API em texto claro no disco, logs, endpoints REST ou DOM.
- Acessibilidade WCAG 2.2 AA e política estrita de **Zero innerHTML** no frontend.
- Criptografia simétrica com autenticação de integridade (AES-256-GCM com tag de 128 bits e nonce de 12 bytes).
- Imunidade total a IDOR em rotas de execuções, achados, evidências e relatórios.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Requisito Constitucional | Status no Plano |
| :--- | :--- | :---: |
| **I. Escopo Normativo** | Restrito a V1 L1 (8 requisitos) | **CONFORME** (Sem alteração no escopo) |
| **II. Vereditos** | Baseado em evidência positiva (PASS/FAIL/INCONCLUSIVE/MANUAL_REQUIRED) | **CONFORME** (Inalterado) |
| **III. Auditabilidade** | Triagem reproduzível e auditável com justificativa | **CONFORME** (AuditLog agora vincula `current_user.username` como actor imutável) |
| **IV. Guardrails** | Confinamento de workspace, autorização DAST incondicional e Zero-Leakage de IA | **CONFORME** (Zero-Leakage reforçado com AES-256-GCM em repouso e cookies seguros HttpOnly) |
| **V. Fluent 2 & A11y** | WCAG 2.2 AA, temas claro/escuro e **Zero innerHTML** | **CONFORME** (Modal de login e painel de usuários utilizam exclusivamente `textContent` e tokens Fluent) |
| **VI. SDD & TDD** | Spec-Driven Development com 100% dos testes passando | **CONFORME** (Bateria TDD planejada antes da implementação) |

---

## Project Structure

### Documentation (this feature)

```text
specs/007-auth-rbac-and-encrypted-user-ai-config/
├── spec.md              # Especificação formal com US1 a US4 e edge cases
├── plan.md              # Este plano de implementação
├── research.md          # Decisões de criptografia, hash e sessão (Fase 0)
├── data-model.md        # Entidades SQLModel User, UserAIConfig e matriz RBAC (Fase 1)
├── quickstart.md        # Guia rápido de login, usuários e credenciais (Fase 1)
├── contracts/           # Contratos OpenAPI 3.1
│   └── auth-api.yaml
└── checklists/
    └── requirements.md  # Checklist de qualidade de requisitos (Gate 1 validado)
```

### Source Code Impacted

```text
app/
├── core/
│   ├── crypto.py         # [NOVO] Criptografia simétrica AES-256-GCM, HKDF, hash PBKDF2
│   ├── auth.py           # [NOVO] Gerenciamento de sessões seguras, dependências get_current_user / require_admin
│   └── ai_secrets.py     # [ATUALIZADO] Suporte a isolamento de credenciais por usuário / sessão
├── models.py             # [ATUALIZADO] Entidades User, UserRole, UserAIConfig, enriquecimento de Run e schemas auth
├── database.py           # [ATUALIZADO] Seed da conta admin/admin e migração idempotente de Run (user_id)
├── main.py               # [ATUALIZADO] Rotas /api/auth/*, /api/users/* e filtros RBAC contextuais
templates/
└── index.html            # [ATUALIZADO] Tela/Modal de login, header com usuário ativo e Guia 6 de Gestão de Usuários
static/
├── app.js                # [ATUALIZADO] Gerenciamento de estado de autenticação, login, logout e visibilidade RBAC
└── theme.css             # [ATUALIZADO] Estilos para o formulário de login e perfil de usuário
tests/
├── test_auth_rbac.py                 # [NOVO] Testes de login, criação de usuários, bloqueios 401/403 e IDOR
└── test_encrypted_user_ai_secrets.py # [NOVO] Testes de criptografia AES-256-GCM em repouso e decifragem no login
```

---

## Planned Execution Steps

### Step 1: Módulo Criptográfico (`app/core/crypto.py`)
- Implementar derivação de chave de 256 bits via HKDF-SHA256 a partir de `APP_SECRET_KEY`.
- Implementar `encrypt_secret(plaintext: str) -> tuple[bytes, bytes, bytes]` (retorna ciphertext+tag e nonce).
- Implementar `decrypt_secret(ciphertext_and_tag: bytes, nonce: bytes) -> str` com validação de tag de integridade.
- Implementar `hash_password(password: str) -> tuple[str, str]` e `verify_password(password: str, stored_hash: str, salt_hex: str) -> bool` com PBKDF2-HMAC-SHA256 em tempo constante.

### Step 2: Modelagem de Dados & Migração Idempotente (`app/models.py`, `app/database.py`)
- Declarar `UserRole`, `User`, `UserAIConfig`.
- Adicionar colunas `user_id: int` e `owner_username: str` na entidade `Run`.
- Criar schemas Pydantic de entrada/saída: `LoginRequest`, `LoginResponse`, `UserCreateRequest`, `UserResponse`, `ChangePasswordRequest`.
- Em `app/database.py`, criar rotina idempotente que adiciona as colunas em bancos legados (`PRAGMA table_info`) e cria o usuário `admin` caso a tabela esteja vazia (`must_change_password=True`).

### Step 3: Autenticação, Sessões e Desacoplamento de Segredos (`app/core/auth.py`, `app/core/ai_secrets.py`)
- Criar `UserSessionStore` em memória mapeando tokens de sessão seguros (`secrets.token_urlsafe(32)`).
- Implementar dependências FastAPI:
  - `get_current_user`: lê cookie `asvs_session`, valida sessão e retorna o usuário ativo (ou levanta 401).
  - `require_admin`: assegura que `current_user.role == "admin"` (ou levanta 403).
  - `verify_run_access`: valida se `run.user_id == current_user.id or current_user.role == "admin"`.
- No login bem-sucedido: buscar `UserAIConfig` do banco, decifrar a chave e injetá-la na sessão ativa volátil. No logout: expurgar os dados em memória.

### Step 4: Endpoints REST e Proteção RBAC (`app/main.py`)
- Endpoints de autenticação:
  - `POST /api/auth/login` (emite cookie `HttpOnly; SameSite=Lax; Path=/`).
  - `POST /api/auth/logout` (expira cookie e destrói sessão).
  - `GET /api/auth/me` (retorna perfil do usuário logado).
  - `POST /api/auth/change-password` (redefine senha e desmarca `must_change_password`).
- Endpoints de usuários (protegidos por `require_admin`):
  - `GET /api/users` (lista contas existentes sem hash).
  - `POST /api/users` (cria novas contas).
  - `PATCH /api/users/{id}/status` (ativa/desativa contas, protegendo contra auto-desativação do último admin).
- Filtros RBAC nas rotas existentes:
  - `GET /api/runs`: se admin, retorna todas; se user, filtra por `user_id == current_user.id`.
  - `POST /api/runs`: associa `user_id = current_user.id` e `owner_username = current_user.username`.
  - `GET /api/runs/{id}`, `/findings`, `/evidence`, `/export`, SSE `/events`, `cancel`, `rerun`: protegidos com `verify_run_access`.
  - `PATCH /api/findings/{id}/triage`: grava `actor = current_user.username` no `AuditLog`.

### Step 5: Interface Fluent 2 & Acessibilidade (`templates/index.html`, `static/app.js`)
- Criar diálogo/modal de login acessível quando o usuário não estiver autenticado.
- Modal obrigatório de troca de senha quando `must_change_password=True`.
- Atualizar o cabeçalho: exibir `[👤 <username> (<role>) | Sair]`.
- Se usuário for admin: exibir aba "6. Gestão de Usuários" com formulário de cadastro e tabela de contas.
- Se usuário for comum: ocultar aba 6 e exibir apenas suas próprias execuções no histórico e dashboard.
- Aderência total ao Princípio V: zero uso de `innerHTML`, construções seguras com `textContent`.

### Step 6: Testes Automatizados TDD & Verificação de Regressão
- Criar `tests/test_auth_rbac.py` cobrindo fluxos de login, RBAC e prevenção de IDOR.
- Criar `tests/test_encrypted_user_ai_secrets.py` validando que nenhuma chave pura é gravada no banco e que a decifragem pós-login funciona.
- Garantir que todos os 53 testes existentes continuem passando sem regressão através de fixtures autenticadas.
