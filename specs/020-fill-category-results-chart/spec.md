# Especificação de Correção (SDD): Preenchimento Correto do Gráfico "Resultados por Categoria"

**Feature Branch**: `020-fill-category-results-chart`
**Created**: 2026-10-22
**Status**: Draft (aguardando aprovação para execução)
**Input**: *"crie um sdd para remover para preencher corretamente o Resultados por Categoria, vide print"* (imagem anexada exibindo donut com 100% / 8 aprovados, mas as três barras horizontais de V1.2, V1.3 e V1.5 em "Resultados por Categoria" totalmente cinzas/vazias).

---

## 1. Diagnóstico e Causa Raiz

### Problema Observado na Imagem:
- No painel da esquerda (**Distribuição dos Resultados**), o donut exibe corretamente 100% de conformidade com 8/8 aprovados.
- No painel da direita (**Resultados por Categoria**), as barras horizontais das três seções avaliadas aparecem totalmente cinzas e vazias:
  - `V1.2 Injection (5)`: barra 100% cinza.
  - `V1.3 Sanitization (2)`: barra 100% cinza.
  - `V1.5 Deserialization (1)`: barra 100% cinza.

### Causa Raiz Comprovada:
1. **Omissão no Endpoint Backend (`GET /api/runs/{run_id}`)**:
   - O dashboard carrega os dados chamando `GET /api/runs/{run_id}` (`loadRunDashboard` em `static/app.js`).
   - Na função `get_run_details` em `app/main.py`, o objeto JSON retornado inclui `metrics`, `verdicts` e `findings`, mas **NÃO inclui `section_breakdown`**.
2. **Dependência Quebrada no Frontend (`static/app.js`)**:
   - O renderizador do gráfico (`renderCharts` em `static/app.js`, linha 1659) executa:
     ```javascript
     const secBreakdown = report.section_breakdown || {};
     ```
   - Como `report.section_breakdown` é `undefined`, `secBreakdown` torna-se um objeto vazio `{}`.
   - Os contadores de cada veredito (`counts["PASS"]`, etc.) resultam em zero.
   - Consequentemente, apenas o retângulo de fundo cinza (`colors.stroke`) é desenhado, sem nenhum retângulo colorido correspondente aos vereditos.

---

## 2. Solução Proposta

1. **Backend (`app/main.py`)**:
   - Incluir o campo `section_breakdown` no retorno de `GET /api/runs/{run_id}`, invocando `build_section_breakdown(verdicts)` (função já existente e testada em `app/agents/reporter_agent.py`).
2. **Frontend Defensivo (`static/app.js`)**:
   - Caso `report.section_breakdown` venha ausente ou vazio, derivar automaticamente a quebra por seção a partir da lista `report.verdicts`.
   - Adicionar rótulos textuais de progresso nas barras (ex.: contadores de aprovados, como `5/5`, `2/2`, `1/1` ou tooltip claro) para enriquecer a experiência do usuário.
3. **Cache-Busting & Versão**:
   - Atualizar a versão para `?v=020` em `app/main.py` e `templates/index.html`.
4. **Testes Automatizados de Contrato**:
   - Teste validando que `GET /api/runs/{run_id}` retorna `section_breakdown` preenchido corretamente para todas as seções (`V1.2`, `V1.3`, `V1.5`).
   - Teste validando que o frontend calcula o fallback caso `section_breakdown` não seja fornecido.

---

## 3. User Scenarios & Acceptance Criteria

### User Story 1 — Visualização Clara dos Resultados por Categoria (P1)
Como usuário visualizando o dashboard de uma avaliação concluída,  
quero ver as barras horizontais de "Resultados por Categoria" preenchidas com as cores correspondentes aos vereditos obtidos,  
para que eu identifique visualmente o nível de conformidade de cada categoria do ASVS (V1.2, V1.3 e V1.5).

#### Acceptance Scenarios:
1. **Given** uma avaliação onde todos os 8 requisitos foram aprovados (`PASS`),  
   **When** o dashboard é carregado na tela,  
   **Then** a barra de `V1.2 Injection (5)` é preenchida 100% em verde (`5 / 5`).
2. **Given** a mesma avaliação,  
   **When** inspecionadas as barras de `V1.3 Sanitization (2)` e `V1.5 Deserialization (1)`,  
   **Then** ambas são preenchidas 100% em verde (`2 / 2` e `1 / 1`).
3. **Given** uma avaliação com vereditos mistos (ex: falha em V1.2.4),  
   **When** renderizada a barra de `V1.2`,  
   **Then** ela exibe a proporção exata em verde (4/5) e em vermelho (1/5).

---

## 4. Requisitos Funcionais

- **FR-001**: O endpoint `GET /api/runs/{run_id}` DEVE retornar o campo `section_breakdown` estruturado por seção (`V1.2`, `V1.3`, `V1.5`) com a contagem de cada status (`PASS`, `FAIL`, `INCONCLUSIVE`, `MANUAL_REQUIRED`).
- **FR-002**: A função `renderCharts` em `static/app.js` DEVE renderizar os segmentos preenchidos nas barras SVG com base em `section_breakdown` (e com cálculo de fallback a partir de `report.verdicts` caso ausente).
- **FR-003**: A integridade das regras constitucionais (Princípios I a IV) DEVE ser preservada: sem alteração de banco, sem quebra de guardrails.
- **FR-004**: Versão atualizada para `020` com bump no template HTML e testes.

---

## 5. Critérios de Sucesso

- **SC-001**: As três barras de "Resultados por Categoria" aparecem devidamente coloridas e preenchidas de acordo com os vereditos da avaliação.
- **SC-002**: O endpoint `GET /api/runs/{run_id}` contém o nó `section_breakdown` com contagens exatas.
- **SC-003**: Todos os testes da suíte automatizada passam com sucesso.

