# Quickstart: Feature 007 — Autenticação, RBAC e IA Criptografada

**Feature**: `007-auth-rbac-and-encrypted-user-ai-config`  
**Data**: 2026-10-15  

---

## 1. Primeiro Acesso com a Conta Padrão

1. Inicie a aplicação:
   ```bash
   .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
2. Abra o navegador em `http://localhost:8000`.
3. Você será apresentado à **Tela de Login**:
   - **Usuário**: `admin`
   - **Senha**: `admin`
4. No primeiro login, o sistema detecta `must_change_password=True` e exige a redefinição de senha:
   - Digite a senha atual (`admin`).
   - Defina sua nova senha forte (mínimo 8 caracteres).
5. O acesso ao Dashboard corporativo é liberado imediatamente.

---

## 2. Configurar e Salvar Credenciais de IA Criptografadas em Repouso

1. Acesse a **Guia 5 (Configuração de IA & Playground)**.
2. Selecione o provedor desejado:
   - **Google Gemini**: Modelo `gemini-3.8-flash` e sua API Key.
   - **Azure OpenAI**: `resource_name`, `deployment_id`, `api_version` e `api_key`.
3. Clique em **"Salvar Credenciais em Memória & Perfil"**:
   - O backend cifra a chave usando **AES-256-GCM** e armazena o criptograma no banco `asvs.db`.
   - A chave nunca é exposta em texto claro no disco.
4. Faça logout e login novamente:
   - Suas credenciais de IA são decifradas automaticamente na memória da sua sessão.
   - O status `[✓ Motor Conectado]` já estará ativo sem necessidade de reinserir a chave.

---

## 3. Gerenciamento de Usuários (Exclusivo Administrador)

1. Como `admin`, acesse a **Guia 6 (Gestão de Usuários)**.
2. Preencha o formulário para criar uma nova conta:
   - **Username**: `analista_seguranca`
   - **Senha Inicial**: `SenhaForte123!`
   - **Papel**: `Usuário (user)`
3. Faça logout do `admin` e login com `analista_seguranca`:
   - O analista verá apenas suas próprias avaliações executadas.
   - Não terá acesso à Guia 6 de Gestão de Usuários.
   - Não poderá visualizar nem manipular execuções do `admin` ou de outros analistas (bloqueio 403 Forbidden).

