# Tasks: 010-unified-zip-upload-and-cache-busting

**Spec Reference**: [`specs/010-unified-zip-upload-and-cache-busting/spec.md`](spec.md)  
**Plan Reference**: [`specs/010-unified-zip-upload-and-cache-busting/plan.md`](plan.md)  
**Status**: Completed (100% TDD GREEN — Gates 1, 2 e 3 Aprovados)

---

## Phase 1: Automated TDD Tests

- [x] T001 Adicionar testes em `tests/test_zip_upload_run.py`:
  - `test_post_api_runs_accepts_multipart_zip_upload_directly`: envia `multipart/form-data` com `zip_file` diretamente para `POST /api/runs` e verifica `HTTP 202 Accepted` + extração real dos arquivos.
  - `test_validation_error_422_returns_string_detail_never_object_list`: envia payload inválido para `POST /api/runs` e verifica que `resp.json()["detail"]` é uma `str` legível (nunca array bruto que gere `[object Object]`).
  - `test_static_assets_and_index_have_cache_busting_and_no_cache_headers`: verifica `?v=010` no HTML e `Cache-Control: no-cache` em `/static/app.js`.
  - `test_real_juice_shop_master_zip_upload_via_post_api_runs`: testa o pacote real `/home/user/felipe/speckit/juice-shop-master.zip` em `POST /api/runs`.
- [x] T002 Executar `.venv/bin/pytest tests/test_zip_upload_run.py` para confirmar estado inicial TDD RED.

---

## Phase 2: Backend & Template Implementation

- [x] T003 Atualizar `app/main.py`:
  - Suporte dual (`multipart/form-data` + `application/json`) em `POST /api/runs`.
  - `await request.form(max_part_size=300 * 1024 * 1024)` em `create_run_via_upload`.
  - `detail` como string legível em `safe_request_validation_exception_handler`.
  - Middleware `Cache-Control: no-cache, must-revalidate` para `/` e `/static/*`.
- [x] T004 Atualizar `templates/index.html` com `?v=010` em `/static/app.js` e `/static/theme.css`.
- [x] T005 Executar `.venv/bin/pytest tests/test_zip_upload_run.py` e confirmar TDD GREEN.

---

## Phase 3: Regressão, Auditoria de Segurança e Gate 3

- [x] T006 Executar `.venv/bin/pytest -q` e validar 100% GREEN.
- [x] T007 Revisão com `aci-security-reviewer`, `llm-security-reviewer` e `constitution-guardian` (Gates 1, 2 e 3).
- [x] T008 Reiniciar container `asvs-self-assessment-web` e testar upload real do `juice-shop-master.zip` em `POST /api/runs`.

