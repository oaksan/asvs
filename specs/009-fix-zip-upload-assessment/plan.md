# Implementation Plan: Correção do Fluxo de Avaliação via Upload de Arquivo .ZIP (Feature 009)

**Branch**: `009-fix-zip-upload-assessment` | **Date**: 2026-10-20 | **Spec**: [`spec.md`](spec.md)

---

## 1. Summary

Esta feature corrige o fluxo de criação de avaliações ASVS via upload de arquivo `.zip` (`zip_upload`):
1. Alinha a chamada `fetch` de `static/app.js` para `POST /api/runs/upload` e adiciona validação prévia de seleção do arquivo `.zip` e parse seguro de respostas JSON/texto.
2. Corrige `create_run_via_upload` em `app/main.py` para aceitar os campos `source_zip` ou `zip_file`, chamar `extracted_dir = extract_safe_zip(tmp_zip_path, upload_id)` e gravar `str(extracted_dir)` em `Run.source_path` e `OrchestratorInput.source_path`.
3. Atualiza os limites do guardrail de descompressão em `app/aci/workspace_aci.py` (`MAX_ZIP_FILES = 15000`, `MAX_ZIP_BYTES = 300 * 1024 * 1024`) mantendo intactas todas as validações contra ZipSlip, Symlinks e ZipBomb.
4. Registra um handler customizado para `RequestValidationError` em `app/main.py` que sanitiza valores `bytes` não-UTF8 antes de `jsonable_encoder`, prevenindo `UnicodeDecodeError` (HTTP 500 texto puro).

---

## 2. Technical Context

- **Language/Version**: Python 3.12+ / FastAPI / SQLModel / Pydantic v2
- **Storage**: SQLite (`asvs.db`) + diretório confinado `.workspace_uploads/run_<id>` dentro de `WORKSPACE_ROOT`
- **Testing**: `pytest` + `FastAPI TestClient` (`tests/test_zip_upload_run.py`)
- **Security Guardrails (Princípio IV)**:
  - Confinamento estrito via `is_relative_to(uploads_dir)` e `is_relative_to(allowed_root)`.
  - Bloqueio de `..`, caminhos iniciados por `/` ou `\`, e symlinks POSIX (`stat.S_ISLNK`).
  - Controle de tamanho descompactado (`MAX_ZIP_BYTES = 300 MB`) e contagem de entradas (`MAX_ZIP_FILES = 15000`).
  - Zero `innerHTML` no frontend (`static/app.js`).

---

## 3. Architecture & File Modifications

### 3.1. `app/aci/workspace_aci.py`
- Atualizar constantes:
  - `MAX_ZIP_BYTES = 300 * 1024 * 1024  # 300 MB`
  - `MAX_ZIP_FILES = 15000`
- Atualizar anotação de tipo de `extract_safe_zip(zip_path: Path, run_id: int | str, base_root: Path | None = None) -> Path` para aceitar `int | str` como identificador do diretório `run_{run_id}`.

### 3.2. `app/main.py`
- Adicionar handler `@app.exception_handler(RequestValidationError)`:
  - Sanitizar campos `input` do tipo `bytes` nos dicionários de `exc.errors()` (convertendo bytes inválidos UTF-8 com `errors="replace"` ou representação segura) e retornar `JSONResponse(status_code=422, content={"detail": sanitized_errors})`.
- Em `POST /api/runs/upload` (`create_run_via_upload`):
  - Obter `zip_file = form.get("source_zip") or form.get("zip_file")`.
  - Invocar `extracted_dir = extract_safe_zip(tmp_zip_path, upload_id)`.
  - Persistir `source_path=str(extracted_dir)` em `Run` e em `OrchestratorInput`.

### 3.3. `static/app.js`
- Em `submitAssessmentForm()`:
  - Se `sourceType === "zip_upload"`, verificar se `fileInput.files[0]` está presente; caso contrário, exibir feedback imediato na UI.
  - Enviar `FormData` com `source_zip` (e `zip_file`) para `POST /api/runs/upload`.
  - Ler a resposta com helper seguro que faz fallback para texto caso o corpo não seja JSON válido, evitando `SyntaxError: JSON.parse`.

