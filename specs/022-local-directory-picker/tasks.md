# Tarefas de Engenharia (SDD Tasks) — Feature 022: Seleção de Diretório Local do Código-Fonte

**Branch**: `022-local-directory-picker`  
**Status**: Concluído (Aprovado em Gate Final)  

---

## Fase 1 — TDD (Testes Automatizados Pré-Implementação)
- [x] **T001**: Criar `tests/test_feature_022_directory_upload.py` contendo a suíte de 13 testes do plano técnico:
  - Testes unitários para `save_safe_directory_upload` (sucesso, path traversal, caminhos absolutos, dispositivos especiais, conflito arquivo/diretório, cotas de tamanho e rollback em falha).
  - Testes de integração para `POST /api/runs/upload-directory` (sucesso, autenticação 401, gate DAST 403, gate IA 412 e disparidade de listas 400).
  - Teste de conformidade estática de assets (`webkitdirectory`, ausência de "Caminho em Workspace Local", cache-busting `?v=022`).
- [x] **T002**: Ajustar testes legados que validavam estritamente a versão `?v=021` ou o rótulo "Caminho em Workspace Local".

---

## Fase 2 — Backend (`app/aci/workspace_aci.py` e `app/main.py`)
- [x] **T003**: Implementar em `app/aci/workspace_aci.py`:
  - Constantes `MAX_DIR_UPLOAD_FILE_BYTES`, `MAX_DIR_TOTAL_BYTES` e `MAX_DIR_FILES`.
  - Função `save_safe_directory_upload` com validação de caminho em 2 fases, checagem Unicode NFC, bloqueio de symlinks via `os.open` e rollback com `shutil.rmtree`.
- [x] **T004**: Implementar endpoint `POST /api/runs/upload-directory` em `app/main.py`:
  - Dependência `get_current_user` e gates pré-flight (DAST e IA).
  - Extração de `files` e `paths` do multipart.
  - Gravação segura e criação de `Run(source_type="directory_upload", ...)`.
- [x] **T005**: Atualizar constante `APP_UI_VERSION = "022"` em `app/main.py`.

---

## Fase 3 — Frontend (`templates/index.html` e `static/app.js`)
- [x] **T006**: Atualizar `templates/index.html`:
  - Renomear opção de origem para "Caminho em Diretório Local" (`directory_upload`).
  - Substituir campo de texto pelo grupo `#directory-upload-group` com input `webkitdirectory directory multiple` e elemento de resumo acessível.
  - Atualizar links de scripts e CSS para `?v=022`.
- [x] **T007**: Implementar lógica em `static/app.js`:
  - Alternância de visibilidade entre upload de diretório e upload de ZIP em `syncSastSourceFields()`.
  - Filtro preventivo de pastas pesadas e arquivos de segredos órfãos.
  - Listener para exibição do resumo `📁 <pasta> — X arquivos (Y ignorados, Z MB)` via `textContent` seguro.
  - Conexão do envio do formulário com `POST /api/runs/upload-directory` via `FormData`.

---

## Fase 4 — Verificação e Docker
- [x] **T008**: Executar suíte de testes direcionada:
  - `.venv/bin/pytest -vv tests/test_feature_022_directory_upload.py` (13/13 passaram)
- [x] **T009**: Executar suíte completa de regressão:
  - `.venv/bin/pytest -q` (177/177 passaram)
- [x] **T010**: Rebuild dos containers Docker:
  - `docker compose up --build -d web`
  - Validar status HTTP 200 e rodapé "Versão 022".

---

## Fase 5 — Revisão de Segurança & Conformidade Constitucional
- [x] **T011**: Auditoria de segurança ACI com foco em confinamento de upload (Aprovado com 0 violações).
- [x] **T012**: Auditoria constitucional final (Gate 3 - Aprovado com 100% de conformidade).

---

## Fase 6 — Versionamento & Sincronização Git
- [x] **T013**: Validar que `.gitignore` protege diretórios temporários de upload (`.workspace_uploads/`), banco SQLite (`asvs.db`) e credenciais.
- [x] **T014**: Executar `git add specs/022-local-directory-picker/ app/ templates/ static/ tests/`.
- [x] **T015**: Criar commit semântico `feat(spec-022): selecao de diretorio local do codigo-fonte com botao Procurar`.
- [x] **T016**: Criar tag `v022` e sincronizar no GitHub via `git push origin main v022`.
