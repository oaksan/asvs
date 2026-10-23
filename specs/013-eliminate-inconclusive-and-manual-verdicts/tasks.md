# Tasks (SDD): Eliminação de Vereditos `INCONCLUSIVE` e `MANUAL_REQUIRED` (`013-eliminate-inconclusive-and-manual-verdicts`)

**Input**: Design documents from `/specs/013-eliminate-inconclusive-and-manual-verdicts/`  
**Prerequisites**: `spec.md`, `plan.md`

---

## Phase 1: Especificação, Mapeamento ASVS e Gate Arquitetural
- [x] T001 Consultar `asvs-mapper` e `solution-architect` para validar as novas regras Semgrep (`v1-2-5-js-child-process-exec`, `v1-3-1-js-angular-unsanitized-html`, `v1-5-1-js-xxe-libxml-noent`) e a lógica de evidência positiva em `scan_workspace_surface` e `ai_aci.py`.
- [x] T002 Invocar `constitution-guardian` para auditoria formal dos Gates 1 e 2 (garantindo conformidade com o Princípio II — Honestidade Epistêmica).

## Phase 2: Testes Automatizados (TDD First)
- [x] T003 [P] Criar suíte `tests/test_feature_013_conclusive_verdicts.py` via `test-author` cobrindo:
  - Coleta de contexto `_collect_code_context_for_v1_3_1("app")` capturando as linhas 120–124 de `app/main.py` (`select_autoescape`) além da linha 60.
  - Coleta de contexto `_collect_code_context_for_v1_3_1` em projetos TypeScript/JavaScript capturando `bypassSecurityTrustHtml` / `DOMPurify`.
  - Detecção SAST Semgrep nas novas regras JS/TS (`v1-2-5-js-child-process-exec`, `v1-3-1-js-angular-unsanitized-html`, `v1-5-1-js-xxe-libxml-noent`).
  - `scan_workspace_surface` gerando evidências positivas auditáveis para `V1.2.5` e `V1.5.1` em projetos Python (`app/`) e Node.js/TS (`Juice Shop`) quando `code_files_count > 0`, mas mantendo `0` indicadores quando `code_files_count == 0` (diretório vazio -> `INCONCLUSIVE`).
  - Preservação de `MANUAL_REQUIRED` em `V1.3.1` quando a IA não está configurada (`ai_configured=False`), e emissão de `PASS`/`FAIL` conclusivo quando configurada.
  - Presença dos cabeçalhos `X-Content-Type-Options: nosniff` e `Content-Security-Policy` nas respostas de `app/main.py`.

## Phase 3: Implementação de Regras SAST e Backend
- [x] T004 Atualizar `config/semgrep_rules/v1_2_injection.yaml`, `config/semgrep_rules/v1_3_sanitization.yaml`, `config/semgrep_rules/v1_5_deserialization.yaml` e `config/req_tool_mapping.yaml` via `sast-rules-engineer`.
- [x] T005 Atualizar `app/aci/workspace_aci.py`, `app/aci/ai_aci.py`, `app/verdict.py` e `app/main.py` via `backend-implementer`.

## Phase 4: Verificação, Revisão de Segurança e Deploy
- [x] T006 Executar `.venv/bin/pytest -q` para validar 100% de aprovação na suíte de testes (121 passed).
- [x] T007 Executar revisores `aci-security-reviewer`, `llm-security-reviewer` e `constitution-guardian` (Gate 3 Final).
- [x] T008 Reconstruir e reiniciar o container `asvs-self-assessment-web` (`docker compose up -d --build web`).

