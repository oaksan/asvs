# Implementation Plan: Integração Fim a Fim de Análise Dinâmica (DAST) e Eliminação de Falsos Inconclusivos no ASVS 5.0 (Capítulo V1 - Level 1)

**Branch**: `002-zap-dast-integration` | **Date**: 2026-10-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-zap-dast-integration/spec.md`

## Summary

Corrigir e sincronizar a execução fim a fim do motor de análise dinâmica **OWASP ZAP** (`app/aci/zap_aci.py`, `app/agents/dast_agent.py`, `app/main.py`, `docker-compose.yml`, `templates/index.html` e `static/app.js`) para eliminar os falsos resultados `INCONCLUSIVE` nos 6 requisitos de `V1 L1` que exigem cobertura `["semgrep", "zap"]` (`V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5`, `V1.5.1`). A solução introduz:
1. Endpoint `GET /api/zap/status` e indicador visual em tempo real de conectividade do daemon OWASP ZAP (`ONLINE` / `OFFLINE`) na UI;
2. Ponte de rede container-para-host (`extra_hosts: ["host.docker.internal:host-gateway"]` em `docker-compose.yml`) e resolução automática `localhost -> host.docker.internal` em `zap_aci.py`;
3. Semeadura explícita da URL raiz (`/JSON/core/action/accessUrl/`) seguida de polling assíncrono até 100% do Spider (`/JSON/spider/view/status/`), drenagem completa da fila passiva (`/JSON/pscan/view/recordsToScan/ == 0`) e polling até 100% do Active Scan (`/JSON/ascan/view/status/`) quando `mode == "active"`;
4. Atalho **"Autoavaliar Própria Ferramenta (`app/`)"** pré-configurado para executar SAST + DAST completo quando o daemon ZAP estiver `ONLINE`, além de legenda clara no formulário sobre a cobertura de `Baseline Passivo` (`50.0% PASS` máximo em alvo limpo) vs. `Active Scan` (`87.5% PASS` em alvo limpo).

## Technical Context

**Language/Version**: Python 3.12 + HTML5 / JavaScript (ES2022) / CSS3 (Fluent 2 Design Tokens)

**Primary Dependencies**: `fastapi`, `uvicorn`, `sqlmodel`, `pydantic`, `pandas`, `httpx`, `sse-starlette`, `jinja2` (`autoescape=True`), `pyyaml`, `semgrep` (CLI), OWASP ZAP Daemon REST API (`ghcr.io/zaproxy/zaproxy:stable`), `@fluentui/web-components` & `@fluentui/tokens` (CDN)

**Storage**: SQLite (`asvs.db`) via SQLModel + configuração declarativa em `config/req_tool_mapping.yaml`

**Testing**: `pytest`, `pytest-asyncio`, `httpx` (`MockTransport` / `TestClient`)

**Target Platform**: Linux Server + Docker & Docker Compose (`extra_hosts: ["host.docker.internal:host-gateway"]`)

**Project Type**: Web Application + Multi-Agent Security Verification Pipeline (SAST/DAST)

**Performance Goals**: Verificação de status do daemon ZAP (`GET /api/zap/status`) em `< 2s`; polling assíncrono não-bloqueante do ZAP com intervalos de `0.2s`–`0.5s` respeitando o timeout da etapa

**Constraints**: Preservar intocado o diretório `specs/001-asvs-v1-assessment/`; manter cumprimento estrito do Princípio II da Constituição (`v1.1.0`) — jamais forjar `PASS` se o daemon ZAP estiver offline, mas garantir que, quando online, o ciclo DAST execute até o fim e comprove a evidência positiva

**Scale/Scope**: 8 requisitos avaliáveis (`V1 L1`), 6 requisitos dependentes de `semgrep + zap` (`V1.2.1`–`V1.2.5`, `V1.5.1`), 2 requisitos exclusivos de `semgrep` (`V1.3.1`, `V1.3.2`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio Constitucional (`v1.1.0`) | Status Pré-Pesquisa | Status Pós-Design (Fase 1) | Evidência no Plano / Artefatos |
| :--- | :--- | :--- | :--- |
| **I. Domínio Normativo, Escopo Restrito (V1 L1) e Referências** | ✅ PASS | ✅ PASS | Escopo mantido estritamente nos 8 requisitos `V1 L1` e catálogo de 345 requisitos somente leitura. |
| **II. Modelo de Veredito Baseado em Evidência Positiva e Cobertura Obrigatória por Ferramenta Mapeada** | ✅ PASS | ✅ PASS | O polling completo de `accessUrl` + `spider` + `pscan` + `ascan` garante evidência positiva genuína do OWASP ZAP ([zap-dast-and-status-api.md](./contracts/zap-dast-and-status-api.md)). |
| **III. Arquitetura Multiagente Orientada a ACI (SWE-agent)** | ✅ PASS | ✅ PASS | Toda comunicação com o ZAP permanece encapsulada em `app/aci/zap_aci.py` com `ACIResponse`, truncamento e registro em `ToolCall`. |
| **IV. Segurança da Própria Ferramenta (INEGOCIÁVEL)** | ✅ PASS | ✅ PASS | Guardrails `zap_authorized == True` e `allowlist` (incluindo `host.docker.internal` apenas quando a URL de entrada for `localhost`/`127.0.0.1` autorizada) preservados integralmente. |
| **V. Stack Técnica Padronizada e Design System Fluent 2** | ✅ PASS | ✅ PASS | Badge de status ZAP e textos explicativos estilizados com tokens Fluent 2 e `aria-live="polite"` para acessibilidade WCAG 2.2 AA. |
| **VI. Seeds Normativos e Mapeamento Versionado de Regras** | ✅ PASS | ✅ PASS | Plugins passivos e ativos continuam lidos dinamicamente de `config/req_tool_mapping.yaml`. |

## Design Técnico Detalhado (`002-zap-dast-integration`)

### 1. Infraestrutura Docker (`docker-compose.yml` e `app/aci/zap_aci.py`)

- Em `docker-compose.yml`:
  - Adicionar `extra_hosts: ["host.docker.internal:host-gateway"]` ao serviço `zap` para que o container `asvs-owasp-zap` consiga acessar aplicações rodando em portas locais do host Linux (como `http://localhost:8000`).
- Em `app/aci/zap_aci.py`:
  - Atualizar `DEFAULT_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "host.docker.internal", "vulnerable-app", "web", "testserver"}`.

### 2. Verificação de Conectividade, Resolução Container-Host e Polling DAST (`app/aci/zap_aci.py`)

- **`check_zap_connectivity(*, http_client=None, timeout_sec=3.0) -> dict[str, Any]`**:
  - Consulta `GET {zap_base}/JSON/core/view/version/`.
  - Se `status_code == 200`, extrai `version = resp.json().get("version", "unknown")` e retorna `online=True`.
  - Caso contrário ou em `httpx.HTTPError`, retorna `online=False`, `version=None` e instrução para iniciar o serviço (`docker compose up -d zap`).
- **`resolve_zap_target_url(client, zap_base, target_url) -> tuple[str, bool]`**:
  - Tenta semear `target_url` no ZAP via `GET {zap_base}/JSON/core/action/accessUrl/?url={target_url}&followRedirects=true`.
  - Se `target_url` usar hostname `localhost` ou `127.0.0.1` e a chamada `accessUrl` falhar (`status_code >= 400`), reescreve o hostname para `host.docker.internal` (preservando porta, path e query) e executa `accessUrl` novamente.
  - Retorna `(resolved_url, reachable_by_zap)`.
- **`zap_spider` com Semeadura e Polling**:
  - Verifica `/JSON/core/view/version/`.
  - Chama `resolve_zap_target_url(client, zap_base, url)` para semear a URL raiz.
  - Dispara `/JSON/spider/action/scan/?url={resolved_url}&maxChildren=10&recurse=true` e obtém `scan_id`.
  - Faz polling assíncrono em `/JSON/spider/view/status/?scanId={scan_id}` até `int(status) >= 100` (ou limite de tempo).
  - Coleta URLs de `/JSON/spider/view/results/?scanId={scan_id}` e `/JSON/core/view/urls/?baseurl={resolved_url}`, garantindo `discovered_urls = [url]` (`urls_count >= 1`) caso o alvo tenha respondido.
- **`zap_scan` com Polling de `pscan` e `ascan`**:
  - Verifica `/JSON/core/view/version/` e chama `resolve_zap_target_url(client, zap_base, url)`.
  - Aguarda a drenagem da fila passiva em `/JSON/pscan/view/recordsToScan/` até `int(recordsToScan) == 0`.
  - Quando `mode == "active"`:
    - Dispara `/JSON/ascan/action/scan/?url={resolved_url}&recurse=true`.
    - Se retornar `scan` ID válido, faz polling em `/JSON/ascan/view/status/?scanId={ascan_id}` até `int(status) >= 100`.
  - Coleta alertas em `/JSON/core/view/alerts/?baseurl={resolved_url}` e retorna `zap_daemon_used=True`, `urls_tested >= 1` e `executed_plugins_by_req` populado para os requisitos do modo selecionado.

### 3. Endpoint REST de Status do ZAP (`app/main.py`)

- Adicionar rota `GET /api/zap/status` que invoca `zap_aci.check_zap_connectivity()` e retorna `ZAPDaemonStatus` (`online`, `version`, `zap_base_url`, `allowed_hosts`, `message`).

### 4. Indicador de Conectividade ZAP e Autoavaliação Completa na UI (`templates/index.html` e `static/app.js`)

- Em `templates/index.html`:
  - Adicionar barra/card de status DAST no formulário de Nova Avaliação contendo o badge `#zap-status-badge` (`Verificando ZAP...` / `ONLINE` / `OFFLINE`), texto `#zap-status-text` e botão `#check-zap-btn` (`Verificar Conexão ZAP`).
  - Adicionar nota explicativa sob o seletor `#zap-mode` detalhando que `Baseline Passivo` valida dinamicamente `V1.2.1`, `V1.2.2`, `V1.2.3` (`50% PASS` com SAST), enquanto `Active Scan` valida dinamicamente todos os 6 requisitos dependentes do ZAP (`V1.2.1`–`V1.2.5`, `V1.5.1` → `87.5% PASS` com SAST).
- Em `static/app.js`:
  - Implementar `refreshZapStatus()` consultando `GET /api/zap/status` na inicialização da página e ao clicar em `#check-zap-btn`, salvando o resultado em `state.zapStatus`.
  - Atualizar o handler de `#self-check-btn` ("Autoavaliar Própria Ferramenta (`app/`)"):
    - Definir `#workspace-subpath = "app"`;
    - Definir `#target-url = window.location.origin || "http://localhost:8000"`;
    - Marcar `#zap-authorized = true`;
    - Se `state.zapStatus && state.zapStatus.online`, selecionar `#zap-mode = "active"` (permitindo comprovar todos os 7 requisitos automatizáveis com `PASS`); se o daemon ZAP estiver `OFFLINE`, limpar `#target-url` (ou alertar claramente no banner como subonição Somente SAST com instrução `docker compose up -d zap`).

## Project Structure

### Documentation (this feature)

```text
specs/002-zap-dast-integration/
├── plan.md              # Este arquivo (saída do comando /speckit.plan)
├── research.md          # Decisões técnicas de polling ZAP e rede Docker (Fase 0)
├── data-model.md        # Contratos de dados de status e sessão DAST (Fase 1)
├── quickstart.md        # Guia rápido de validação SAST + DAST (Fase 1)
├── checklists/
│   └── requirements.md  # Checklist de qualidade da especificação (16/16 PASS)
├── contracts/
│   └── zap-dast-and-status-api.md # Contratos REST e ACI da integração ZAP (Fase 1)
└── tasks.md             # Lista de tarefas (a ser gerada por /speckit.tasks)
```

### Source Code (repository root)

```text
docker-compose.yml       # Serviço zap com extra_hosts: ["host.docker.internal:host-gateway"]
app/
├── main.py              # Novo endpoint GET /api/zap/status
├── aci/
│   └── zap_aci.py       # check_zap_connectivity, resolve_zap_target_url, polling spider/pscan/ascan
└── agents/
    └── dast_agent.py    # Propagação detalhada de progresso e status do ciclo DAST
templates/
└── index.html           # Indicador de conectividade OWASP ZAP e legenda de cobertura por modo
static/
└── app.js               # refreshZapStatus() e autoavaliação SAST+DAST inteligente em #self-check-btn
tests/
├── test_aci.py          # Testes unitários de polling ZAP, tradução host.docker.internal e status
└── test_pipeline_integration.py # Testes fim a fim validando 12.5% (SAST), 50.0% (Baseline) e 87.5% (Active)
```

## Complexity Tracking

Nenhuma violação à Constituição (`v1.1.0`).
