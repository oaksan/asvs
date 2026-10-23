# Tasks: Integração Fim a Fim de Análise Dinâmica (DAST) e Eliminação de Falsos Inconclusivos no ASVS 5.0 (Capítulo V1 - Level 1)

**Input**: Design documents from `/specs/002-zap-dast-integration/`
**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md) (required for user stories), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/zap-dast-and-status-api.md](./contracts/zap-dast-and-status-api.md)

**Tests**: Incluídos para validar o ciclo completo de polling do OWASP ZAP (`accessUrl` -> `spider` -> `pscan` -> `ascan`), tradução automática `localhost -> host.docker.internal`, endpoint `GET /api/zap/status` e transição dos vereditos (`12.5% PASS` Somente SAST, `50.0% PASS` Baseline Passivo, `87.5% PASS` Active Scan).

**Organization**: Tarefas agrupadas por User Story (`US1`, `US2`, `US3`) para permitir implementação e validação independentes de cada incremento, preservando intacto o diretório histórico `specs/001-asvs-v1-assessment/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode ser executada em paralelo (arquivos distintos, sem dependências em andamento)
- **[Story]**: Rótulo de rastreabilidade da User Story (`[US1]`, `[US2]`, `[US3]`)
- Caminhos exatos de arquivos incluídos em todas as tarefas

---

## Phase 1: Setup (Infraestrutura Containerizada & Allowlist DAST)

**Purpose**: Configurar a ponte de rede entre o container do OWASP ZAP e o host Linux e atualizar a *allowlist* DAST para permitir a resolução transparente de alvos locais.

- [X] T001 Adicionar `extra_hosts: ["host.docker.internal:host-gateway"]` na definição do serviço `zap` em `docker-compose.yml` para permitir que o container `asvs-owasp-zap` alcance aplicações executando nas portas locais do host Linux
- [X] T002 [P] Atualizar `DEFAULT_ALLOWED_HOSTS` em `app/aci/zap_aci.py` para incluir `"host.docker.internal"` (`{"localhost", "127.0.0.1", "host.docker.internal", "vulnerable-app", "web", "testserver"}`) preservando a validação estrita de `validate_dast_target`

---

## Phase 2: Foundational (Conectividade do Daemon ZAP & Resolução Container-Host)

**Purpose**: Implementar as primitivas fundamentais de verificação de saúde do daemon OWASP ZAP e semeadura/resolução de URLs entre host e container antes da execução das User Stories.

**⚠️ CRITICAL**: Nenhuma User Story pode ser concluída sem estas funções base na camada ACI (`app/aci/zap_aci.py`).

- [X] T003 Implementar `check_zap_connectivity(*, http_client: httpx.AsyncClient | None = None, timeout_sec: float = 3.0) -> dict[str, Any]` em `app/aci/zap_aci.py` consultando `GET {zap_base}/JSON/core/view/version/` e retornando os campos restritos por `data-model.md`: `online` (`bool`, "Obrigatório (`True` quando `/JSON/core/view/version/` responde `200 OK`)"), `version` (`str | None`, "Nullable (ex.: `\"2.15.0\"` quando `online == True`)"), `zap_base_url` (`str`, "Não-vazio (default `\"http://localhost:8090\"`)"), `allowed_hosts` (`list[str]`, "Lista ordenada não-vazia (inclui `\"localhost\"`, `\"127.0.0.1\"`, `\"host.docker.internal\"`, `\"vulnerable-app\"`, `\"web\"`)") e `message` (`str`, "Não-vazio — Mensagem diagnóstica pronta para exibição na interface (incluindo comando `docker compose up -d zap` quando `online == False`)")
- [X] T004 Implementar `resolve_zap_target_url(client: httpx.AsyncClient, zap_base: str, target_url: str) -> tuple[str, bool]` em `app/aci/zap_aci.py` para semear a URL raiz via `GET {zap_base}/JSON/core/action/accessUrl/?url={target_url}&followRedirects=true` e, caso `target_url` utilize hostname `localhost` ou `127.0.0.1` e retorne falha (`status_code >= 400`) de dentro do container ZAP, reescrever automaticamente o hostname para `host.docker.internal` mantendo porta/caminho e repetir a semeadura

**Checkpoint**: Primitivas de conectividade e resolução de URL prontas para uso pelo ciclo DAST e pela API REST.

---

## Phase 3: User Story 1 - Executar Ciclo Completo e Sincronizado de Verificação Dinâmica (DAST) sem Falsos Inconclusivos (Priority: P1) 🎯 MVP

**Goal**: Garantir que o motor dinâmico OWASP ZAP semeie a URL alvo, aguarde até 100% do Spider, drene a fila passiva (`recordsToScan == 0`) e, no modo `active`, aguarde até 100% do Active Scan antes de coletar os alertas, eliminando falsos `INCONCLUSIVE` nos 6 requisitos mapeados para `["semgrep", "zap"]` (`V1.2.1`–`V1.2.5`, `V1.5.1`).

**Independent Test**: Submeter uma avaliação em modo `baseline` (`50.0% PASS` em alvo seguro: `V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.3.2`) e em modo `active` (`87.5% PASS` em alvo seguro: `V1.2.1`–`V1.2.5`, `V1.3.2`, `V1.5.1`, `0 INCONCLUSIVE`, `1 MANUAL_REQUIRED` em `V1.3.1`), confirmando que `zap_spider` e `zap_scan` aguardam a conclusão real dos scans por polling.

### Tests for User Story 1

- [X] T005 [P] [US1] Adicionar testes unitários em `tests/test_aci.py` validando: (a) resolução automática `http://localhost:8000` -> `http://host.docker.internal:8000` em `resolve_zap_target_url` quando `accessUrl` em `localhost` falha no container; (b) polling assíncrono de `zap_spider` até `spider_progress == 100` com `urls_count >= 1`; (c) polling de `pscan/view/recordsToScan/` até `0` e `ascan/view/status/` até `100` em `zap_scan`
- [X] T006 [P] [US1] Adicionar testes de integração fim a fim em `tests/test_pipeline_integration.py` comprovando os 3 cenários normativos da matriz de vereditos: Somente SAST (`12.5% PASS` / `1 PASS`, `6 INCONCLUSIVE`, `1 MANUAL_REQUIRED`), SAST + ZAP `baseline` (`50.0% PASS` / `4 PASS`, `3 INCONCLUSIVE`, `1 MANUAL_REQUIRED`) e SAST + ZAP `active` (`87.5% PASS` / `7 PASS`, `0 INCONCLUSIVE`, `1 MANUAL_REQUIRED`)

### Implementation for User Story 1

- [X] T007 [US1] Atualizar `zap_spider` em `app/aci/zap_aci.py` para chamar `resolve_zap_target_url`, iniciar `/JSON/spider/action/scan/`, realizar polling assíncrono (`asyncio.sleep`) em `/JSON/spider/view/status/?scanId={scan_id}` até `int(status) >= 100`, consultar `/JSON/spider/view/results/` e `/JSON/core/view/urls/?baseurl={resolved_url}` e retornar payload conforme `data-model.md`: `target_url` ("URL original validada contra `allowlist`"), `resolved_target_url` ("URL efetivamente utilizada pelo daemon ZAP (`localhost` ou `host.docker.internal`)"), `zap_daemon_used` ("`True` somente se o daemon ZAP respondeu à API REST"), `spider_scan_id` ("ID retornado por `/JSON/spider/action/scan/`"), `spider_progress` ("`0 <= spider_progress <= 100`"), `urls_discovered` ("Truncado a `MAX_ACI_PAGE_SIZE = 50`") e `urls_count` ("`>= 1` quando `zap_daemon_used == True` e o alvo respondeu a `accessUrl`")
- [X] T008 [US1] Atualizar `zap_scan` em `app/aci/zap_aci.py` para chamar `resolve_zap_target_url`, realizar polling em `/JSON/pscan/view/recordsToScan/` até `int(recordsToScan) == 0`, disparar `/JSON/ascan/action/scan/?url={resolved_url}&recurse=true` com polling em `/JSON/ascan/view/status/?scanId={ascan_id}` até `int(status) >= 100` quando `mode == "active"`, coletar alertas de `/JSON/core/view/alerts/?baseurl={resolved_url}` e retornar payload conforme `data-model.md`: `mode` ("`Literal[\"baseline\", \"active\"]` — `\"baseline\"` (default) ou `\"active\"`"), `zap_daemon_used` ("`True` somente se o daemon ZAP executou a varredura"), `pscan_records_remaining` ("`0` quando a fila passiva drenou completamente"), `ascan_progress` ("`100` quando `mode == \"active\"`, `None` quando `mode == \"baseline\"`"), `urls_tested` ("`>= 1` quando o alvo foi inspecionado pelo ZAP"), `executed_plugins_by_req` ("Mapeia cada `req_id` aos IDs de plugins ZAP efetivamente executados no modo") e `alerts_persisted` ("`>= 0`")
- [X] T009 [US1] Atualizar `DASTAgent.run` em `app/agents/dast_agent.py` para propagar nos eventos SSE (`progress_callback`) e no `summary_message` da etapa DAST a URL resolvida (`resolved_target_url` quando diferente de `target_url`), o progresso do Spider (`spider_progress`), a drenagem da fila passiva e o número de requisitos com plugins ZAP efetivamente executados no modo escolhido (`baseline` vs. `active`)

**Checkpoint**: User Story 1 concluída — o ciclo DAST no OWASP ZAP executa até 100% e elimina os falsos `INCONCLUSIVE` quando o daemon está ativo.

---

## Phase 4: User Story 2 - Diagnosticar Conectividade do Motor Dinâmico em Tempo Real na Interface (Priority: P2)

**Goal**: Exibir em tempo real no painel "Nova Avaliação & Pipeline" se o daemon do OWASP ZAP está `ONLINE` (com versão e URL) ou `OFFLINE` (com comando de inicialização), permitindo revalidar a conexão com um clique e alertando o usuário caso tente iniciar DAST com o motor desligado.

**Independent Test**: Acessar `GET /api/zap/status` e carregar a interface web (`http://localhost:8000`), verificando o badge `#zap-status-badge` (`ONLINE` ou `OFFLINE`) e o botão `#check-zap-btn` sem recarregar a página.

### Tests for User Story 2

- [X] T010 [P] [US2] Adicionar testes em `tests/test_aci.py` e `tests/test_pipeline_integration.py` para `check_zap_connectivity` e para o endpoint `GET /api/zap/status` validando o schema `ZAPDaemonStatus` tanto no cenário `online == True` (`version` preenchida) quanto no cenário `online == False` (`version == None` e instrução `docker compose up -d zap` na `message`)

### Implementation for User Story 2

- [X] T011 [US2] Definir o schema Pydantic `ZAPDaemonStatus` (com restrições de `data-model.md`: `online: bool`, `version: str | None = None`, `zap_base_url: str`, `allowed_hosts: list[str]`, `message: str`) e criar o endpoint `GET /api/zap/status` em `app/main.py` invocando `zap_aci.check_zap_connectivity()`
- [X] T012 [P] [US2] Adicionar o painel de diagnóstico de conectividade DAST no formulário de nova avaliação em `templates/index.html`, contendo o badge `#zap-status-badge` (`aria-live="polite"`), o texto de detalhe `#zap-status-text` e o botão `#check-zap-btn` ("Verificar Conexão ZAP")
- [X] T013 [US2] Implementar `refreshZapStatus()` e `state.zapStatus` em `static/app.js` para consultar `GET /api/zap/status` no carregamento da página e no clique em `#check-zap-btn`, atualizando `#zap-status-badge` e `#zap-status-text` e exibindo alerta explícito caso o avaliador inicie uma avaliação com `#target-url` preenchida enquanto `state.zapStatus.online === false`

**Checkpoint**: User Story 2 concluída — o avaliador tem visibilidade imediata da conectividade do OWASP ZAP antes de disparar qualquer avaliação.

---

## Phase 5: User Story 3 - Executar Autoavaliação Completa (SAST + DAST) com Um Clique e Transparência de Modo (Priority: P2)

**Goal**: Configurar o botão "Autoavaliar Própria Ferramenta (`app/`)" (`#self-check-btn`) para preencher automaticamente a URL da aplicação em execução, marcar a autorização DAST e selecionar o modo `active` quando o daemon ZAP estiver `ONLINE`, além de explicar claramente na interface a diferença de cobertura entre `Baseline Passivo` (`V1.2.1`–`V1.2.3`) e `Active Scan` (`V1.2.1`–`V1.2.5`, `V1.5.1`).

**Independent Test**: Clicar no botão `#self-check-btn` na interface web e verificar que `#workspace-subpath` recebe `"app"`, `#target-url` recebe `window.location.origin`, `#zap-authorized` é marcado, `#zap-mode` seleciona `"active"` (quando o ZAP está `ONLINE`) e a nota de cobertura sob `#zap-mode` detalha os requisitos atendidos em cada modo.

### Implementation for User Story 3

- [X] T014 [P] [US3] Adicionar legenda explicativa sob o seletor `#zap-mode` em `templates/index.html` informando que `Baseline Passivo` valida dinamicamente `V1.2.1`, `V1.2.2` e `V1.2.3` (`50.0% PASS` máximo com SAST), enquanto `Active Scan` adiciona os plugins ativos exigidos por `V1.2.4`, `V1.2.5` e `V1.5.1` (`87.5% PASS` com SAST em alvo seguro)
- [X] T015 [US3] Atualizar o listener de `#self-check-btn` em `static/app.js` para consultar `await refreshZapStatus()` antes do envio, preencher `#workspace-subpath = "app"`, preencher `#target-url = window.location.origin || "http://localhost:8000"`, marcar `#zap-authorized = true` e, quando `state.zapStatus && state.zapStatus.online`, selecionar `#zap-mode = "active"` (ou manter Somente SAST com aviso claro se o daemon ZAP estiver `OFFLINE`)

**Checkpoint**: User Story 3 concluída — autoavaliação SAST + DAST com um clique e transparência de cobertura por modo na UI.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validação final integrada da suíte de testes, autoavaliação de segurança e verificação de integridade dos diretórios de especificação.

- [X] T016 Executar a suíte completa de testes automatizados (`pytest -v`) e o scanner estático Semgrep (`semgrep scan --config config/semgrep_rules app/`) garantindo 100% de aprovação e `0` achados de segurança no código atualizado
- [X] T017 Verificar via `git status` / inspeção de arquivos que todos os artefatos de `specs/001-asvs-v1-assessment/` permaneceram intocados e que `specs/002-zap-dast-integration/` contém a documentação completa da Iteração 002

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Inicia imediatamente (`T001`, `T002`).
- **Foundational (Phase 2)**: Depende da Phase 1 (`T003`, `T004`) — bloqueia o início das User Stories.
- **User Story 1 (Phase 3 - P1 🎯 MVP)**: Depende da Phase 2 (`T005`–`T009`).
- **User Story 2 (Phase 4 - P2)**: Depende da Phase 2 (`T010`–`T013`); pode ser desenvolvida em paralelo à US1 após `T003`.
- **User Story 3 (Phase 5 - P2)**: Depende de `T012` e `T013` da US2 (`T014`, `T015`).
- **Polish (Phase 6)**: Depende da conclusão de todas as User Stories (`T016`, `T017`).

### Parallel Opportunities

- `T001` (`docker-compose.yml`) e `T002` (`app/aci/zap_aci.py`) podem rodar em paralelo.
- `T005` (`tests/test_aci.py`) e `T006` (`tests/test_pipeline_integration.py`) podem rodar em paralelo.
- `T011` (`app/main.py`) e `T012` (`templates/index.html`) podem rodar em paralelo.

---

## Parallel Example: User Story 1 & User Story 2

```bash
# Paralelizar testes de unidade ACI e integração de pipeline (US1):
Task T005: "Adicionar testes unitários de polling ZAP e resolução host.docker.internal em tests/test_aci.py"
Task T006: "Adicionar testes de integração de matriz de vereditos (12.5%, 50.0%, 87.5%) em tests/test_pipeline_integration.py"

# Paralelizar endpoint backend e marcação HTML do diagnóstico ZAP (US2):
Task T011: "Criar schema ZAPDaemonStatus e endpoint GET /api/zap/status em app/main.py"
Task T012: "Adicionar painel de diagnóstico #zap-status-badge e #check-zap-btn em templates/index.html"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Concluir Phase 1 (`T001`–`T002`) e Phase 2 (`T003`–`T004`).
2. Concluir Phase 3 — User Story 1 (`T005`–`T009`).
3. **STOP & VALIDATE**: Validar que o ciclo DAST aguarda Spider (100%), Passive Scan (`0` registros pendentes) e Active Scan (100%), elevando a conformidade de `12.5% PASS` para `50.0% PASS` (`baseline`) e `87.5% PASS` (`active`).

### Incremental Delivery

1. **Iteração Base (`Phase 1 + Phase 2`)**: Ponte `host.docker.internal`, `check_zap_connectivity` e `resolve_zap_target_url`.
2. **Incremento MVP (`Phase 3 - US1`)**: Ciclo DAST sincronizado fim a fim em `zap_aci.py` e `dast_agent.py`.
3. **Incremento Diagnóstico (`Phase 4 - US2`)**: Endpoint `GET /api/zap/status` e indicador visual `ONLINE`/`OFFLINE` em tempo real.
4. **Incremento Autoavaliação (`Phase 5 - US3`)**: Atalho `#self-check-btn` inteligente (`SAST + DAST Active`) e transparência de cobertura por modo.

