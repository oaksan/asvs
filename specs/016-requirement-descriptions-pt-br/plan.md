# Plano de Implementação: 016 — Descrições dos requisitos em português

## Resumo
Mudança aditiva e de baixo risco: novo campo `description_pt` no YAML de mapeamento, exposto no relatório e no endpoint em escopo, e consumido pela UI com fallback para o texto normativo em inglês, que passa a ser um "Texto original" recolhível.

## Contexto Técnico
Python 3.12 / FastAPI / SQLModel; frontend HTML5 + JS vanilla + Fluent 2. Sem novas dependências. Sem mudança de schema.

## Constitution Check
- I: CSV continua a fonte normativa; tradução é camada de apresentação, escopo V1 L1 preservado.
- II: vereditos inalterados. IV: sem novas execuções externas e sem segredos.
- Acessibilidade WCAG 2.2 AA: `lang` por trecho (FR-006).

## Mudanças por Arquivo
| Arquivo | Mudança |
| :--- | :--- |
| `config/req_tool_mapping.yaml` | Adicionar `description_pt` aos 8 requisitos (textos da spec §3). |
| `app/agents/reporter_agent.py` | Incluir `description_pt` (fallback `""`) em cada veredito. |
| `app/main.py` | Incluir `description_pt` em `/api/requirements/in-scope`. |
| `static/app.js` | `renderVerdictsTable` e `openRequirementModal`: PT como principal; `<details>` com texto original; fallback para inglês; cache do catálogo em escopo. |
| `static/theme.css` | Estilos do `<details>` de texto original e impressão (aberto). |
| `templates/index.html` | Bump de cache-busting `?v=016`. |
| `tests/test_feature_016_requirement_descriptions_pt.py` | Testes novos; ajustar testes de cache `?v=015` → `?v=016`. |

## Agentes (SDD)
`asvs-mapper` (validar fidelidade das traduções), `test-author` (TDD), `backend-implementer`, `frontend-implementer`, `constitution-guardian` (gates).

## Riscos
Fidelidade da tradução → tabela revisada no Gate 1 e texto original sempre acessível. Cache do navegador → `?v=016`.
