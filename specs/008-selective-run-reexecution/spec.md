# Feature Specification: Reexecução Seletiva de Avaliações ASVS com Filtros Multidimensionais

**Feature Code**: `008-selective-run-reexecution`  
**Feature Branch**: `008-selective-run-reexecution`  
**Created**: 2026-10-15  
**Status**: Ready for Review / Gate 1  
**Input**: "selecionar uma execucao completa e poder reexecutar itens especificos dessa execucao completa, selecionando quais quero reexecutar filtrando por Seção, ID, Veredito, Confiança e Ferramenta"

---

## 1. User Scenarios & Testing *(mandatory)*

### User Story 1 - Reexecução Seletiva via API REST com Herança de Estado (Priority: P1 🎯 MVP)

Como analista de segurança ou administrador do sistema,  
Quero selecionar uma execução prévia e reexecutar apenas um subconjunto específico de requisitos normativos do ASVS V1 L1,  
Para que eu possa reavaliar correções pontuais de código ou ajustar ferramentas sem reprocessar testes demorados desnecessariamente, mantendo a integridade do veredito global.

**Why this priority**: É o motor nuclear da funcionalidade. Permite disparar execuções parciais eficientes mantendo rastreabilidade e herança do estado dos requisitos não reexecutados.

**Independent Test**: Pode ser testado de forma hermética via API invocando `POST /api/runs/{run_id}/rerun` com payload `{"req_ids": ["V1.3.1"]}`: apenas o agente de IA é disparado, as outras 7 regras são herdadas da run pai, e a nova run atinge status `COMPLETED` com todos os 8 requisitos consolidados.

**Acceptance Scenarios**:

1. **Given** uma avaliação prévia `#10` finalizada com vereditos para os 8 requisitos V1 L1,  
   **When** o analista submete `POST /api/runs/10/rerun` com payload `{"req_ids": ["V1.2.4", "V1.3.1"]}`,  
   **Then** uma nova execução `#11` é criada com `previous_run_id = 10`, `selected_req_ids_json = '["V1.2.4", "V1.3.1"]'` e status `PENDING`.

2. **Given** a execução seletiva `#11` em andamento,  
   **When** o pipeline orquestrador executa,  
   **Then** o Scoper confina o escopo a `["V1.2.4", "V1.3.1"]`; o SAST executa apenas regras de `V1.2.4`; o DAST executa apenas plugins de `V1.2.4`; e o AI Evaluator inspeciona apenas `V1.3.1`.

3. **Given** a finalização da execução seletiva `#11`,  
   **When** o estágio `VERDICT` consolida os resultados,  
   **Then** os vereditos de `V1.2.4` e `V1.3.1` são recalculados com as novas evidências, enquanto os vereditos dos outros 6 requisitos (`V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.5`, `V1.3.2`, `V1.5.1`) são clonados e herdados da run `#10`.

4. **Given** uma requisição de reexecução seletiva com `req_ids` inválidos (ex.: `["V9.9.9"]` fora do escopo V1 L1),  
   **When** o endpoint é acionado,  
   **Then** a API rejeita com `HTTP 400 Bad Request` detalhando quais requisitos são inválidos.

5. **Given** um usuário comum (`user_bob`) tentando reexecutar uma avaliação pertencente a outro usuário (`user_alice`),  
   **When** ele submete `POST /api/runs/{id_da_alice}/rerun`,  
   **Then** a operação é bloqueada com `HTTP 403 Forbidden` (mitigação mandatória de IDOR / RBAC).

---

### User Story 2 - Filtros Multidimensionais e Modal de Reexecução na Interface Fluent 2 (Priority: P2)

Como usuário na interface Web,  
Quero filtrar os itens de uma execução concluída por Seção, ID, Veredito, Confiança e Ferramenta e selecionar visualmente quais itens reexecutar,  
Para que eu consiga rapidamente identificar requisitos reprovados (`FAIL`) ou inconclusivos (`INCONCLUSIVE`) e disparar sua reexecução com poucos cliques.

**Why this priority**: Torna a reexecução seletiva acessível, rápida e intuitiva para o operador sem manipulação manual de JSON.

**Independent Test**: Pode ser testado acessando o Dashboard da avaliação, clicando em "Reexecução Seletiva...", aplicando os filtros (ex: filtrar por Veredito `FAIL`), clicando em "Selecionar Todos os Filtrados" e disparando a execução acompanhada pelo stepper SSE.

**Acceptance Scenarios**:

1. **Given** uma avaliação selecionada no Dashboard ou Histórico,  
   **When** o usuário clica no botão "Reexecução Seletiva...",  
   **Then** um diálogo modal `<dialog id="selective-rerun-dialog">` é aberto exibindo os 8 requisitos com checkboxes e os filtros multidimensionais.

2. **Given** o modal de reexecução seletiva aberto,  
   **When** o usuário altera o filtro **Veredito** para `FAIL`,  
   **Then** a tabela exibe instantaneamente apenas os requisitos com veredito `FAIL` no DOM.

3. **Given** os filtros aplicados (ex: Seção `V1.2`, Confiança `HIGH`),  
   **When** o usuário clica em "Selecionar Filtrados",  
   **Then** os checkboxes dos itens visíveis são marcados e o contador exibe `"X de 8 requisitos selecionados"`.

4. **Given** nenhum requisito selecionado (0 checkboxes marcados),  
   **When** o usuário observa o botão de confirmação,  
   **Then** o botão "Disparar Reexecução Seletiva" permanece desabilitado (`disabled=true`).

5. **Given** 1 ou mais requisitos selecionados,  
   **When** o usuário clica em "Disparar Reexecução Seletiva",  
   **Then** o modal fecha, a aba 1 (Nova Avaliação & Pipeline) é ativada, o SSE se conecta à nova execução e os logs mostram a reexecução seletiva em andamento.

---

### User Story 3 - Rastreabilidade, Linhagem e Transparência no Relatório (Priority: P3)

Como auditor de conformidade ou gestor de segurança,  
Quero visualizar quais itens de uma avaliação foram reexecutados e quais foram herdados da execução anterior,  
Para que a trilha de auditoria permaneça completamente transparente e auditável.

**Why this priority**: Garante que os relatórios e comparações identifiquem com clareza o histórico evolutivo de cada requisito avaliado.

**Acceptance Scenarios**:

1. **Given** uma avaliação originada de reexecução seletiva,  
   **When** visualizada no Dashboard ou no Relatório HTML exportado,  
   **Then** um badge informativo exibe `"Reexecução Seletiva (X/8) — Baseada na Execução #Y"`.

2. **Given** a tabela de vereditos de uma execução seletiva,  
   **When** o usuário inspeciona cada linha de requisito,  
   **Then** uma tag indica se o veredito foi `Recalculado nesta execução` ou `Herdado da Execução #Y`.

---

## 2. Edge Cases & Guardrails

- **EC-001**: O que acontece se o usuário enviar `req_ids` vazio (`[]`) na API?  
  *Tratamento*: Rejeita com `HTTP 400 Bad Request` ("A lista de requisitos para reexecução seletiva não pode ser vazia. Para reexecução total, envie a lista completa ou omita o campo req_ids").
- **EC-002**: O que acontece se a execução pai (`previous_run_id`) ainda estiver com status `RUNNING` ou `PENDING`?  
  *Tratamento*: A reexecução é bloqueada com `HTTP 400 Bad Request` ("Apenas avaliações concluídas ou finalizadas podem ser selecionadas para reexecução seletiva").
- **EC-003**: O que acontece se a reexecução seletiva incluir apenas requisitos de IA (ex: apenas `V1.3.1`)?  
  *Tratamento*: O pipeline pula os estágios SAST e DAST (`SKIPPED`) com `0s` de duração e avança diretamente para `AI_EVALUATION`, economizando tempo e recursos computacionais.
- **EC-004**: O que acontece se a reexecução seletiva incluir requisitos que exigem DAST (`V1.2.1-V1.2.5`, `V1.5.1`), mas o daemon ZAP estiver offline?  
  *Tratamento*: O sistema respeita o guardrail constitucional: os requisitos dependentes de DAST sem ferramenta ativa recebem status `INCONCLUSIVE` caso não possuam achados estáticos ativos.

---

## 3. Requirements & Architecture Constraints

### Functional Requirements

- **FR-001**: A entidade `Run` DEVE ser enriquecida com `is_selective: bool` (default `False`), `selected_req_ids_json: str | None` e `inherited_from_run_id: int | None`.
- **FR-002**: O endpoint `POST /api/runs/{run_id}/rerun` DEVE aceitar payload opcional `SelectiveRerunRequest(req_ids: list[str] | None = None)`.
- **FR-003**: O `OrchestratorAgent` DEVE filtrar a lista `IN_SCOPE_REQ_IDS` pela interseção com `req_ids` selecionados ao invocar `SASTAgent`, `DASTAgent` e `AIEvaluatorAgent`.
- **FR-004**: No estágio `VERDICT`, o sistema DEVE clonar os vereditos, achados e evidências dos requisitos não selecionados a partir da `previous_run_id`, marcando-os com flag `is_inherited = True`.
- **FR-005**: A interface Fluent 2 DEVE fornecer filtros multidimensionais por:
  - **Seção**: `Todas`, `V1.2 Sanitização & Codificação`, `V1.3 Manipulação Segura de Código`, `V1.5 Comunicação & Cookies`.
  - **ID**: `Todos`, `V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5`, `V1.3.1`, `V1.3.2`, `V1.5.1`.
  - **Veredito**: `Todos`, `PASS`, `FAIL`, `INCONCLUSIVE`, `MANUAL_REQUIRED`.
  - **Confiança**: `Todas`, `HIGH`, `MEDIUM`, `LOW`.
  - **Ferramenta**: `Todas`, `Semgrep (SAST)`, `OWASP ZAP (DAST)`, `AI Evaluator (IA)`.
- **FR-006**: A manipulação da interface no modal DEVE cumprir a política estrita de **Zero innerHTML** (100% `document.createElement` e `textContent`).

---

## 4. Success Criteria *(mandatory)*

- **SC-001**: Usuários conseguem filtrar os 8 requisitos da execução selecionada por qualquer combinação dos 5 filtros (Seção, ID, Veredito, Confiança, Ferramenta) e selecionar itens específicos em menos de 3 cliques.
- **SC-002**: A reexecução de um único requisito (ex: `V1.3.1` ou `V1.3.2`) executa em menos de 10 segundos, pulando estágios de ferramentas não correlacionadas.
- **SC-003**: A nova execução mantém 100% de integridade com todos os 8 vereditos consolidados (itens reexecutados atualizados + itens não selecionados herdados da execução anterior).
- **SC-004**: Usuários não-proprietários são bloqueados com `HTTP 403 Forbidden` ao tentar reexecutar avaliações alheias (0% de tolerância a IDOR).
- **SC-005**: Toda a suíte de testes do projeto (91 testes existentes + novos testes de reexecução seletiva) atinge 100% de aprovação (GREEN).
