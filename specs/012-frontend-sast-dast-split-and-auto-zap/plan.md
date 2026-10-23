# Implementation Plan: Separação Visual SAST/DAST, Alternância Exclusiva SAST, Active Scan Padrão e Auto-Validação ZAP

**Branch**: `012-frontend-sast-dast-split-and-auto-zap` | **Date**: 2026-10-20 | **Spec**: [spec.md](file:///home/user/felipe/speckit/asvs/specs/012-frontend-sast-dast-split-and-auto-zap/spec.md)

---

## 1. Summary

Reestruturar a seção **"Configurar Nova Avaliação de Segurança"** (`templates/index.html`, `static/theme.css`, `static/app.js`) e os defaults de `zap_mode` (`app/models.py`, `app/schemas.py`, `app/main.py`) para:
1. Separar visualmente e validar como obrigatórios os blocos **1. Artefato SAST (Código-Fonte)** e **2. Artefato DAST (Aplicação em Execução)**.
2. Corrigir a regra `[hidden] { display: none !important; }` em `static/theme.css` e sincronizar via JS (`syncSastSourceFields`) para que o combobox **Origem do Código-Fonte** exiba exclusivamente o textbox **Caminho Relativo no Workspace** OU o botão procurar de **Arquivo .ZIP do Código-Fonte**.
3. Fixar o modo de varredura DAST sempre em **Active Scan (`active`)**.
4. Implementar auto-validação pós-subida do container OWASP ZAP (`scheduleZapAutoCheck`) disparada no boot da página, após login e com retries automáticos (`3s`, `6s`, `12s` e polling de `10s` enquanto `OFFLINE`).

---

## 2. Alterações Detalhadas por Arquivo

### 2.1. `static/theme.css`
- Adicionar regra global:
  ```css
  [hidden] {
    display: none !important;
  }
  ```
- Adicionar estilos para `.artifact-split-grid` e `.artifact-section-card` (dois cartões lado a lado com borda, cabeçalho semântico SAST / DAST e destaque visual de erro).

### 2.2. `templates/index.html`
- Dentro de `#new-run-form`:
  - Substituir a lista plana de campos por `.artifact-split-grid` contendo dois cartões distintos:
    - **Cartão 1 (`#sast-artifact-card`): 1. Artefato SAST — Código-Fonte (Semgrep & IA)**
      - Combobox `#source-type` (`Caminho em Workspace Local` | `Upload de Arquivo .ZIP`)
      - `#workspace-path-group` (visível quando `source-type == "workspace_path"`)
      - `#zip-upload-group` (`hidden`, visível apenas quando `source-type == "zip_upload"`)
    - **Cartão 2 (`#dast-artifact-card`): 2. Artefato DAST — Aplicação Alvo (OWASP ZAP)**
      - Input `#target-url` (`required`, com dica de allowlist)
      - Campo `#zap-mode` fixado em `active` (`Active Scan — Ataque Ativo + Spider`)
      - Container `#dast-auth-container` com checkbox `#zap-authorized` integrado ao cartão DAST.

### 2.3. `static/app.js`
- **`syncSastSourceFields()`**:
  - Lê `sourceSelect.value`:
    - Se `"zip_upload"`: `pathGroup.hidden = true; pathGroup.style.display = "none"; zipGroup.hidden = false; zipGroup.style.display = "flex";`
    - Se `"workspace_path"`: `pathGroup.hidden = false; pathGroup.style.display = "flex"; zipGroup.hidden = true; zipGroup.style.display = "none";`
  - Executada na inicialização (`initAssessmentForm`), no evento `change` de `#source-type` e no botão `Autoavaliar Própria Ferramenta`.
- **`scheduleZapAutoCheck()`**:
  - Executa `refreshZapStatus()` imediatamente no `DOMContentLoaded` e após o login.
  - Agenda verificações automáticas em `3000ms`, `6000ms` e `12000ms` após a subida da aplicação (e mantém um `setInterval` a cada `10000ms` que consulta `/api/zap/status` caso `state.zapStatus.online` ainda seja `false`).
- **Validação de Artefatos SAST + DAST em `submitAssessmentForm()`**:
  - Valida se o artefato SAST foi fornecido (`subpath` não vazio quando `workspace_path`, ou `zipFileInput.files.length > 0` quando `zip_upload`).
  - Valida se o artefato DAST (`targetUrl`) foi preenchido (quando exigido na avaliação pela interface) e se o checkbox `zap_authorized` está marcado.
  - Envia sempre `zap_mode = "active"`.

### 2.4. `app/models.py`, `app/schemas.py` e `app/main.py`
- Atualizar default de `zap_mode` para `"active"` em `CreateRunRequest`, `RunCreate` e `create_run_via_upload`.

