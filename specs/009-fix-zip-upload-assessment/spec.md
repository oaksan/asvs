# Feature Specification: Correção do Fluxo de Avaliação via Upload de Arquivo .ZIP (Feature 009)

**Feature Branch**: `009-fix-zip-upload-assessment`  
**Created**: 2026-10-20  
**Status**: Approved  
**Input**: User request: "executar o SDD completo da Feature 009 para corrigir o erro quando anexa o zip na avaliação ASVS"

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Submissão de Avaliação via Upload de Arquivo `.ZIP` na Interface Web (Priority: P1)

Como analista de segurança utilizando a interface web do ASVS Self-Assessment Tool, quero selecionar a opção **"Upload de Arquivo .ZIP"**, anexar o pacote `.zip` de um projeto (como o `juice-shop-master.zip` ou qualquer aplicação alvo) e iniciar a avaliação V1 L1 sem erros de serialização ou falha de rede (`SyntaxError: JSON.parse`), tendo o código-fonte extraído com segurança em diretório confinado e analisado pelo pipeline completo (Scoper, SAST, DAST, IA e Verdict).

**Why this priority**: Corrige o bloqueio crítico em que o envio de arquivo `.zip` pela interface web falhava com erro 500 (`UnicodeDecodeError` no FastAPI / `JSON.parse` no navegador) e impedia a avaliação de pacotes `.zip`.

**Independent Test**: Enviar um pacote `.zip` válido via `POST /api/runs/upload` utilizando tanto o campo `zip_file` (enviado pelo frontend) quanto `source_zip`, verificando que a avaliação é criada com `HTTP 202 Accepted`, que `Run.source_path` aponta para o diretório real extraído em `.workspace_uploads/run_<id>` e que a execução conclui com `COMPLETED`.

**Acceptance Scenarios**:

1. **Given** um usuário autenticado com IA configurada e checkbox `zap_authorized=true`, **When** submete o formulário no modo `zip_upload` com um arquivo `.zip` válido, **Then** o frontend envia `POST /api/runs/upload`, o backend extrai os arquivos com segurança em `.workspace_uploads/run_<id>`, persiste o caminho real em `Run.source_path` e retorna `HTTP 202 Accepted` em JSON.
2. **Given** uma execução criada via upload `.zip`, **When** o `OrchestratorAgent` executa o pipeline (ou quando o usuário dispara Reexecução Total/Seletiva dessa execução), **Then** o diretório extraído permanece acessível e confinado dentro de `WORKSPACE_ROOT`, permitindo a leitura pelo `Scoper`, `SASTAgent` e `AIEvaluatorAgent`.

---

### User Story 2 - Suporte a Pacotes `.ZIP` de Projetos Reais com Guardrails Anti-ZipSlip/ZipBomb (Priority: P1)

Como engenheiro de segurança, quero que o guardrail `extract_safe_zip` suporte pacotes `.zip` de projetos reais de médio/grande porte (como o *OWASP Juice Shop*, que possui ~2.500–4.000 arquivos), mantendo bloqueio inegociável contra Path Traversal (`ZipSlip`), links simbólicos POSIX e bombas de descompressão (`ZipBomb`).

**Why this priority**: O limite anterior (`MAX_ZIP_FILES = 2000` e `MAX_ZIP_BYTES = 100 MB`) rejeitava pacotes legítimos como o `juice-shop-master.zip` (~60 MB compactado, >2.000 entradas).

**Independent Test**: Submeter um arquivo `.zip` contendo mais de 2.000 entradas válidas (até 15.000 entradas / 300 MB descompactados) e verificar extração bem-sucedida; submeter arquivos `.zip` contendo `../` ou symlinks e verificar rejeição imediata com `HTTP 400 Bad Request` em JSON.

**Acceptance Scenarios**:

1. **Given** um pacote `.zip` legítimo com até `15.000` entradas e até `300 MB` descompactados, **When** `extract_safe_zip` é executado, **Then** a extração ocorre com sucesso dentro de `.workspace_uploads/run_<id>`.
2. **Given** um pacote `.zip` malicioso contendo entradas com `../` (ZipSlip) ou symlinks POSIX, **When** enviado para `POST /api/runs/upload`, **Then** o guardrail bloqueia a extração e retorna `HTTP 400 Bad Request` com mensagem JSON clara.

---

### User Story 3 - Resiliência JSON em Erros de Validação Binária e no Frontend (Priority: P2)

Como usuário da aplicação, quero que qualquer erro de validação HTTP (incluindo envio acidental de payload binário/multipart para rotas JSON) retorne sempre um objeto JSON válido no backend e seja tratado de forma resiliente no frontend sem lançar `SyntaxError: JSON.parse`.

**Why this priority**: Previne que falhas de validação do FastAPI com bytes não-UTF8 derrubem o handler de exceção com `UnicodeDecodeError` (HTTP 500 texto puro).

**Independent Test**: Enviar um corpo multipart binário contendo bytes inválidos UTF-8 (como `b"PK\x03\x04\xe4..."`) para `POST /api/runs` e verificar que a API responde com `HTTP 422 Unprocessable Entity` em JSON válido, sem `UnicodeDecodeError`.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O frontend (`static/app.js`) DEVE enviar requisições de avaliação com `source_type === "zip_upload"` para o endpoint `POST /api/runs/upload`, validando previamente se um arquivo `.zip` foi selecionado no input `#zip-file`.
- **FR-002**: O endpoint `POST /api/runs/upload` (`app/main.py`) DEVE aceitar o arquivo `.zip` tanto no campo multipart `source_zip` quanto em `zip_file`, garantindo compatibilidade com clientes de API e com a UI web.
- **FR-003**: `create_run_via_upload` DEVE invocar `extract_safe_zip(tmp_zip_path, upload_id)` passando um identificador seguro e utilizar o `Path` retornado pela função como `source_path` no registro `Run` e no `OrchestratorInput`.
- **FR-004**: `app/aci/workspace_aci.py` DEVE ajustar `MAX_ZIP_FILES = 15000` e `MAX_ZIP_BYTES = 300 * 1024 * 1024` (300 MB), preservando a verificação de Path Traversal (`..`), caminhos absolutos, symlinks POSIX e confinamento `is_relative_to`.
- **FR-005**: `app/main.py` DEVE registrar um exception handler para `RequestValidationError` que sanitize objetos `bytes` não-UTF8 antes da serialização JSON, garantindo respostas HTTP 422 sempre em formato JSON.
- **FR-006**: `static/app.js` DEVE ler a resposta HTTP de forma resiliente ao iniciar avaliações, exibindo mensagem amigável caso o servidor retorne erro, mantendo 100% de conformidade com a política **Zero innerHTML**.

