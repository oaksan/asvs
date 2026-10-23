# Feature Specification: Suporte Unificado a Upload .ZIP em `POST /api/runs`, Formatação de Erros 422 e Cache-Busting (Feature 010)

**Feature Branch**: `010-unified-zip-upload-and-cache-busting`  
**Created**: 2026-10-20  
**Status**: Approved  
**Input**: User request: "executar o SDD completo da Feature 010 para corrigir o Erro de Guardrail (422): [object Object] ao enviar o arquivo .zip"

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Aceitação Transparente de `multipart/form-data` em `POST /api/runs` (Priority: P1)

Como usuário avaliando um pacote `.zip` (como o `juice-shop-master.zip`), quero que o endpoint `POST /api/runs` aceite nativamente tanto requisições `application/json` (`workspace_path`) quanto `multipart/form-data` (`zip_upload`), delegando automaticamente o upload multipart para `create_run_via_upload`, de modo que o envio funcione imediatamente mesmo sem recarregar a página ou limpar o cache do navegador.

**Why this priority**: Elimina o erro `422 Unprocessable Entity` quando o navegador envia `FormData` para `POST /api/runs`.

**Independent Test**: Enviar uma requisição `multipart/form-data` contendo `zip_file` diretamente para `POST /api/runs` e verificar que retorna `HTTP 202 Accepted` com extração segura em `.workspace_uploads/run_<id>`.

**Acceptance Scenarios**:

1. **Given** um cliente web (com ou sem cache de JS) enviando `FormData` com `zip_file` para `POST /api/runs`, **When** a requisição chega ao backend com `Content-Type: multipart/form-data`, **Then** `create_run` delega a execução para `create_run_via_upload`, extrai o `.zip` e retorna `HTTP 202 Accepted`.
2. **Given** um cliente enviando `Content-Type: application/json` para `POST /api/runs`, **When** o payload segue `CreateRunRequest`, **Then** a execução por `workspace_path` funciona normalmente com `HTTP 202 Accepted`.

---

### User Story 2 - Mensagem `detail` em String Legível para Erros HTTP 422 (Priority: P1)

Como usuário da interface web, quero que qualquer erro `HTTP 422` retorne o campo `detail` como uma string legível em português (mantendo a lista detalhada em `errors`), garantindo que nenhuma versão do frontend exiba `[object Object]` em alertas de erro.

**Why this priority**: Impede que arrays de objetos do Pydantic sejam convertidos em `[object Object]` ao concatenar `payload.detail` em mensagens de alerta.

**Independent Test**: Enviar um JSON inválido para `POST /api/runs` e verificar que a resposta `422` contém `isinstance(resp.json()["detail"], str)` e `isinstance(resp.json()["errors"], list)`.

---

### User Story 3 - Cache-Busting e Cabeçalhos `Cache-Control: no-cache` em Arquivos Estáticos (Priority: P2)

Como usuário da aplicação web, quero que `templates/index.html` referencie `/static/app.js?v=010` e que o servidor envie `Cache-Control: no-cache, must-revalidate` para arquivos estáticos, garantindo que atualizações de código frontend sejam refletidas sem exigir limpeza manual de cache.

**Why this priority**: Evita que o navegador execute versões antigas de `static/app.js` após atualizações do container.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `POST /api/runs` (`app/main.py`) DEVE detectar `Content-Type: multipart/form-data` e delegar a chamada diretamente para `create_run_via_upload`.
- **FR-002**: `create_run_via_upload` DEVE utilizar `await request.form(max_part_size=300 * 1024 * 1024)` para suportar formulários multipart de até 300 MB.
- **FR-003**: `safe_request_validation_exception_handler` (`app/main.py`) DEVE retornar `detail` como `str` legível (concatenando as mensagens de erro sanitizadas) e incluir a lista estruturada no campo `errors`.
- **FR-004**: `templates/index.html` DEVE incluir query string de versão `?v=010` em `/static/app.js` e `/static/fluent-theme.css`, e `app/main.py` DEVE definir `Cache-Control: no-cache, must-revalidate` para respostas de `/static/` e `/`.

