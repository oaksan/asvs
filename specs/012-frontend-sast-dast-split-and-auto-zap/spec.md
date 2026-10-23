# Feature Specification: Separação Visual SAST/DAST, Alternância Exclusiva de Fonte SAST, Active Scan Padrão e Auto-Validação do OWASP ZAP

**Feature Branch**: `012-frontend-sast-dast-split-and-auto-zap`  
**Created**: 2026-10-20  
**Status**: Draft  
**Input**: Melhorar o frontend de "Configurar Nova Avaliação de Segurança": (1) modo de varredura sempre Active Scan; (2) validação automática de que o ZAP está online alguns segundos após subir a aplicação sem precisar clicar em "Verificar Conexão"; (3) separar visualmente e exigir os artefatos de SAST e DAST; (4) no SAST, alternar exclusivamente entre o textbox "Caminho Relativo no Workspace" e o botão procurar de "Arquivo .ZIP do Código-Fonte" conforme a seleção do combobox "Origem do Código-Fonte".

---

## 1. Diagnóstico e Contexto Técnico

1. **Bug de CSS no atributo `hidden` (`.form-field { display: flex; }`)**:
   - Em `static/theme.css`, a classe `.form-field` define `display: flex;`, que possui especificidade superior ao estilo nativo do navegador `[hidden] { display: none; }`. Por isso, `#workspace-path-group` e `#zip-upload-group` apareciam simultaneamente na tela mesmo quando um deles possuía o atributo `hidden`.
2. **Atraso na inicialização do container OWASP ZAP e falta de revalidação automática**:
   - Quando a aplicação sobe via `docker compose up -d`, o container `web` (FastAPI) inicia em ~1s, enquanto o daemon Java do OWASP ZAP leva de 5s a 15s para disponibilizar sua API REST. Além disso, `refreshZapStatus()` não era chamado após o login nem possuía retry automático nos primeiros segundos após a subida, obrigando o usuário a clicar manualmente em "Verificar Conexão".
3. **Mistura de campos SAST e DAST no formulário e modo de varredura manual**:
   - Os campos de SAST e DAST estavam misturados em um único grid plano, e o modo de varredura vinha em `baseline` por padrão. O usuário deseja que o formulário apresente e exija separadamente os artefatos de **SAST** e de **DAST**, mantendo o modo de varredura sempre em **Active Scan (`active`)**.

---

## 2. User Scenarios & Testing *(mandatory)*

### User Story 1 - Separação Visual e Obrigatoriedade dos Artefatos SAST e DAST com Alternância Exclusiva no SAST (Priority: P1)

Como analista de segurança configurando uma nova avaliação, quero visualizar os parâmetros de **SAST (Análise Estática)** e **DAST (Análise Dinâmica)** em cartões separados e claramente identificados, onde o cartão SAST exibe exclusivamente o campo correspondente à origem selecionada (Caminho ou Arquivo `.ZIP`), e ambos os artefatos (SAST e DAST) são validados antes do início da execução.

**Acceptance Scenarios**:

1. **Given** que o usuário está na tela "Configurar Nova Avaliação de Segurança", **When** o combobox "Origem do Código-Fonte" está em `Caminho em Workspace Local` (`workspace_path`), **Then** o textbox "Caminho Relativo no Workspace" (`#workspace-path-group`) é exibido e o seletor "Arquivo .ZIP do Código-Fonte" (`#zip-upload-group`) permanece estritamente oculto (`display: none` / `hidden`).
2. **Given** que o usuário altera o combobox "Origem do Código-Fonte" para `Upload de Arquivo .ZIP` (`zip_upload`), **When** o evento `change` dispara, **Then** o textbox "Caminho Relativo no Workspace" é ocultado e apenas o botão/input "Arquivo .ZIP do Código-Fonte" é exibido.
3. **Given** que o usuário clica em "Iniciar Avaliação V1 L1", **When** o artefato SAST (caminho ou arquivo `.zip`) ou o artefato DAST (`target_url` e checkbox `zap_authorized`) não foi preenchido, **Then** o frontend destaca o campo pendente e exibe mensagem clara exigindo o preenchimento dos artefatos de SAST e DAST.

---

### User Story 2 - Modo de Varredura Sempre Active Scan (`active`) (Priority: P1)

Como analista de segurança, quero que o modo de varredura do OWASP ZAP seja sempre **Active Scan (`active`)**, garantindo a verificação completa dos requisitos dinâmicos (`V1.2.1` a `V1.2.5` e `V1.5.1`) sem precisar alterar manualmente o seletor a cada execução.

**Acceptance Scenarios**:

1. **Given** que a seção DAST é carregada na interface, **When** uma avaliação é configurada ou disparada, **Then** o modo de varredura (`zap_mode`) está fixado em `active` (**Active Scan — Cobertura Completa V1.2.1–V1.2.5 e V1.5.1**) tanto no frontend quanto no default dos schemas de backend.

---

### User Story 3 - Validação Automática de Conectividade do OWASP ZAP Pós-Subida (Priority: P1)

Como analista de segurança, quero que a interface valide automaticamente se o OWASP ZAP está `ONLINE` alguns segundos após subir a aplicação (e logo após o login), atualizando o badge para `ZAP ONLINE` automaticamente sem que eu precise clicar no botão "Verificar Conexão".

**Acceptance Scenarios**:

1. **Given** que a aplicação acabou de subir e o usuário abre a interface (ou realiza login), **When** o OWASP ZAP leva alguns segundos para iniciar, **Then** o frontend executa verificações automáticas escalonadas (ex.: imediato, `3s`, `6s`, `12s` e polling periódico enquanto `OFFLINE`) e atualiza automaticamente o badge `#zap-status-badge` para `ZAP ONLINE` assim que o daemon responder.

---

## 3. Requirements *(mandatory)*

- **FR-001 (CSS `[hidden]` Override Fix)**: `static/theme.css` DEVE declarar `[hidden] { display: none !important; }` para garantir que elementos `.form-field[hidden]` nunca sejam exibidos por conflito de especificidade com `display: flex`.
- **FR-002 (Separação SAST e DAST)**: `templates/index.html` DEVE estruturar o formulário `#new-run-form` em dois blocos/cartões distintos lado a lado:
  1. **Artefato SAST (Análise Estática — Semgrep & IA)** contendo `#source-type`, `#workspace-path-group` e `#zip-upload-group`.
  2. **Artefato DAST (Análise Dinâmica — OWASP ZAP)** contendo `#target-url` (obrigatório), modo fixo **Active Scan (`#zap-mode` = `active`)** e o termo de consentimento `#zap-authorized`.
- **FR-003 (Modo Sempre Active Scan)**: O campo `#zap-mode` no frontend e o default de `zap_mode` em `CreateRunRequest` / `RunCreate` / `create_run_via_upload` DEVEM ser sempre `"active"`.
- **FR-004 (Auto-Validação do ZAP Pós-Subida)**: `static/app.js` DEVE disparar `refreshZapStatus()` no carregamento inicial (`DOMContentLoaded`), imediatamente após o login bem-sucedido, e agendar verificações automáticas após `3s`, `6s`, `12s` (além de polling leve a cada `10s` enquanto o status estiver `OFFLINE`).
- **FR-005 (Cache-Busting)**: Atualizar a versão dos assets estáticos em `templates/index.html` e nos testes correspondentes para garantir carregamento imediato do novo CSS e JS.

