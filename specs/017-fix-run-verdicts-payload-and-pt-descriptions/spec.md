# Especificação de Correção (SDD): Descrições em português não aparecem e "undefined — undefined" em Resultado por Verificação

**Feature Branch**: `017-fix-run-verdicts-payload-and-pt-descriptions`
**Created**: 2026-10-22
**Status**: Draft (aguardando Gate 1)
**Input**: *"Crie o SDD para corrigir, pois ele continua vindo com a descrição dos itens do ASVS em inglês"* (captura de tela: descrição em inglês, sem título curto e com a linha `undefined — undefined` sob cada V1.x.y).

---

## 1. Diagnóstico (causa raiz, comprovada no código e no container)

| # | Causa | Evidência |
| :-: | :--- | :--- |
| 1 | **Payload errado alimenta a tela.** O dashboard carrega `GET /api/runs/{id}` (`loadRunDashboard`, `static/app.js`), cujo campo `verdicts` vem de `list_run_verdicts` (`app/main.py`). Esse retorno NÃO contém `section_id`, `section_name`, `req_description`, `friendly_title` nem `description_pt`. | `undefined — undefined` na captura (`v.section_id + " — " + v.section_name`). As Features 015 e 016 alteraram apenas o `reporter_agent` e `/api/requirements/in-scope`, que não são a fonte da tabela. |
| 2 | **Fallback da UI cai no inglês.** Sem `description_pt` no veredito, o JS usa o catálogo em escopo. O catálogo só traz `description_pt` se o processo Python do servidor já carregou o código novo. | O `uvicorn` do container roda **sem `--reload`**; o `docker-compose.yml` monta `.:/workspace` (JS/CSS/YAML atualizam ao vivo, mas o Python só muda após reiniciar o container). O container foi criado às 20:59, antes das Features 015/016. |
| 3 | **Lacuna de testes.** Os testes da 015/016 validaram o `reporter_agent`, o endpoint do catálogo e o texto de `app.js`, mas nenhum validou o contrato do endpoint que a tela realmente consome. | `tests/test_feature_015_*.py`, `tests/test_feature_016_*.py` |

## 2. User Scenarios & Testing

### User Story 1 — Descrição em português em todos os 8 itens na tela (P1)
**Acceptance Scenarios**
1. **Given** uma execução concluída, **When** `GET /api/runs/{id}` é chamado, **Then** cada item de `verdicts` inclui `section_id`, `section_name`, `req_description` (inglês, idêntico ao CSV), `friendly_title` e `description_pt` (campos aditivos).
2. **Given** o dashboard carregado, **When** a tabela "Resultado por Verificação" é renderizada, **Then** cada item de V1.2.1 a V1.5.1 mostra título curto, seção, descrição **em português** e o bloco recolhível "Texto original (ASVS 5.0, inglês)".
3. **Given** o endpoint `GET /api/runs/{id}/verdicts` (rota própria), **When** chamado, **Then** retorna o mesmo conjunto de campos aditivos.

### User Story 2 — Nenhum "undefined" na interface (P1)
1. **Given** um veredito sem `section_id`/`section_name` (payload antigo ou parcial), **When** renderizado, **Then** a UI deriva a seção a partir do `req_id` (ex.: `V1.2.1` → `V1.2`) e do catálogo em escopo; **se ainda ausente, omite a linha** em vez de exibir `undefined`.
2. **Given** qualquer campo textual ausente, **When** renderizado, **Then** nunca aparece a string `undefined` ou `null` na tabela, no modal ou nos filtros por categoria.

### User Story 3 — Código novo sempre em execução (P2)
1. **Given** a documentação de execução (`README.md`), **When** o usuário atualiza o código, **Then** há instrução explícita: `docker compose up --build -d` (ou `docker compose restart web`) é obrigatório após mudanças em Python.
2. **Given** a tela, **When** carregada, **Then** a versão da aplicação (`?v=017`) é exibida discretamente no rodapé, e `GET /api/health` (ou rota equivalente já existente) informa `version`, permitindo conferir se o servidor está na versão esperada.

## 3. Requisitos Funcionais
- **FR-001**: `list_run_verdicts` DEVE incluir, de forma aditiva, `section_id`, `section_name`, `req_description`, `friendly_title` e `description_pt` por veredito, obtidos de `Requirement` e `config/req_tool_mapping.yaml`.
- **FR-002**: `Requirement.req_description` e o CSV normativo NÃO DEVEM ser alterados (Princípio I).
- **FR-003**: A UI NUNCA DEVE renderizar `undefined`/`null` (tabela, modal, filtros).
- **FR-004**: Fallback da UI: veredito → catálogo em escopo → inglês original → "Descrição normativa indisponível".
- **FR-005**: Teste de contrato DEVE exercitar `GET /api/runs/{id}` e `GET /api/runs/{id}/verdicts` com uma execução com 8 vereditos persistidos (semeados no banco de teste, com RBAC), validando os campos da FR-001 para V1.2.1–V1.5.1.
- **FR-006**: README DEVE documentar o rebuild/restart necessário após mudanças em Python; versão exposta conforme US3.2.
- **FR-007**: Sem alteração em vereditos, guardrails ACI/ZAP/IA, schema do banco ou escopo V1 L1 (8 requisitos). Sem segredos em logs.

## 4. Fora de Escopo
Habilitar `uvicorn --reload` em produção; tradução automática por IA; i18n completa.

## 5. Critérios de Sucesso
- **SC-001**: Na tela, 8 de 8 itens com descrição em português e nenhuma ocorrência de `undefined`.
- **SC-002**: Teste de contrato passa para os dois endpoints de vereditos.
- **SC-003**: `pytest -q` sem novas regressões (falhas pré-existentes do Semgrep em `test_aci.py` e `test_pipeline_integration.py` ficam fora do critério).
