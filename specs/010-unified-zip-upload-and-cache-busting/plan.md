# Implementation Plan: Suporte Unificado a Upload .ZIP em `POST /api/runs`, Formatação 422 e Cache-Busting (Feature 010)

**Branch**: `010-unified-zip-upload-and-cache-busting` | **Date**: 2026-10-20 | **Spec**: [`spec.md`](spec.md)

---

## 1. Summary

1. **Unificação de Content-Type em `POST /api/runs` (`app/main.py`)**:
   - Alterar `create_run` para inspecionar `request.headers.get("content-type", "")`.
   - Se contiver `"multipart/form-data"`, delegar imediatamente para `await create_run_via_upload(...)`.
   - Caso contrário, fazer parse do corpo JSON e validar via `CreateRunRequest.model_validate(...)`, lançando `RequestValidationError` em caso de falha de schema.
2. **Formatação String em `safe_request_validation_exception_handler` (`app/main.py`)**:
   - Extrair mensagens legíveis de `safe_errors` para compor uma string única em `content["detail"]`, preservando a lista completa em `content["errors"]`.
3. **Cache-Busting e `Cache-Control` (`templates/index.html` e `app/main.py`)**:
   - Adicionar middleware HTTP em `app/main.py` aplicando `Cache-Control: no-cache, must-revalidate` para `/` e `/static/*`.
   - Atualizar referências em `templates/index.html` para `/static/fluent-theme.css?v=010` e `/static/app.js?v=010`.

---

## 2. Architecture & File Modifications

- `app/main.py`:
  - Middleware `disable_static_cache_middleware`.
  - Handler `safe_request_validation_exception_handler` retornando `{"detail": summary_str, "errors": jsonable_encoder(safe_errors)}`.
  - Endpoint `create_run` suportando `multipart/form-data` e `application/json`.
  - `await request.form(max_part_size=300 * 1024 * 1024)` em `create_run_via_upload`.
- `templates/index.html`:
  - Versionamento `?v=010` nos assets estáticos.
- `tests/test_zip_upload_run.py`:
  - Novos testes TDD validando upload multipart direto em `POST /api/runs`, `detail` como string em respostas 422 e cabeçalhos `Cache-Control`.

