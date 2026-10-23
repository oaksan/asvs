# Especificação de Funcionalidade (SDD): Gestão Completa de Usuários e Troca de Senha (Aba 5)

**Feature Branch**: `021-complete-user-management`  
**Created**: 2026-10-22  
**Status**: Ready for Implementation (Aprovado por Threat Modeler, Solution Architect e Constitution Guardian)  
**Input**: *"crie um sdd para na 5. Gestão de Usuários (Admin) ,eu poder fazer uma gestao de usuario completo, podendo por exemplo alterar minha senha ou criar outros usuários"*

---

## 1. Contexto e Diagnóstico

Na Feature 007 foi introduzida a autenticação local com RBAC, listagem de usuários e um formulário para cadastrar novos analistas. No entanto, a experiência de gestão de usuários na **Aba 5: Gestão de Usuários (Admin)** ainda possui lacunas que limitam a autonomia do administrador e dos usuários:

### Lacunas Identificadas:
1. **Alteração Voluntária da Própria Senha**:
   - Atualmente, a troca de senha só é acionada compulsoriamente via modal durante o primeiro login (`must_change_password=True`), ou de forma pouco acessível.
   - Não existe um formulário explícito na Aba 5 para o usuário alterar voluntariamente sua própria senha a qualquer momento.
2. **Operações Administrativas Incompletas**:
   - O administrador consegue criar e ativar/desativar usuários, mas **não consegue redefinir a senha esquecida de outro usuário**, nem **alterar o papel (role)** de um usuário (promover a Admin ou rebaixar a Usuário Comum), nem **excluir contas obsoletas**.
   - Na listagem de usuários, falta identificação visual de quem é a conta atualmente logada (`(Você)`), e faltavam salvaguardas explícitas na interface para prevenir auto-ações destrutivas.

---

## 2. Objetivos da Feature 021

1. **Card "Minha Conta / Alterar Minha Senha"**:
   - Adicionar uma seção direta e acessível na Aba 5 para alteração da senha do próprio usuário logado (informando senha atual, nova senha e confirmação, com feedback visual imediato e seguro).
2. **Gestão Completa de Outros Usuários (Admin)**:
   - **Criação de Usuários**: Manter e aprimorar o formulário de cadastro com validação em tempo real.
   - **Redefinição de Senha de Terceiros**: Permitir que o Admin defina uma nova senha temporária para qualquer outro usuário (marcando `must_change_password=True` e revogando sessões ativas).
   - **Edição de Papel (Role)**: Permitir alterar o papel de um usuário entre `user` e `admin` (com proteção contra auto-rebaixamento e prevenção de lockout do último admin ativo).
   - **Exclusão de Usuários**: Permitir remover contas com preservação de histórico de auditoria (`Run` e `AuditLog`), limpeza em cascata de credenciais de IA (`UserAIConfig`) e proibição terminante de auto-exclusão.
   - **Identificador "(Você)"**: Destacar a conta do usuário conectado na tabela e desabilitar preventivamente ações destrutivas contra a própria conta na UI.
3. **Segurança e Guardrails Constitucionais (Princípios I a VI)**:
   - Zero-Leakage: Nenhuma senha é transmitida em plain-text nos retornos JSON; senhas salvas com hash seguro (`hash_password` em `app/core/crypto.py`).
   - Sessões ativas invalidadas compulsoriamente em qualquer redefinição, alteração de papel ou exclusão (`terminate_user_sessions`).
   - Proteções estritas contra exclusão, rebaixamento ou desativação acidental da própria conta ou do último administrador ativo.
   - Auditoria completa em `AuditLog` para todas as ações administrativas.

---

## 3. User Scenarios & Acceptance Criteria (Given / When / Then)

### User Story 1 — Alteração Voluntária da Própria Senha (P1)
Como usuário autenticado acessando a aba de gestão,  
quero um formulário dedicado para alterar minha senha a qualquer momento,  
para manter minha conta segura sem depender de fluxos forçados de primeiro acesso.

#### Acceptance Scenarios:
1. **Given** um usuário logado na aba "5. Gestão de Usuários",  
   **When** preencher o card "Alterar Minha Senha" com a senha atual correta e a nova senha (mín. 8 caracteres) e submeter o formulário,  
   **Then** a senha é atualizada no banco de dados, `must_change_password` torna-se `False`, o backend responde `HTTP 200 OK` e o feedback visual exibe confirmação em verde.
2. **Given** o formulário de alteração de senha,  
   **When** a senha atual informada for incorreta ou a nova senha possuir menos de 8 caracteres,  
   **Then** o backend rejeita com `HTTP 400 Bad Request` e a UI exibe o erro claro sem alterar as credenciais.

### User Story 2 — Redefinição Administrativa de Senha de Terceiros (P1)
Como administrador do sistema,  
quero poder redefinir a senha temporária de outro analista que esqueceu sua credencial,  
para restabelecer o acesso do profissional sem necessidade de intervenção direta no banco de dados.

#### Acceptance Scenarios:
1. **Given** o administrador logado (`id=1`) e um analista cadastrado (`id=2`, `username="maria"`),  
   **When** o admin clicar em "Redefinir Senha", informar uma nova senha temporária (mín. 8 caracteres) e confirmar,  
   **Then** o endpoint `POST /api/users/2/reset-password` atualiza a senha de `maria`, define compulsoriamente `must_change_password=True`, revoga as sessões ativas de `maria` via `user_session_store.terminate_user_sessions(2)`, registra a ação em `AuditLog` e retorna `HTTP 200 OK`.
2. **Given** o usuário que teve a senha redefinida pelo admin,  
   **When** realizar o próximo login com a nova senha temporária,  
   **Then** o sistema bloqueia o acesso às rotas protegidas e exige obrigatoriamente a troca de senha antes de liberar o uso da aplicação.
3. **Given** o administrador logado (`id=1`),  
   **When** ele tentar acionar a redefinição de senha para a própria conta via `POST /api/users/1/reset-password`,  
   **Then** a requisição é rejeitada com `HTTP 400 Bad Request` orientando o uso do formulário de troca da própria senha com validação de senha atual.

### User Story 3 — Alteração de Papel e Prevenção de Auto-Rebaixamento / Lockout (P2)
Como administrador,  
quero poder promover ou rebaixar outros analistas entre os papéis `user` e `admin`,  
com salvaguardas que impeçam que eu rebaixe a mim mesmo ou deixe o sistema sem administradores.

#### Acceptance Scenarios:
1. **Given** um usuário comum (`user`),  
   **When** o admin alterar seu papel para `admin` via `PATCH /api/users/{id}/role` com `{"role": "admin"}`,  
   **Then** o papel é atualizado no banco, as sessões ativas do usuário são invalidadas forçando re-login para emissão de novos tokens com as novas permissões, a ação é auditada e o backend retorna `HTTP 200 OK`.
2. **Given** o próprio administrador logado,  
   **When** uma requisição de alteração de papel é enviada para seu próprio `id`,  
   **Then** a requisição é rejeitada com `HTTP 400 Bad Request` ("Não é permitido alterar o papel da sua própria conta").
3. **Given** apenas um administrador ativo no sistema,  
   **When** uma tentativa de rebaixar este administrador para `user` for submetida,  
   **Then** o backend rejeita com `HTTP 400 Bad Request` ("Não é permitido revogar privilégios do último administrador ativo").

### User Story 4 — Exclusão Segura com Preservação de Histórico e Anti-Lockout (P2)
Como administrador,  
quero poder excluir usuários inativos ou obsoletos,  
garantindo que histórico de avaliações seja preservado, credenciais de IA sejam limpas e auto-exclusão seja bloqueada.

#### Acceptance Scenarios:
1. **Given** um usuário cadastrado (`id=3`) com configurações de IA em `UserAIConfig`,  
   **When** o admin clicar em "Excluir" e confirmar no diálogo,  
   **Then** a requisição `DELETE /api/users/3` remove o registro `UserAIConfig`, reatribui os registros históricos de `Run` ao administrador logado, desassocia `AuditLog`, remove o `User`, expurga sessões ativas via `user_session_store.terminate_user_sessions(3)`, audita a remoção e retorna `HTTP 200 OK`.
2. **Given** o administrador logado tentando submeter `DELETE /api/users/{self_id}`,  
   **When** a requisição atinge o backend,  
   **Then** a operação é terminantemente bloqueada com `HTTP 400 Bad Request` ("Auto-exclusão da própria conta é proibida").
3. **Given** o último administrador ativo,  
   **When** qualquer requisição `DELETE` for direcionada ao seu ID,  
   **Then** o backend bloqueia com `HTTP 400 Bad Request` ("Não é permitido excluir o último administrador ativo").

### User Story 5 — Identificação Visual "(Você)" e Acessibilidade Ergonômica (P1)
Como usuário interagindo com a tabela na Aba 5,  
quero identificar claramente minha própria linha e ver ações perigosas desabilitadas,  
evitando erros operacionais e confusão visual.

#### Acceptance Scenarios:
1. **Given** o usuário logado visualizando a tabela de usuários,  
   **When** a lista é renderizada,  
   **Then** a linha do usuário atual exibe um badge visual `(Você)` ao lado do nome de usuário.
2. **Given** a linha correspondente ao usuário logado,  
   **When** inspecionados os botões de ação,  
   **Then** os botões de "Desativar", "Alterar Papel" e "Excluir" estão visualmente desabilitados (`disabled`, `aria-disabled="true"` e atributo `title="Ação desabilitada para sua própria conta"`).
3. **Given** a interface da Aba 5,  
   **When** montada no DOM,  
   **Then** não há nenhum uso de `innerHTML` (uso estrito de `document.createElement`, `el()` e `textContent`) e o layout adere 100% aos tokens do Fluent 2 e suporte a contraste claro/escuro.

---

## 4. Requisitos de Contratos e Endpoints

### 4.1 Novos Modelos Pydantic (`app/models.py`)
- **`UserResetPasswordRequest`**:
  ```python
  class UserResetPasswordRequest(BaseModel):
      """Payload para POST /api/users/{user_id}/reset-password (Admin only)."""
      new_password: str = PydanticField(..., min_length=8, max_length=128)
  ```
- **`UserRoleUpdateRequest`**:
  ```python
  class UserRoleUpdateRequest(BaseModel):
      """Payload para PATCH /api/users/{user_id}/role (Admin only)."""
      role: Literal["admin", "user"]
  ```

### 4.2 Endpoints Backend (`app/main.py`)
- **`POST /api/auth/change-password`**: Existente, consumido pelo novo card da Aba 5 (qualquer usuário autenticado).
- **`POST /api/users`**: Existente, cadastro de novos analistas (Admin only).
- **`GET /api/users`**: Existente, listagem sem credenciais (Admin only).
- **`PATCH /api/users/{user_id}/status`**: Existente, com trava de último admin (Admin only).
- **`POST /api/users/{user_id}/reset-password`** [NOVO]: Redefinição administrativa de senha temporária (Admin only).
- **`PATCH /api/users/{user_id}/role`** [NOVO]: Alteração de papel `admin` <-> `user` (Admin only).
- **`DELETE /api/users/{user_id}`** [NOVO]: Exclusão segura com limpeza de chaves de IA e preservação de histórico (Admin only).

---

## 5. Critérios de Sucesso e Verificação

- **SC-001**: O usuário consegue trocar sua própria senha diretamente na Aba 5 através de formulário dedicado e efetuar login com a nova credencial.
- **SC-002**: O administrador consegue criar novos usuários, redefinir senhas temporárias de terceiros (com exigência de troca no próximo login), alterar papéis e excluir contas com integridade relacional.
- **SC-003**: Todas as 4 travas de segurança (Anti-Self-Delete, Anti-Self-Demote, Anti-Self-Reset e Anti-Lockout do último admin) são rigorosamente validadas no backend com testes unitários.
- **SC-004**: Sessões ativas de usuários modificados/excluídos são invalidadas imediatamente na memória volátil (`UserSessionStore`).
- **SC-005**: 100% de aprovação na suíte de testes automatizados (`pytest`).
