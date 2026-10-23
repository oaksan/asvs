# Contratos de Interface: Status do Daemon OWASP ZAP e Ciclo DAST Sincronizado (`002-zap-dast-integration`)

**Feature**: [spec.md](../spec.md)  
**Date**: 2026-10-13

---

## 1. Contrato REST — Diagnóstico do Daemon OWASP ZAP (`app/main.py`)

### `GET /api/zap/status`

Verifica em tempo real se o daemon do OWASP ZAP (`ZAP_BASE_URL`, padrão `http://localhost:8090`) está online e retorna os metadados de conectividade para exibição na UI.

- **Response `200 OK` (Quando o daemon ZAP está ONLINE)**:
  ```json
  {
    "online": true,
    "version": "2.15.0",
    "zap_base_url": "http://localhost:8090",
    "allowed_hosts": [
      "127.0.0.1",
      "host.docker.internal",
      "localhost",
      "testserver",
      "vulnerable-app",
      "web"
    ],
    "message": "OWASP ZAP Daemon ONLINE (v2.15.0) em http://localhost:8090."
  }
  ```

- **Response `200 OK` (Quando o daemon ZAP está OFFLINE)**:
  ```json
  {
    "online": false,
    "version": null,
    "zap_base_url": "http://localhost:8090",
    "allowed_hosts": [
      "127.0.0.1",
      "host.docker.internal",
      "localhost",
      "testserver",
      "vulnerable-app",
      "web"
    ],
    "message": "OWASP ZAP Daemon OFFLINE em http://localhost:8090. Inicie o serviço com: docker compose up -d zap"
  }
  ```

---

## 2. Contratos da Camada ACI (`app/aci/zap_aci.py`)

### 2.1 `check_zap_connectivity`

```python
async def check_zap_connectivity(
    *,
    http_client: httpx.AsyncClient | None = None,
    timeout_sec: float = 3.0,
) -> dict[str, Any]:
    """Query GET {zap_base}/JSON/core/view/version/ and return structured connectivity status."""
```

### 2.2 `resolve_zap_target_url`

```python
async def resolve_zap_target_url(
    client: httpx.AsyncClient,
    zap_base: str,
    target_url: str,
) -> tuple[str, bool]:
    """Seed `target_url` in ZAP via `/JSON/core/action/accessUrl/`.
    
    If `target_url` targets `localhost` or `127.0.0.1` and fails from inside the ZAP container,
    automatically rewrite the hostname to `host.docker.internal` and retry `accessUrl`.
    Returns `(resolved_url, reachable)`.
    """
```

### 2.3 `zap_spider` (Sincronizado com Polling)

1. Valida `validate_dast_target(url, zap_authorized)`.
2. Verifica conectividade em `/JSON/core/view/version/`.
3. Chama `resolve_zap_target_url(client, zap_base, url)` para semear a URL raiz na árvore do ZAP.
4. Inicia `/JSON/spider/action/scan/?url={resolved_url}&maxChildren=10&recurse=true`.
5. Realiza polling em `/JSON/spider/view/status/?scanId={scan_id}` até `int(status) >= 100` (ou `timeout_sec`).
6. Lê `/JSON/spider/view/results/?scanId={scan_id}` e `/JSON/core/view/urls/?baseurl={resolved_url}`, garantindo `urls_count >= 1` quando o alvo respondeu.

### 2.4 `zap_scan` (Sincronizado com `pscan` e `ascan` Polling)

1. Valida `validate_dast_target(url, zap_authorized)` e `mode in {"baseline", "active"}`.
2. Resolve e semeia `resolved_url` via `resolve_zap_target_url`.
3. Faz polling em `/JSON/pscan/view/recordsToScan/` até `int(recordsToScan) == 0` (com timeout de segurança).
4. Se `mode == "active"`:
   - Dispara `/JSON/ascan/action/scan/?url={resolved_url}&recurse=true`.
   - Se um `scanId` numérico for retornado, faz polling em `/JSON/ascan/view/status/?scanId={ascan_id}` até `int(status) >= 100`.
5. Coleta alertas em `/JSON/core/view/alerts/?baseurl={resolved_url}` e retorna:
   - `zap_daemon_used = True`
   - `urls_tested >= 1`
   - `executed_plugins_by_req` contendo os plugins `passive` (em `baseline`) ou `passive + active` (em `active`) para os requisitos em escopo.

---

## 3. Matriz de Vereditos Esperados por Modo de Execução (em Alvo Seguro `app/`)

| `req_id` | `required_tools` | Plugins ZAP (`passive` / `active`) | Somente SAST (`DAST - SKIPPED` ou ZAP Offline) | SAST + ZAP `baseline` (Passivo) | SAST + ZAP `active` (Ativo) |
| :--- | :---: | :--- | :---: | :---: | :---: |
| **V1.2.1** | `["semgrep", "zap"]` | `passive: [10038, 10021]`, `active: [40012, 40014]` | `INCONCLUSIVE` | **`PASS`** (`HIGH`) | **`PASS`** (`HIGH`) |
| **V1.2.2** | `["semgrep", "zap"]` | `passive: [10028]`, `active: [20019, 40012]` | `INCONCLUSIVE` | **`PASS`** (`HIGH`) | **`PASS`** (`HIGH`) |
| **V1.2.3** | `["semgrep", "zap"]` | `passive: [10038]`, `active: [40012]` | `INCONCLUSIVE` | **`PASS`** (`HIGH`) | **`PASS`** (`HIGH`) |
| **V1.2.4** | `["semgrep", "zap"]` | `passive: []`, `active: [40018]` | `INCONCLUSIVE` | `INCONCLUSIVE` | **`PASS`** (`HIGH`) |
| **V1.2.5** | `["semgrep", "zap"]` | `passive: []`, `active: [90020]` | `INCONCLUSIVE` | `INCONCLUSIVE` | **`PASS`** (`HIGH`) |
| **V1.3.1** | `["semgrep"]` | N/A (revisão manual de política WYSIWYG) | `MANUAL_REQUIRED` | `MANUAL_REQUIRED` | `MANUAL_REQUIRED` |
| **V1.3.2** | `["semgrep"]` | N/A | **`PASS`** (`MEDIUM`) | **`PASS`** (`MEDIUM`) | **`PASS`** (`MEDIUM`) |
| **V1.5.1** | `["semgrep", "zap"]` | `passive: []`, `active: [90023]` | `INCONCLUSIVE` | `INCONCLUSIVE` | **`PASS`** (`HIGH`) |
| **Métrica `% PASS`** | — | — | **`12.5% PASS`** (`1/8`) | **`50.0% PASS`** (`4/8`) | **`87.5% PASS`** (`7/8`) |

