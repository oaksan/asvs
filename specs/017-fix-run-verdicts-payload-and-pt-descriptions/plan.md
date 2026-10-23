# Plano de Implementação: 017 — Correção do payload de vereditos e descrições em português

## Resumo
Correção na origem: enriquecer o payload que a tela realmente usa (`/api/runs/{id}` e `/api/runs/{id}/verdicts`) com os campos de apresentação, endurecer a UI contra campos ausentes e adicionar teste de contrato ponta a ponta, mais orientação/indicação de versão para evitar servidor com código antigo.

## Contexto Técnico
Python 3.12 / FastAPI / SQLModel; JS vanilla. Sem novas dependências e sem mudança de schema SQLite.

## Constitution Check
I (CSV intocado, escopo V1 L1), II (vereditos inalterados), IV (sem execução externa nova, sem segredos), WCAG 2.2 AA (`lang` por trecho já definido na 016).

## Mudanças por Arquivo
| Arquivo | Mudança |
| :--- | :--- |
| `app/main.py` | `list_run_verdicts`: carregar `Requirement` (in_scope) e `load_req_tool_mapping()` uma vez e adicionar `section_id`, `section_name`, `req_description`, `friendly_title`, `description_pt`. Reutilizado por `get_run_details`. Expor `version` no health/rodapé. |
| `static/app.js` | Helper `safeText()`; derivar seção de `req_id`/catálogo; omitir linhas vazias; nunca imprimir `undefined`; filtros por categoria usando seção derivada. |
| `templates/index.html` | Rodapé com versão; `?v=017`. |
| `README.md` | Seção "Executando mudanças em Python" (`docker compose up --build -d` / `restart web`). |
| `tests/test_feature_017_run_verdicts_payload.py` | Teste de contrato dos dois endpoints (execução semeada com 8 vereditos) + teste estático "sem `undefined`". |
| `tests/test_ui_presentation.py`, `tests/test_zip_upload_run.py` | Cache-busting `?v=016` → `?v=017`. |

## Agentes (SDD)
`test-author` (TDD, contrato), `backend-implementer`, `frontend-implementer`, `constitution-guardian` (gates). `aci-security-reviewer`: não necessário (sem superfície de ataque nova; RBAC existente preservado).

## Riscos
- Overhead por requisição: 8 linhas + YAML em cache (`lru_cache`) — desprezível.
- RBAC: `verify_run_access` permanece como primeira operação (sem exposição nova de dados de outras execuções).
