# Phase 0 Research: Integração Fim a Fim de Análise Dinâmica (OWASP ZAP) e Eliminação de Falsos Inconclusivos (`002-zap-dast-integration`)

**Feature**: [spec.md](./spec.md)  
**Date**: 2026-10-13  
**Constitution Reference**: `.specify/memory/constitution.md` (`v1.1.0`)

---

## 1. Diagnóstico de Conectividade Pré-Execução do Daemon OWASP ZAP

- **Decision**: Implementar a função assíncrona `check_zap_connectivity(http_client, timeout_sec=3.0)` em `app/aci/zap_aci.py` consultando `GET {zap_base}/JSON/core/view/version/` e expô-la via `GET /api/zap/status` em `app/main.py`, consumida pelo badge de saúde DAST em `templates/index.html` / `static/app.js`.
- **Rationale**: Na Iteração anterior, o usuário só descobria que o daemon OWASP ZAP (`http://localhost:8090`) estava desligado após iniciar o pipeline e receber `6 INCONCLUSIVE`. Exibir o estado em tempo real (`ONLINE v2.x` vs. `OFFLINE`) na tela de configuração permite ao avaliador verificar (ou subir com `docker compose up -d zap`) o motor dinâmico antes de disparar a execução.
- **Alternatives considered**:
  - *Tentar iniciar o container Docker automaticamente de dentro do backend FastAPI via `subprocess`*: Descartado como mecanismo único porque viola o princípio de privilégio mínimo caso o backend rode sem acesso ao socket Docker (`/var/run/docker.sock`) e conflita com ambientes onde o ZAP já está em outro host/container.

---

## 2. Resolução Transparente de Alvos `localhost` entre Host Linux e Container OWASP ZAP

- **Decision**:
  1. Configurar `extra_hosts: ["host.docker.internal:host-gateway"]` no serviço `zap` em `docker-compose.yml` e incluir `"host.docker.internal"` em `DEFAULT_ALLOWED_HOSTS` em `app/aci/zap_aci.py`.
  2. Implementar `resolve_zap_target_url(client, zap_base, target_url)` em `app/aci/zap_aci.py`: quando `target_url` tiver hostname `localhost` ou `127.0.0.1`, a ACI chama `GET {zap_base}/JSON/core/action/accessUrl/?url={target_url}&followRedirects=true`. Se o ZAP retornar erro HTTP/500 (porque `localhost` dentro do container ZAP aponta para o próprio container e não para o host) ou 0 nós em `/JSON/core/view/urls/`, a ACI reescreve automaticamente o host da URL para `host.docker.internal` (mantendo esquema, porta e caminho, ex.: `http://host.docker.internal:8000`) e repete `accessUrl`.
- **Rationale**: Em Linux, containers Docker isolados em bridge network não resolvem o `localhost` da máquina hospedeira sem `host-gateway`. Traduzir transparentemente `localhost -> host.docker.internal` dentro de `zap_aci.py` permite que o usuário digite `http://localhost:8000` (ou use o botão de Autoavaliação) no navegador enquanto o container `asvs-owasp-zap` alcança a aplicação na máquina hospedeira sem erro de conexão recusada.
- **Alternatives considered**:
  - *Usar `network_mode: "host"` no container ZAP*: Descartado por reduzir o isolamento de rede do container ZAP e apresentar comportamentos inconsistentes em Docker Desktop (macOS/Windows/WSL2).

---

## 3. Semeadura Explícita (`accessUrl`) e Sincronização por Polling (`spider`, `pscan`, `ascan`)

- **Decision**: Estruturar o fluxo DAST em `app/aci/zap_aci.py` nas seguintes fases determinísticas com polling assíncrono (`asyncio.sleep`):
  1. **Semeadura (`accessUrl`)**: `GET {zap_base}/JSON/core/action/accessUrl/?url={resolved_url}&followRedirects=true` para registrar a URL raiz na árvore de Sites do ZAP mesmo antes do Spider iniciar.
  2. **Spider com Polling**:
     - `GET {zap_base}/JSON/spider/action/scan/?url={resolved_url}&maxChildren=10&recurse=true` → obtém `scan_id`.
     - Loop de polling (`interval = 0.25s`, `max_wait = timeout_sec`) em `GET {zap_base}/JSON/spider/view/status/?scanId={scan_id}` até `int(status) >= 100`.
     - Coleta de URLs combinando `/JSON/spider/view/results/?scanId={scan_id}` e `/JSON/core/view/urls/?baseurl={resolved_url}`, garantindo `[resolved_url]` como mínimo quando o alvo foi acessado com sucesso (`urls_count >= 1`).
  3. **Passive Scan Drain (`pscan`)**:
     - Loop de polling (`interval = 0.2s`, `max_wait = 5.0s`) em `GET {zap_base}/JSON/pscan/view/recordsToScan/` até `int(recordsToScan) == 0`, garantindo que as regras passivas (`10038`, `10021`, `10028`) terminem de inspecionar todas as respostas HTTP do Spider.
  4. **Active Scan com Polling (`mode == "active"`)**:
     - `GET {zap_base}/JSON/ascan/action/scan/?url={resolved_url}&recurse=true` → obtém `ascan_id`.
     - Loop de polling (`interval = 0.25s`, `max_wait = timeout_sec`) em `GET {zap_base}/JSON/ascan/view/status/?scanId={ascan_id}` até `int(status) >= 100`.
     - Caso a API do ZAP retorne código HTTP 200 ou conclua o scan sobre os nós da árvore semeada, todos os plugins `passive` + `active` mapeados para `V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5` e `V1.5.1` são registrados em `executed_plugins_by_req`.
  5. **Coleta e Mapeamento de Alertas**:
     - Consulta `GET {zap_base}/JSON/core/view/alerts/?baseurl={resolved_url}` normalizando a URL de volta para a URL original nos registros `Finding` / `Evidence` para exibição limpa ao usuário.
- **Rationale**: A API REST do OWASP ZAP dispara scans em threads Java de background e retorna imediatamente `{"scan": "0"}`. Sem aguardar `status >= 100` e `recordsToScan == 0`, a leitura imediata de resultados/alertas ocorre antes do tráfego HTTP ser analisado, gerando `0 URLs` ou `0 plugins` e falsos vereditos `INCONCLUSIVE`.
- **Alternatives considered**:
  - *Usar `zap-baseline.py` / `zap-full-scan.py` via `docker exec`*: Descartado porque reinicia o processo ZAP a cada chamada (adicionando 30–60s de overhead por execução) em vez de reutilizar o daemon persistente já ativo.

---

## 4. Autoavaliação Completa com Um Clique (`#self-check-btn`) e Transparência de Modos

- **Decision**:
  - Ao clicar em **"Autoavaliar Própria Ferramenta (`app/`)"** (`#self-check-btn` em `static/app.js`), o controlador frontend:
    1. Define `#workspace-subpath = "app"`;
    2. Preenche `#target-url` com `window.location.origin || "http://localhost:8000"`;
    3. Marca `#zap-authorized = true`;
    4. Se o status do daemon ZAP (`state.zapStatus.online`) estiver `true`, seleciona `#zap-mode = "active"` (para que os 6 requisitos dependentes de ZAP, inclusive `V1.2.4`, `V1.2.5` e `V1.5.1`, executem seus plugins ativos e recebam `PASS`); caso o daemon ZAP esteja `OFFLINE`, avisa claramente no banner antes/durante a submissão.
- **Rationale**: O usuário relatou que, ao testar a própria ferramenta na UI, o ZAP era ignorado ou retornava múltiplos `INCONCLUSIVE`. Automatizar a configuração completa de SAST + DAST no botão de autoavaliação elimina erros manuais de preenchimento no formulário.
- **Alternatives considered**:
  - *Manter `zap-mode = "baseline"` fixo no botão de autoavaliação*: Descartado porque em modo `baseline` os requisitos `V1.2.4`, `V1.2.5` e `V1.5.1` (que não possuem plugins passivos no ZAP) continuariam recebendo `INCONCLUSIVE`.

