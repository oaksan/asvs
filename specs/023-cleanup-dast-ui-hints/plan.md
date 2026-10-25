# Plano Técnico de Implementação (SDD Plan) — Feature 023: Simplificação Visual do Card DAST

**Branch**: `023-cleanup-dast-ui-hints`  
**Referência da Spec**: [spec.md](file:///home/user/felipe/speckit/asvs/specs/023-cleanup-dast-ui-hints/spec.md)  
**Status**: Pronto para Execução  
**Versão Alvo**: `v023`  

---

## 1. Arquitetura das Alterações

### 1.1 `templates/index.html`
Modificações dentro de `#dast-artifact-card`:
- Linha 163–165: Remover `<small style="color:var(--colorNeutralForeground3);">Allowlist permitida: ...</small>`.
- Linha 169–171: Remover `<div style="padding:8px 12px; ...">Modo de Varredura Fixo: ...</div>`.
- Linhas 179 e 186–188:
  - Remover o atributo `aria-describedby="dast-auth-hint"` do `<input type="checkbox" id="zap-authorized">`.
  - Remover a tag `<div id="dast-auth-hint">...</div>`.
- Atualizar cache-busting para `?v=023` nos links de estilos e scripts.

### 1.2 `app/main.py`
- Incrementar `APP_UI_VERSION = "023"`.

### 1.3 `tests/test_feature_023_cleanup_dast_ui.py`
Criar suíte TDD automatizada validando:
- Ausência das 3 cadeias de texto no HTML renderizado de `/`.
- Ausência do atributo `aria-describedby` quebrado no `#zap-authorized`.
- Presença contínua do badge `OWASP ZAP • Active Scan Fixo`.
- Presença do input hidden `#zap-mode` com valor `active`.
- Presença do container `#dast-auth-container` e do checkbox `#zap-authorized`.
- Teste de integração de guardrail DAST preservado.
- Compatibilidade com `APP_UI_VERSION == "023"`.

---

## 2. Matriz de Rastreabilidade

| Requisito Spec | Componente Modificado | Teste TDD |
| :--- | :--- | :--- |
| **FR-001** (Remoção Allowlist text) | `templates/index.html` | `test_dast_card_does_not_contain_allowlist_text` |
| **FR-002** (Remoção Box Modo Fixo) | `templates/index.html` | `test_dast_card_does_not_contain_fixed_scan_mode_box` |
| **FR-003** (Remoção Hint Termo Legal) | `templates/index.html` | `test_dast_card_does_not_contain_dast_auth_hint` |
| **FR-004** (Remoção ARIA Quebrado) | `templates/index.html` | `test_zap_authorized_has_no_dangling_aria_describedby` |
| **FR-005** (Preservação Funcional DAST) | `app/main.py`, `templates/index.html` | `test_dast_functional_guardrails_remain_active` |
| **NFR-001** (Acessibilidade WCAG 2.2 AA) | `templates/index.html` | `test_zap_authorized_has_no_dangling_aria_describedby` |
| **NFR-002** (Princípio IV) | `app/main.py` | `test_dast_functional_guardrails_remain_active` |

