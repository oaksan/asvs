# Tasks: 009-fix-zip-upload-assessment

**Spec Reference**: [`specs/009-fix-zip-upload-assessment/spec.md`](spec.md)  
**Plan Reference**: [`specs/009-fix-zip-upload-assessment/plan.md`](plan.md)  
**Status**: Completed (100% TDD GREEN)

---

## Phase 1: Automated TDD Tests (Blocking Prerequisites)

**Purpose**: Criar testes automatizados em `tests/test_zip_upload_run.py` cobrindo o fluxo de upload `.zip`, extração em `.workspace_uploads`, limites expandidos e resiliência contra payloads binários antes da implementação (TDD RED).

- [x] T001 Criar suite de testes `tests/test_zip_upload_run.py` cobrindo:
  - Upload `.zip` via `POST /api/runs/upload` enviando campo `zip_file` (padrão do frontend `static/app.js`) e `source_zip`.
  - Verificação de que `Run.source_path` existe no sistema de arquivos dentro de `.workspace_uploads/run_<id>` e contém os arquivos extraídos.
  - Suporte a pacotes `.zip` com mais de 2.000 arquivos (ex.: 2.500 entradas simulando projeto do porte do OWASP Juice Shop).
  - Rejeição `HTTP 400 Bad Request` em JSON quando o `.zip` contém Path Traversal (`../`) ou não é um `.zip` válido.
  - Resiliência JSON (`HTTP 422`) quando um corpo binário multipart não-UTF8 é enviado para `POST /api/runs` (prevenindo `UnicodeDecodeError` HTTP 500).
- [x] T002 Executar `.venv/bin/pytest tests/test_zip_upload_run.py` para confirmar estado inicial TDD RED.

---

## Phase 2: Backend & ACI Implementation (Priority: P1 🎯 MVP)

- [x] T003 Atualizar `app/aci/workspace_aci.py`:
  - Elevar `MAX_ZIP_FILES = 15000` e `MAX_ZIP_BYTES = 300 * 1024 * 1024` (300 MB).
  - Permitir `run_id: int | str` em `extract_safe_zip`, validar em duas passagens e limpar diretório em caso de exceção.
- [x] T004 Atualizar `app/main.py`:
  - Registrar `@app.exception_handler(RequestValidationError)` sanitizando objetos `bytes` não-UTF8 em `exc.errors()` para evitar `UnicodeDecodeError`.
  - Em `POST /api/runs/upload` (`create_run_via_upload`), aceitar `form.get("source_zip") or form.get("zip_file")`.
  - Capturar `extracted_dir = extract_safe_zip(tmp_zip_path, upload_id)` e atribuir `str(extracted_dir)` a `Run.source_path` e `OrchestratorInput.source_path`.

---

## Phase 3: Frontend Implementation (Priority: P1 🎯 MVP)

- [x] T005 Atualizar `static/app.js` em `submitAssessmentForm()`:
  - Validar que um arquivo `.zip` foi selecionado quando `sourceType === "zip_upload"`.
  - Enviar o `FormData` para `POST /api/runs/upload` (incluindo `source_zip` e `zip_file`).
  - Fazer parse resiliente da resposta HTTP (evitando `SyntaxError: JSON.parse` caso ocorra erro de rede/proxy) mantendo 100% de conformidade com **Zero innerHTML**.
- [x] T006 Executar `.venv/bin/pytest tests/test_zip_upload_run.py` e confirmar 100% TDD GREEN.

---

## Phase 4: Homologação, Regressão e Revisão de Segurança (Gate 3)

- [x] T007 Executar suíte completa `.venv/bin/pytest -q` garantindo zero regressão (`105 passed`).
- [x] T008 Executar auditorias `aci-security-reviewer` e `llm-security-reviewer`.
- [x] T009 Obter aprovação formal do Gate 3 pelo `constitution-guardian` e reiniciar container `web`.
