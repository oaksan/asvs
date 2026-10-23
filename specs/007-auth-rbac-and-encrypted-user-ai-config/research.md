# Phase 0 Research: Autenticação Local, RBAC e Criptografia em Repouso de IA

**Feature**: `007-auth-rbac-and-encrypted-user-ai-config`  
**Data**: 2026-10-15  
**Status**: Concluído (Decisões Técnicas Validadas)

---

## 1. Problemas Investigados e Decisões Técnicas

### Decisão 1: Algoritmo de Hashing de Senhas
- **Opções Analisadas**:
  1. *Argon2id*: Excelente resistência a GPU/ASIC, mas requer bibliotecas C nativas adicionais.
  2. *Bcrypt*: Amplamente adotado, mas truncado a 72 bytes.
  3. *PBKDF2-HMAC-SHA256*: Recomendado pelo NIST SP 800-63B e OWASP Password Storage Cheat Sheet (mínimo 600.000 iterações per OWASP 2024), nativo no Python via `hashlib.pbkdf2_hmac`, com portabilidade total e zero dependências de compilação.
- **Decisão**: **PBKDF2-HMAC-SHA256** com:
  - Iterações: `600_000`
  - Salt: 32 bytes gerados por `secrets.token_bytes(32)`
  - Formato de armazenamento: `pbkdf2:sha256:600000:<salt_hex>:<hash_hex>`
  - Comparação em tempo constante: `hmac.compare_digest` para imunidade contra timing attacks.

---

### Decisão 2: Criptografia em Repouso de Credenciais de IA (Zero-Leakage no SQLite)
- **Problema**: O Princípio IV da Constituição proíbe terminantemente armazenar chaves de API em texto claro no banco de dados SQLite (`asvs.db`).
- **Opções Analisadas**:
  1. *Fernet (AES-128-CBC + HMAC-SHA256)*: Seguro, mas produz tokens mais longos em base64.
  2. *AES-256-GCM (Galois/Counter Mode)*: Cifra simétrica autenticada (AEAD) de 256 bits, padrão internacional (FIPS 197 / NIST SP 800-38D), fornece confidencialidade e autenticação de integridade simultânea via Authentication Tag de 128 bits.
- **Decisão**: **AES-256-GCM** via `cryptography.hazmat.primitives.ciphers.aead.AESGCM`:
  - Derivação de Chave: A chave de 32 bytes (256 bits) é derivada de `APP_SECRET_KEY` utilizando **HKDF-SHA256** com contexto estático `"asvs-ai-secret-storage"`.
  - Nonce/IV: 12 bytes gerados aleatoriamente por operação (`os.urandom(12)`).
  - Criptograma persistido: `encrypted_api_key` (bytes cifrados contendo a tag de 16 bytes apensada pelo AESGCM), e `nonce` (12 bytes).
  - Qualquer tentativa de adulteração de bytes no SQLite resulta em falha de autenticação de tag (`InvalidTag`), prevenindo injeções de cifras.

---

### Decisão 3: Mecanismo de Sessão Web e Cookies
- **Opções Analisadas**:
  1. *JWT em LocalStorage*: Vulnerável a exfiltração por ataques de DOM XSS.
  2. *JWT em Cookie*: Requer gerenciamento de revogação/blacklisting.
  3. *Sessão Opaca em Cookie HttpOnly*: Token aleatório de alta entropia (256 bits) armazenado em cookie seguro `HttpOnly; SameSite=Lax; Path=/`, com estado em memória volátil `UserSessionStore`.
- **Decisão**: **Sessão Opaca em Cookie `asvs_session`**:
  - Token: `secrets.token_urlsafe(32)` (256 bits de entropia).
  - Flags: `HttpOnly=True` (inviolável via `document.cookie`), `SameSite="Lax"`, `Path=/`, e `Secure=False` em desenvolvimento local / `Secure=True` em produção.
  - Expiração: Inatividade de 60 minutos e expiração absoluta de 8 horas.
  - Regeneração: Ao fazer login bem-sucedido, qualquer identificador de sessão anterior é destruído e um novo token é emitido (imunidade contra Session Fixation).
  - No logout: O cookie é expirado imediatamente (`Max-Age=0`) e o registro volátil de sessão é expurgado do servidor.

---

### Decisão 4: Ciclo de Vida da Chave de IA e Isolamento Multi-Usuário
- **Problema**: O `AISecretStore` atual é um Singleton global de processo, compartilhando a chave entre todas as requisições.
- **Decisão**: Desacoplar o gerenciamento de credenciais ativas para contexto do usuário:
  1. **Persistência**: Ao salvar credenciais na Guia 5, a chave é cifrada com AES-256-GCM e gravada no registro `user_ai_config` vinculado a `current_user.id`.
  2. **Handshake no Login**: Imediatamente após a validação da senha no login, a aplicação lê `user_ai_config`, decifra a chave em memória e popula o contexto de sessão volátil daquele usuário.
  3. **Execução de Pipeline / Chat**: Quando o usuário dispara uma avaliação ou envia mensagem no Playground, o pipeline consome as credenciais da sessão ativa daquele usuário.
  4. **Zero-Leakage**: Em nenhuma circunstância a chave decifrada é serializada no banco, refletida em endpoints REST ou logada.

---

### Decisão 5: Controle de Acesso Baseado em Papéis (RBAC) e Prevenção de IDOR
- **Regras de Autorização**:
  - `admin`: Pode visualizar, listar, cancelar, reexecutar e comparar todas as avaliações no sistema; possui acesso exclusivo à Guia 6 de Gestão de Usuários.
  - `user`: Filtro estrito `Run.user_id == current_user.id` em todas as consultas. Tentativas de acessar qualquer ID pertencente a outro usuário retornam `HTTP 403 Forbidden`.
  - Validador reutilizável: Dependência `verify_run_ownership(run_id, current_user, session)` aplicada de forma padronizada a todos os endpoints de runs, findings, evidence, export e SSE.

---

### Decisão 6: Compatibilidade e Migração Idempotente do Banco SQLite
- **Cenário**: O banco existente `asvs.db` já possui registros de `Run`, `Finding`, `Evidence` sem a coluna `user_id`.
- **Estratégia de Migração**:
  - Na função `init_db()`, executar `CREATE TABLE IF NOT EXISTS` para as novas tabelas `user` e `user_ai_config`.
  - Executar verificação `PRAGMA table_info(run)`: se a coluna `user_id` não existir, executar `ALTER TABLE run ADD COLUMN user_id INTEGER DEFAULT 1` e `ALTER TABLE run ADD COLUMN owner_username TEXT DEFAULT 'admin'`.
  - Criar o usuário `admin` caso a tabela `user` esteja vazia, associando as execuções legadas ao `admin`.
  - Zero perda de dados ou quebra de retrocompatibilidade.

