# Feature Specification: Autenticação Local, RBAC e Persistência Criptografada de Credenciais de IA por Usuário

**Feature Code**: `007-auth-rbac-and-encrypted-user-ai-config`  
**Feature Branch**: `007-auth-rbac-and-encrypted-user-ai-config`  
**Created**: 2026-10-15  
**Status**: Ready for Review / Gate 1  
**Input**: "Implementar autenticação local com padrão admin/admin, gerenciamento de usuários locais, isolamento RBAC de avaliações (admin vê todas, usuário comum vê apenas as suas) e persistência segura criptografada em repouso (AES-256-GCM) das credenciais de IA por usuário."

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Autenticação Local e Troca Obrigatória de Senha Inicial (Priority: P1 🎯 MVP)

Como analista ou administrador de segurança,  
Quero acessar a ferramenta ASVS através de uma interface de login com credenciais locais,  
Para que todas as minhas ações, relatórios e configurações de segurança fiquem vinculadas à minha identidade autenticada de forma segura e protegida contra acessos não autorizados.

**Why this priority**: A autenticação é o alicerce fundamental para a introdução de múltiplos usuários, controle de acesso e proteção das credenciais em repouso.

**Independent Test**: Pode ser testado de forma independente acessando a página inicial: usuários não autenticados são direcionados para a tela de login; o login com `admin / admin` é aceito; no primeiro acesso, o sistema força a troca de senha antes de liberar o acesso às demais telas; e um cookie de sessão seguro (`HttpOnly; SameSite=Lax; Path=/`) é emitido.

**Acceptance Scenarios**:

1. **Given** que a aplicação foi inicializada pela primeira vez com banco vazio,  
   **When** o usuário acessa qualquer rota do sistema sem sessão ativa,  
   **Then** a interface apresenta a tela de login acessível e bloqueia o acesso a painéis e APIs protegidas com `HTTP 401 Unauthorized`.

2. **Given** a tela de login aberta,  
   **When** o usuário submete o formulário com `username="admin"` e `password="admin"`,  
   **Then** o backend valida as credenciais contra o hash criptográfico (Argon2id/PBKDF2), regenera o identificador de sessão, emite o cookie de sessão seguro e detecta que a flag `must_change_password` está ativa.

3. **Given** um usuário logado com `must_change_password=True`,  
   **When** ele tenta invocar qualquer rota da aplicação diferente de alterar senha e logout,  
   **Then** o sistema bloqueia a ação com `HTTP 403 Forbidden` e exibe o modal mandatório de redefinição de senha com requisito de complexidade (mínimo 8 caracteres).

4. **Given** a tela de troca de senha aberta,  
   **When** o usuário informa a senha atual e define uma nova senha válida,  
   **Then** o sistema atualiza o hash no banco, desmarca `must_change_password` e redireciona o usuário para o dashboard principal com sessão autenticada.

5. **Given** um usuário logado,  
   **When** ele clica no botão "Sair" do cabeçalho,  
   **Then** a sessão é imediatamente invalidada no servidor e no cliente (`Max-Age=0`), expurgando segredos voláteis da memória.

---

### User Story 2 - Controle de Acesso Baseado em Papéis (RBAC) e Prevenção de IDOR (Priority: P1)

Como usuário com perfil comum (`user`),  
Quero visualizar, executar e triar apenas as avaliações de segurança que eu mesmo disparei,  
Enquanto administradores (`admin`) possam auditar e comparar todas as avaliações corporativas,  
Garantindo o isolamento estrito de dados entre diferentes equipes e analistas.

**Why this priority**: Evita vazamento de código-fonte, achados de vulnerabilidade e relatórios confidenciais entre analistas diferentes, atendendo ao Princípio I e às diretrizes OWASP contra Insecure Direct Object References (IDOR).

**Independent Test**: Criar dois usuários (`analista_a` e `analista_b`). O `analista_a` executa uma avaliação; o `analista_b` faz login e confirma que a lista de execuções está vazia; qualquer tentativa de `analista_b` acessar `GET /api/runs/{run_id_de_a}` ou suas evidências/relatórios retorna estritamente `HTTP 403 Forbidden`. O `admin` faz login e visualiza ambas as execuções.

**Acceptance Scenarios**:

1. **Given** um usuário com perfil `user` autenticado,  
   **When** ele acessa a Aba 1 ou a Aba 4 (Histórico) ou consulta `GET /api/runs`,  
   **Then** a listagem exibe estritamente as execuções pertencentes ao seu `user_id`.

2. **Given** um usuário comum tentando acessar diretamente uma execução de outro usuário (ex.: `GET /api/runs/{id}`, `/findings`, `/evidence`, `/export`, SSE `/events`),  
   **When** o `run.user_id` da execução não coincide com o `current_user.id`,  
   **Then** o sistema rejeita a requisição com `HTTP 403 Forbidden` e registra a tentativa de acesso indevido no log.

3. **Given** um usuário com perfil `admin` autenticado,  
   **When** ele consulta `GET /api/runs` ou a tela de histórico,  
   **Then** todas as execuções do sistema são listadas, exibindo o identificador e nome do executor proprietário (`owner_username`).

4. **Given** uma triagem de falso positivo realizada em `PATCH /api/findings/{id}/triage`,  
   **When** o usuário submete a justificativa,  
   **Then** o registro em `AuditLog` grava compulsoriamente o `actor` derivado da sessão autenticada (`current_user.username`), prevenindo repúdio de decisões de conformidade.

---

### User Story 3 - Persistência Criptografada em Repouso de Credenciais de IA por Usuário (Priority: P2)

Como usuário do sistema,  
Quero que minhas configurações e chaves de API do Azure OpenAI ou Google Gemini fiquem salvas para a minha conta de forma profissional e criptografada em repouso,  
Para que eu não precise reinserir a chave a cada novo login e sem que minha chave seja exposta em texto claro no banco de dados.

**Why this priority**: Elimina atrito operacional diário mantendo conformidade inegociável com a política Zero-Leakage (Princípio IV da Constituição).

**Independent Test**: Usuário `analista_a` configura a chave de API na Guia 5 e salva. Inspecionar o banco SQLite (`asvs.db`): o campo `encrypted_api_key` contém bytes criptografados e a chave pura NÃO existe em nenhuma tabela ou coluna. O usuário faz logout e novo login: a aplicação decifra a chave em memória de sessão e o chat playground já responde imediatamente sem solicitar a chave novamente.

**Acceptance Scenarios**:

1. **Given** um usuário autenticado na Guia 5 (Configuração de IA),  
   **When** ele insere suas credenciais (Azure OpenAI ou Gemini) e clica em "Salvar Credenciais",  
   **Then** o backend cifra a chave usando **AES-256-GCM** com chave mestra derivada e nonce exclusivo, persistindo o criptograma associado ao `user_id`.

2. **Given** uma chave de IA salva para um usuário,  
   **When** o banco SQLite é inspecionado diretamente via query SQL ou dump de disco,  
   **Then** a chave em texto plano não aparece em nenhum byte do arquivo; apenas o payload cifrado e a máscara `••••••••` estão armazenados.

3. **Given** um usuário que já salvou sua chave de IA realizando login,  
   **When** o login é concluído com sucesso,  
   **Then** o sistema decifra a chave em memória volátil de sessão para aquele usuário e atualiza o status para `Motor Conectado: <modelo>`, permitindo executar avaliações ASVS e interagir no chat sem reinserir a chave.

4. **Given** a consulta `GET /api/ai/status`,  
   **When** qualquer requisição consulta o status de IA,  
   **Then** o payload de resposta expõe apenas metadados do modelo e a chave mascarada como `••••••••`, nunca revelando a chave decifrada.

5. **Given** o logout do usuário ou expiração da sessão,  
   **When** o encerramento da sessão ocorre,  
   **Then** as credenciais decifradas são imediatamente descartadas da memória do servidor.

---

### User Story 4 - Gerenciamento de Usuários Locais para Administradores (Priority: P3)

Como administrador do sistema,  
Quero uma aba dedicada para criar novos usuários locais, definir seus papéis (`admin` ou `user`) e ativar/desativar contas,  
Para que eu possa gerenciar a equipe de segurança sem intervenção manual no banco de dados.

**Why this priority**: Facilita a governança de acessos no ambiente corporativo e viabiliza a segregação de funções.

**Independent Test**: Usuário `admin` acessa a Guia 6 ("Gestão de Usuários"), preenche o formulário para criar um novo usuário `analista_teste` com papel `user`, e confirma que o novo usuário foi criado. O novo usuário consegue logar. O usuário comum não vê a Guia 6 e qualquer chamada direta a `POST /api/users` por ele retorna `HTTP 403`.

**Acceptance Scenarios**:

1. **Given** um usuário com papel `admin` autenticado,  
   **When** ele acessa a interface,  
   **Then** uma guia exclusiva "6. Gestão de Usuários" é exibida na navegação Fluent 2.

2. **Given** o formulário de criação de usuários na Guia 6,  
   **When** o administrador informa `username`, `password` inicial e seleciona o papel (`user` ou `admin`),  
   **Then** o usuário é criado com hash seguro, flag `must_change_password=True` e listado na tabela de usuários.

3. **Given** a lista de usuários existentes,  
   **When** o administrador visualiza os registros,  
   **Then** são exibidos `id`, `username`, `role`, status (`Ativo`/`Inativo`) e data de criação, sem expor nenhum hash de senha.

4. **Given** um usuário comum (`user`),  
   **When** ele tenta invocar `GET /api/users` ou `POST /api/users`,  
   **Then** a rota retorna `HTTP 403 Forbidden` com a mensagem `"Acesso restrito a administradores"`.

5. **Given** o último administrador ativo do sistema,  
   **When** há uma tentativa de desativá-lo ou alterar seu papel para `user`,  
   **Then** a operação é bloqueada para prevenir *lockout* administrativo do sistema.

---

### Edge Cases

- **EC-001**: O que acontece se a variável de ambiente `APP_SECRET_KEY` não for definida?  
  *Tratamento*: Em modo de desenvolvimento, a aplicação gera e confina um arquivo local `.secret_key` com permissão restrita `0600` para estabilidade entre reinicializações. Em modo de produção, a aplicação aborta a inicialização com mensagem de erro clara orientando a configuração de `APP_SECRET_KEY`.
- **EC-002**: O que acontece se o arquivo de banco SQLite for copiado por um terceiro sem a `APP_SECRET_KEY`?  
  *Tratamento*: As senhas de usuários continuam protegidas por PBKDF2/Argon2id com salt individual e as credenciais de IA permanecem indecifráveis, pois dependem da chave simétrica mestra ausente no banco.
- **EC-003**: O que acontece se um usuário for desativado enquanto possui uma sessão ativa?  
  *Tratamento*: A cada requisição, a dependência `get_current_user` valida se `user.is_active is True`. Se o usuário foi desativado, a requisição é imediatamente rejeitada com `HTTP 401 Unauthorized` e a sessão é invalidada.
- **EC-004**: O que acontece se um usuário comum tentar comparar execuções de terceiros no endpoint `GET /api/runs/compare`?  
  *Tratamento*: O endpoint valida se ambas as execuções (`base_run_id` e `target_run_id`) pertencem ao usuário requisitante (ou se o requisitante é admin), retornando `HTTP 403 Forbidden` caso haja violação.
- **EC-005**: Como evitar que a aplicação fique bloqueada sem nenhum admin caso haja corrupção?  
  *Tratamento*: Na rotina de inicialização `init_db()`, se não existir nenhum usuário na tabela `User`, a conta `admin` é recriada automaticamente com senha `admin` e `must_change_password=True`.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE fornecer tela de login acessível (Fluent 2, WCAG 2.2 AA) solicitando `username` e `password`.
- **FR-002**: O sistema DEVE inicializar automaticamente a conta `admin` com senha inicial `admin`, papel `admin` e flag `must_change_password=True` caso a tabela de usuários esteja vazia.
- **FR-003**: As senhas de usuários DEVEM ser armazenadas exclusivamente em formato de hash criptográfico resistente (PBKDF2-HMAC-SHA256 com mínimo 600.000 iterações ou Argon2id) utilizando salt aleatório individual de 32 bytes gerado por `os.urandom`.
- **FR-004**: Sessões ativas DEVEM ser gerenciadas via cookie HTTP seguro com atributos obrigatórios `HttpOnly=True`, `SameSite="Lax"`, `Path=/` e `Secure=True` (em ambientes HTTPS/produção).
- **FR-005**: Ao autenticar com sucesso, o sistema DEVE regenerar o identificador de sessão para imunidade contra ataques de fixação de sessão.
- **FR-006**: O sistema DEVE bloquear qualquer operação de usuário cuja flag `must_change_password` seja verdadeira (exceto alteração de senha e logout) com `HTTP 403 Forbidden`.
- **FR-007**: A entidade `Run` DEVE possuir a coluna `user_id` associada ao usuário executor autenticado.
- **FR-008**: Em consultas de listagem (`GET /api/runs`), usuários comuns DEVEM receber unicamente as execuções cujo `user_id` corresponda ao seu identificador; administradores DEVEM receber todas as execuções.
- **FR-009**: Em endpoints de detalhes, relatórios, eventos SSE, cancelamento, reexecução e evidências de uma avaliação (`/api/runs/{id}/*`), o sistema DEVE verificar se o usuário requisitante é o proprietário da avaliação ou um administrador, retornando `HTTP 403 Forbidden` em caso negativo.
- **FR-010**: No endpoint de triagem (`PATCH /api/findings/{id}/triage`), o sistema DEVE validar a posse da avaliação associada e registrar no `AuditLog` o campo `actor` extraído compulsoriamente do usuário autenticado na sessão.
- **FR-011**: O sistema DEVE disponibilizar endpoints administrativos (`/api/users`) protegidos pela política `require_admin`, permitindo listar, criar e desativar usuários.
- **FR-012**: O sistema DEVE impedir que o último administrador ativo seja desativado ou rebaixado de papel.
- **FR-013**: As credenciais de IA (API key, provedor, deployment, recurso) configuradas por um usuário DEVEM ser persistidas em repouso no banco SQLite cifradas com **AES-256-GCM**, acompanhadas de nonce de 12 bytes gerado aleatoriamente por operação e tag de integridade de 128 bits.
- **FR-014**: O sistema DEVE utilizar chave mestra derivada de `APP_SECRET_KEY` (lida do ambiente ou de arquivo protegido confinado) para a cifra e decifra das credenciais em repouso.
- **FR-015**: No login bem-sucedido, o sistema DEVE decifrar a chave de IA do usuário em memória volátil de sessão, deixando o motor de IA pronto para uso sem expor a chave decifrada na API ou no banco.
- **FR-016**: Em todas as respostas de API (`/api/ai/status`, `/api/users`), a chave de API e os hashes de senha DEVEM permanecer estritamente mascarados ou omitidos, respeitando a política Zero-Leakage (Princípio IV).
- **FR-017**: Ao efetuar logout (`POST /api/auth/logout`), as credenciais de IA e o contexto de sessão decifrado em memória DEVEM ser imediatamente expurgados.
- **FR-018**: O cabeçalho da interface web DEVE exibir o nome do usuário autenticado, seu papel (`Administrador` ou `Usuário`) e um botão acessível para encerramento de sessão.

---

## Key Entities *(mandatory)*

- **`User`**: Representa a conta local de acesso à ferramenta ASVS.
  - Campos: `id` (PK, int), `username` (str, unique, index), `password_hash` (str), `password_salt` (str), `role` (`"admin"` | `"user"`), `must_change_password` (bool), `is_active` (bool), `created_at` (datetime), `updated_at` (datetime).
- **`UserAIConfig`**: Armazena as configurações e o segredo criptografado de IA do usuário.
  - Campos: `id` (PK, int), `user_id` (FK `user.id`, unique, index), `provider` (str), `model_name` (str), `resource_name` (str, opcional), `deployment_id` (str, opcional), `api_version` (str), `encrypted_api_key` (bytes, AES-256-GCM), `nonce` (bytes, 12 bytes), `auth_tag` (bytes, 16 bytes), `key_masked` (str: `"••••••••"`), `updated_at` (datetime).
- **`Run`** *(entidade existente enriquecida)*:
  - Adição de: `user_id` (int, FK `user.id`, index, nullable=False), `owner_username` (str, index, desnormalizado para auditoria).
- **`AuditLog`** *(entidade existente enriquecida)*:
  - Adição de: `user_id` (int, FK `user.id`, index, nullable=False), `actor` (str, fixado como o username da sessão).

---

## Success Criteria *(mandatory)*

- **SC-001**: 100% dos acessos às rotas protegidas sem sessão ativa válida são interceptados e redirecionados para login com `HTTP 401`.
- **SC-002**: A conta inicial padrão `admin / admin` permite o primeiro acesso com sucesso e força compulsoriamente a troca de senha antes de qualquer outra ação.
- **SC-003**: Tentativas de usuários comuns acessarem, visualizarem, exportarem ou triarem execuções de outros usuários resultam em 100% de bloqueio com `HTTP 403 Forbidden` (0% de tolerância a IDOR).
- **SC-004**: O banco de dados SQLite (`asvs.db`) armazena 0 ocorrências de chaves de API ou senhas em texto claro (auditoria por busca de strings e entropia).
- **SC-005**: Ao fazer login, um usuário que já salvou sua chave de API tem suas credenciais decifradas em memória em menos de 100ms, deixando o Playground e o pipeline ASVS imediatamente operacionais.
- **SC-006**: Administradores conseguem listar todas as avaliações de todos os analistas e gerenciar usuários através da Guia 6 de Gestão de Usuários.
- **SC-007**: Toda a suíte de testes automatizados (novos testes de autenticação/RBAC + os 53 testes existentes de ACI, SAST, DAST e Vereditos) atinge 100% de aprovação (GREEN).
- **SC-008**: A conformidade com os Princípios I a VI da Constituição v1.3.0 e com as diretrizes de acessibilidade WCAG 2.2 AA (Zero innerHTML) é preservada integralmente.

