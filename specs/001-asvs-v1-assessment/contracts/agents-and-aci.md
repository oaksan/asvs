# Contract: Arquitetura Multiagente, Interfaces ACI e Mapeamento de Regras

**Feature**: `001-asvs-v1-assessment`  
**Date**: 2026-10-13 (Iteração 2)  
**Reference**: Yang et al., *"SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering"* (`docs/Yang_et_al_SWE-agent.pdf`)

---

## 1. Envelope Padrão de Resposta da ACI (`app/aci/`)

Toda função exposta em `workspace_aci.py`, `semgrep_aci.py` e `zap_aci.py` DEVE retornar uma instância do contrato Pydantic `ACIResponse[T]` e registrar automaticamente um `ToolCall` no SQLite (`asvs.db`):

```python
class ACIResponse(BaseModel, Generic[T]):
    ok: bool
    aci: Literal["workspace_aci", "semgrep_aci", "zap_aci"]
    command: str
    summary_message: str  # NUNCA vazia! Ex.: "0 achados para a regra v1-2-4-sqli em 14 arquivos."
    page: int = 1
    page_size: int = 50   # Limite rígido: <= 50 itens por página
    total_items: int = 0
    total_pages: int = 1
    has_next: bool = False
    data: list[T] | T | None = None
    corrective_hint: str | None = None  # Preenchido quando ok=False (guardrail/erro)
```

---

## 2. Catálogo de Comandos por Módulo ACI

### 2.1 `app/aci/workspace_aci.py`

Confinado estritamente ao diretório raiz permitido (`WORKSPACE_ROOT` ou diretório de extração segura de `.zip`).

| Comando | Assinatura | Comportamento e Guardrails |
| :--- | :--- | :--- |
| `scan_workspace_surface` | `(source_path: str) -> ACIResponse[SurfaceSummary]` | Inventaria arquivos por extensão/linguagem e detecta superfícies relevantes para V1 L1 usando expressões regulares de código/importação real (sem auto-colisão com literais internos de `workspace_aci.py`). Bloqueia `..` e symlinks externos. |
| `list_files` | `(source_path: str, pattern: str = "*", page: int = 1) -> ACIResponse[str]` | Lista até 50 caminhos relativos por página. Se 0 arquivos corresponderem, retorna `"0 arquivos encontrados para o padrão X"`. |
| `read_snippet` | `(source_path: str, rel_file: str, start_line: int, end_line: int) -> ACIResponse[CodeExcerpt]` | Lê no máximo 30 linhas numeradas ao redor do ponto de interesse para inspeção de evidência. |

### 2.2 `app/aci/semgrep_aci.py`

Executa o Semgrep CLI usando `subprocess.run([...], shell=False, capture_output=True, text=True, timeout=...)`.

| Comando | Assinatura | Comportamento e Guardrails |
| :--- | :--- | :--- |
| `run_rules` | `(run_id: int, req_id: str, source_path: str) -> ACIResponse[SemgrepRunSummary]` | Resolve as regras mapeadas para `req_id` em `config/req_tool_mapping.yaml`, valida o caminho, executa `semgrep scan --config <rule_path> --sarif` como lista de argumentos (`shell=False`), persiste achados brutos/normalizados e retorna resumo explícito: `"N achados para M regras de {req_id} em K arquivos inspecionados"`. |
| `list_findings` | `(run_id: int, req_id: str, page: int = 1) -> ACIResponse[FindingSummary]` | Retorna até 50 achados SAST paginados para o `req_id`. Se 0, retorna `"0 achados SAST para {req_id} nos K arquivos verificados"`. |
| `show_evidence` | `(evidence_id: int) -> ACIResponse[EvidenceDetail]` | Retorna `arquivo:linha` e o trecho de código truncado (máx. 20 linhas) para um achado específico. |

### 2.3 `app/aci/zap_aci.py`

Comunica-se via `httpx.AsyncClient` com o daemon OWASP ZAP e valida obrigatoriamente `zap_authorized == True` e `target_url` na `allowlist`.

| Comando | Assinatura | Comportamento e Guardrails |
| :--- | :--- | :--- |
| `zap_spider` | `(run_id: int, url: str) -> ACIResponse[ZapSpiderSummary]` | Valida `url` na `allowlist`; verifica conectividade real com a API REST do daemon OWASP ZAP (`/JSON/spider/action/scan/`); retorna `zap_daemon_used: bool` e a contagem de URLs descobertas pelo ZAP. |
| `zap_scan` | `(run_id: int, url: str, mode: Literal["baseline", "active"], req_id: str \| None = None) -> ACIResponse[ZapScanSummary]` | Verifica conectividade com o daemon ZAP (`zap_daemon_used`). Se o daemon ZAP estiver offline, retorna `executed_plugins_by_req = {}` e `urls_tested = 0` com mensagem explícita de indisponibilidade do daemon ZAP (sem forjar cobertura via fallback HTTP). Quando o daemon ZAP está online: no modo `"baseline"` (default), executa apenas os plugins `passive` mapeados; no modo `"active"`, executa plugins `passive` + `active` mapeados para `V1 L1`. |
| `zap_alerts` | `(run_id: int, req_id: str, page: int = 1) -> ACIResponse[FindingSummary]` | Filtra alertas do ZAP pelos `plugin_id`s mapeados para `req_id`, pagina em blocos de até 50 itens e retorna `"0 alertas ZAP para os plugins [X, Y] de {req_id} em N URLs testadas"` quando limpo. |

---

## 3. Contratos Pydantic dos 7 Agentes (`app/agents/`)

| Agente | Módulo | Input Model (Pydantic) | Output Model (Pydantic) | Responsabilidade e Uso de ACI |
| :--- | :--- | :--- | :--- | :--- |
| **1. Orchestrator** | `app/agents/orchestrator.py` | `OrchestratorInput(run_id: int)` | `OrchestratorOutput(run_id: int, final_status: str, stages_completed: list[str])` | Coordena a máquina de estados da `Run`, despacha `Scoper`, executa `SAST Agent` e `DAST Agent` (em paralelo via `asyncio.gather` quando DAST habilitado), aciona `Triage`, `Verdict` e `Reporter`, gerencia cancelamento/timeouts e publica eventos SSE. |
| **2. Scoper** | `app/agents/scoper.py` | `ScoperInput(run_id: int, source_path: str, target_url: str \| None)` | `ScoperOutput(total_files: int, languages: dict[str, int], surfaces_by_req: dict[str, ReqSurfaceInfo], dast_enabled: bool)` | Usa `workspace_aci.scan_workspace_surface` para identificar quais dos 8 requisitos possuem superfície de código verificável (ex.: templates HTML para `V1.2.1`, SQL para `V1.2.4`, XML para `V1.5.1`). |
| **3. SAST Agent** | `app/agents/sast_agent.py` | `SASTAgentInput(run_id: int, source_path: str, req_ids: list[str])` | `SASTAgentOutput(executed_rules_by_req: dict[str, list[str]], scanned_files_by_req: dict[str, int], findings_count_by_req: dict[str, int])` | Invoca `semgrep_aci.run_rules` e `semgrep_aci.list_findings` para cada um dos 8 requisitos V1 L1, colapsando observações antigas do histórico. |
| **4. DAST Agent** | `app/agents/dast_agent.py` | `DASTAgentInput(run_id: int, target_url: str, zap_authorized: bool, zap_mode: Literal["baseline", "active"], req_ids: list[str])` | `DASTAgentOutput(dast_executed: bool, urls_crawled: int, executed_plugins_by_req: dict[str, list[str]], alerts_count_by_req: dict[str, int])` | Invoca `zap_aci.zap_spider`, `zap_aci.zap_scan` e `zap_aci.zap_alerts`, reportando `dast_executed = True` somente quando o daemon ZAP respondeu e executou plugins sobre `urls_crawled > 0`. |
| **5. Triage/Correlation Agent** | `app/agents/triage_agent.py` | `TriageAgentInput(run_id: int)` | `TriageAgentOutput(total_raw: int, deduplicated_count: int, correlated_reqs: list[str])` | Deduplica achados por `fingerprint`, correlaciona achados SAST e DAST que apontam para o mesmo requisito (aumentando `confidence` para `"HIGH"` quando ambos concordam) e preserva marcações de falso positivo existentes em reexecuções. |
| **6. Verdict Agent** | `app/agents/verdict_agent.py` | `VerdictAgentInput(run_id: int, scoper_output: ScoperOutput, sast_output: SASTAgentOutput, dast_output: DASTAgentOutput \| None)` | `VerdictAgentOutput(verdicts: list[VerdictRecordSchema], pass_percentage: float, counts: dict[str, int])` | Carrega `required_tools` de `config/req_tool_mapping.yaml` para cada `req_id` e invoca `evaluate_requirement_verdict` (`app/verdict.py`), exigindo evidência positiva de **todas** as ferramentas mapeadas (`semgrep` + `zap` para `V1.2.1`–`V1.2.5`, `V1.5.1`; apenas `semgrep` para `V1.3.2` e `V1.3.1`). |
| **7. Reporter Agent** | `app/agents/reporter_agent.py` | `ReporterAgentInput(run_id: int)` | `ReporterAgentOutput(run_id: int, summary_metrics: dict, section_breakdown: dict[str, dict[str, int]], export_ready: bool)` | Consolida os dados para o dashboard Fluent 2, calcula agregações por seção (`V1.2`, `V1.3`, `V1.5`) e gera os artefatos de exportação JSON e HTML estático. |
