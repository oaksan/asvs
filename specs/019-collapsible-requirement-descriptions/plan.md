# Plano de Implementação: 019 — Descrição Completa em Bloco Recolhível para V1.2.1 a V1.5.1

## 1. Resumo Executivo
Implementar um container expansível `<details class="req-desc-details">` com summary `"Descrição completa"` para abrigar o texto em português de cada um dos 8 requisitos (V1.2.1 a V1.5.1). Isso reduz a poluição visual, otimiza o uso do espaço vertical e permite leitura sob demanda ou impressão completa.

## 2. Análise Técnica e Arquitetural
- **Frontend (`static/app.js`)**:
  - Ajustar `appendRequirementDescription(container, v, className, isCollapsible = true)`:
    - Quando for renderizado na tabela (`isCollapsible = true`), cria `<details class="req-desc-details">` com `<summary>Descrição completa</summary>` e corpo contendo a descrição completa em português.
    - Quando for no modal "Ver Detalhes", exibe diretamente o texto sem necessidade de clique extra, ou como um bloco destacado.
- **Estilos (`static/theme.css`)**:
  - Estilizar `.req-desc-details`:
    - Summary com estilo discreto, cursor pointer, transição suave e ícone nativo ou Fluent.
    - Estilo em `@media print`: `details.req-desc-details { display: block !important; }` com summary oculto ou indicado e texto sempre visível.
- **Cache-Busting & Versão**:
  - Atualizar `APP_UI_VERSION = "019"` em `app/main.py`.
  - Atualizar assets para `?v=019` em `templates/index.html`.
- **Testes Automatizados (`tests/test_feature_019_collapsible_descriptions.py`)**:
  - Validar que `static/app.js` renderiza `req-desc-details` e `Descrição completa`.
  - Validar que a descrição em português é mantida na íntegra dentro do bloco.
  - Validar a versão 019 no HTML.

## 3. Conformidade com a Constituição do Projeto
- **Princípio I (Domínio Normativo)**: Mantido integralmente. O CSV oficial e o banco SQLite não são alterados.
- **Princípio II (Vereditos)**: Mantido. Sem impactos nas regras de decisão.
- **Princípio IV (Guardrails & Segurança)**: Mantido. Nenhuma chamada de shell ou segredos envolvidos.
- **Acessibilidade (WCAG 2.2 AA)**: Mantida através da semântica nativa de `<details>` e `<summary>`.

## 4. Mapeamento de Mudanças por Arquivo

| Arquivo | Componente | Descrição da Modificação |
| :--- | :--- | :--- |
| `specs/019-collapsible-requirement-descriptions/` | SDD | Documentação completa (spec, plan, tasks). |
| `static/app.js` | UI Logic | Encapsulamento da descrição completa no componente `<details class="req-desc-details">`. |
| `static/theme.css` | Styling | Regras de estilo para `.req-desc-details` e expansão automática em `@media print`. |
| `app/main.py` | Backend | Atualização de `APP_UI_VERSION = "019"`. |
| `templates/index.html` | Template | Atualização de versão e cache-busting `?v=019`. |
| `tests/test_feature_019_collapsible_descriptions.py` | TDD | Testes específicos da Feature 019. |
| `tests/test_ui_presentation.py` e `tests/test_zip_upload_run.py` | Regressão | Atualização de expectativas de versão para `019`. |

