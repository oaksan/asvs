# Plano de Implementação: 015 — Descrição dos requisitos em Resultado por Verificação

## Resumo
Mudança aditiva e de baixo risco: enriquecer o relatório com `friendly_title`, e reorganizar a tabela `#verdicts-table` para mostrar título + descrição sob o identificador de cada requisito.

## Contexto Técnico
Python 3.12 / FastAPI / SQLModel; frontend HTML5 + JS vanilla + Fluent 2. Sem novas dependências. Sem mudança de schema no SQLite (título vem do YAML de mapeamento).

## Constitution Check
- I (escopo V1 L1, 8 req): preservado. II (vereditos): sem alteração. IV (guardrails): sem novas execuções externas, sem segredos. Acessibilidade WCAG 2.2 AA: coberta por FR-006.

## Mudanças por Arquivo
| Arquivo | Mudança |
| :--- | :--- |
| `config/req_tool_mapping.yaml` | Adicionar `friendly_title` aos 8 requisitos. |
| `app/agents/reporter_agent.py` | Incluir `friendly_title` (fallback `section_name`) em cada item de veredito. |
| `app/main.py` | Incluir `friendly_title` em `/api/requirements/in-scope` (campo aditivo). |
| `templates/index.html` | Remover coluna "O que foi verificado"; ajustar `colspan` para 4. |
| `static/app.js` | `renderVerdictsTable`: título + descrição na col. 1; fallback via catálogo em escopo (cache em memória do resultado de `/api/requirements/in-scope`). |
| `static/theme.css` | Estilos da descrição (quebra de linha, `max-width`, impressão). |
| `tests/test_feature_015_requirement_descriptions.py` | Testes novos. |

## Agentes (SDD)
`asvs-mapper` (títulos), `test-author` (TDD), `frontend-implementer`, `backend-implementer`, `constitution-guardian` (gates).

## Riscos
Cache do navegador servindo `app.js` antigo → mitigado pelo cache-busting da Feature 010.
