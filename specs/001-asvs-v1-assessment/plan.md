# Implementation Plan: Pipeline e Dashboard Web de Autoavaliação OWASP ASVS 5.0 (Capítulo V1 - Level 1)

**Branch**: `001-asvs-v1-assessment` | **Date**: 2026-10-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-asvs-v1-assessment/spec.md` (Iteração 2 — Cobertura Obrigatória por Ferramenta Mapeada e Precisão DAST/OWASP ZAP)

## Summary

Construir e refinar a aplicação web **ASVS-Self-Assesment-Tool** para executar e exibir o pipeline multiagente de avaliação automatizada do padrão **OWASP ASVS 5.0**, restrito exclusivamente ao **Capítulo V1 (Encoding and Sanitization), Level 1** (8 requisitos: `V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5`, `V1.3.1`, `V1.3.2`, `V1.5.1`), mantendo os 345 requisitos (`V1`–`V17`) catalogados para consulta somente leitura. Nesta **Iteração 2**, o motor de veredito (`app/verdict.py`), o `VerdictAgent`, o `zap_aci`, o `workspace_aci` e o controlador frontend (`static/app.js`) são atualizados para garantir que requisitos mapeados para `["semgrep", "zap"]` em `config/req_tool_mapping.yaml` recebam obrigatoriamente `INCONCLUSIVE` (e nunca `PASS`) quando a etapa DAST (OWASP ZAP) não for executada, quando o daemon ZAP estiver offline ou quando os plugins ZAP requeridos pelo requisito não tiverem sido executados.

## Technical Context

**Language/Version**: Python 3.12 + HTML5 / JavaScript (ES2022) / CSS3 (Fluent 2 Design Tokens)

**Primary Dependencies**: `fastapi`, `uvicorn`, `sqlmodel`, `pydantic`, `pandas`, `httpx`, `python-owasp-zap-v2.4` (ou chamadas REST diretas via `httpx`), `sse-starlette`, `jinja2` (`autoescape=True`), `pyyaml`, `python-multipart`, `semgrep` (CLI), `@fluentui/web-components` & `@fluentui/tokens` (CDN)

**Storage**: SQLite (`asvs.db`) gerenciado via SQLModel + artefatos versionados em `config/` e `docs/`

**Testing**: `pytest`, `pytest-asyncio`, `httpx` (`TestClient` / `AsyncClient`), mais alvo vulnerável dedicado (`tests/vulnerable_app/`)

**Target Platform**: Linux Server + Containers Docker (`docker-compose` orquestrando serviço `zap` em modo daemon e aplicação web)

**Project Type**: Web Application + Multi-Agent Security Verification Pipeline (SAST/DAST)

**Performance Goals**: Transições de etapa transmitidas via SSE em `< 2s`; cancelamento de execução em `< 5s`; consultas paginadas de achados e catálogo em `< 200ms`

**Constraints**: Escopo estrito em `V1` e `L = 1` (8 requisitos); máximo de 50 achados por página na ACI; zero execução de shell com input do usuário (`shell=False`); modo ativo do ZAP desabilitado por padrão e condicionado a checkbox de autorização + `allowlist`; exigência de evidência positiva de **todas** as ferramentas mapeadas (`required_tools`) para emissão de `PASS`; conformidade da própria ferramenta com o ASVS V1 L1 e WCAG 2.2 AA

**Scale/Scope**: 345 requisitos catalogados (`V1`–`V17`), 8 requisitos avaliados (`V1 L1`), 7 agentes com contratos Pydantic, 3 módulos ACI, pacotes de código de até 100 MB

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio Constitucional (`v1.1.0`) | Status Pré-Pesquisa | Status Pós-Design (Fase 1) | Evidência no Plano / Artefatos |
| :--- | :--- | :--- | :--- |
| **I. Domínio Normativo, Escopo Restrito (V1 L1) e Referências** | ✅ PASS | ✅ PASS | Seed dos 345 requisitos com `in_scope = (chapter_id == 'V1' and level == 1)` (8 requisitos); tabela explícita `docs/mapping_4_0_to_5_0.md` documentada em [research.md](./research.md). |
| **II. Modelo de Veredito Baseado em Evidência Positiva e Cobertura Obrigatória por Ferramenta Mapeada** | ✅ PASS | ✅ PASS | `RequirementVerdictInput.required_tools` em `app/verdict.py` exige `has_sast_positive` **E** `has_dast_positive` quando `"zap" in required_tools`; caso DAST seja `SKIPPED`, daemon ZAP inacessível ou plugins ZAP não executados, retorna `INCONCLUSIVE` (ou `FAIL` se houver achados ativos). |
| **III. Arquitetura Multiagente Orientada a ACI (SWE-agent)** | ✅ PASS | ✅ PASS | 7 agentes em `app/agents/` e 3 ACIs em `app/aci/` com paginação (`<= 50`), feedback explícito para 0 achados, colapso de histórico e estado em `asvs.db` ([agents-and-aci.md](./contracts/agents-and-aci.md)). |
| **IV. Segurança da Própria Ferramenta (INEGOCIÁVEL)** | ✅ PASS | ✅ PASS | Guardrails em `POST /api/runs` e nas ACIs: checkbox + allowlist para ZAP, modo passivo default, `shell=False` com lista de argumentos, `autoescape=True` no Jinja2 e queries SQLModel parametrizadas. |
| **V. Stack Técnica Padronizada e Design System Fluent 2** | ✅ PASS | ✅ PASS | Python 3.12, FastAPI, SQLModel, SQLite, SSE, Semgrep CLI, ZAP Docker (`docker-compose.yml`), HTML5 + Fluent 2 (`microsoft/fluentui` em `skills.sh`), gráficos SVG com tokens Fluent, WCAG 2.2 AA. |
| **VI. Seeds Normativos e Mapeamento Versionado de Regras** | ✅ PASS | ✅ PASS | Seed automático em `app/database.py` na inicialização se vazio; `tools`, regras Semgrep e plugins ZAP parametrizados em `config/req_tool_mapping.yaml` e `config/semgrep_rules/`. |

## Design Técnico — Iteração 2 (Precisão DAST/ZAP & Veredito por Ferramenta Mapeada)

### 1. Motor Puro de Veredito (`app/verdict.py`)

- **Contrato `RequirementVerdictInput`**:
  - Adicionar o campo `required_tools: list[str] = field(default_factory=lambda: ["semgrep"])`.
- **Regra em `evaluate_requirement_verdict(inp: RequirementVerdictInput)`**:
  1. Se `inp.active_findings_count > 0` → retorna `VerdictStatus.FAIL` (qualquer achado ativo em SAST ou DAST reprova imediatamente o requisito).
  2. Se `inp.manual_verification_needed` ou (`inp.req_id == "V1.3.1"` sem superfície/indicador positivo confirmado) → retorna `VerdictStatus.MANUAL_REQUIRED`.
  3. **Verificação de Ferramentas Obrigatórias (`required_tools`)**:
     - `requires_sast = "semgrep" in inp.required_tools`
     - `requires_dast = "zap" in inp.required_tools`
     - Se `requires_sast and not has_sast_positive` → retorna `VerdictStatus.INCONCLUSIVE` explicando que a cobertura estática (Semgrep) ou superfície relevante não foi comprovada.
     - Se `requires_dast and not has_dast_positive` → retorna `VerdictStatus.INCONCLUSIVE` (mesmo que `has_sast_positive == True`!), preservando a evidência positiva parcial do Semgrep em `positive_evidence`, mas informando na `rationale` que o requisito mapeia `tools: ["semgrep", "zap"]` e exige validação dinâmica pelo OWASP ZAP (não executada por `DAST - SKIPPED`, daemon ZAP inacessível ou ausência de plugins ZAP executados no modo selecionado).
  4. Somente quando todas as ferramentas exigidas em `required_tools` apresentarem evidência positiva (`(not requires_sast or has_sast_positive) and (not requires_dast or has_dast_positive)`) → retorna `VerdictStatus.PASS`.

### 2. Agente de Veredito (`app/agents/verdict_agent.py`)

- Em `VerdictAgent.run` e em `recalculate_single_requirement_verdict`:
  - Ler `req_cfg = load_req_tool_mapping().get("requirements", {}).get(req_id, {})`.
  - Extrair `required_tools = list(req_cfg.get("tools", ["semgrep"]))`.
  - Passar `required_tools=required_tools` ao instanciar `RequirementVerdictInput`.

### 3. Conectividade Real do OWASP ZAP e Execução de Plugins (`app/aci/zap_aci.py` e `app/agents/dast_agent.py`)

- **`app/aci/zap_aci.py`**:
  - Em `zap_scan`: verificar se o daemon REST do OWASP ZAP (`ZAP_BASE_URL`) respondeu efetivamente às chamadas da API (`/JSON/...`, `zap_daemon_used == True`).
  - Se `zap_daemon_used == False` (daemon ZAP desligado/inacessível), **não** reportar plugins como executados (`executed_plugins_by_req = {rid: [] for rid in target_reqs}`, `urls_tested = 0`) e registrar em `summary_message` que o daemon OWASP ZAP em `ZAP_BASE_URL` está offline/inacessível, impedindo que um simples `GET` HTTP conte como evidência positiva de plugins ZAP.
  - Quando `zap_daemon_used == True` e `mode == "baseline"`, `plugins_by_req[rid]` contém apenas `zap_cfg.get("passive", [])`. Assim, requisitos cujos plugins ZAP são exclusivamente ativos (`V1.2.4`, `V1.2.5`, `V1.5.1` possuem `passive: []`) ficam com `executed_plugins_by_req[rid] = []`, resultando corretamente em `INCONCLUSIVE` até que uma varredura em modo `active` seja executada.
- **`app/agents/dast_agent.py`**:
  - Propagar fielmente `executed_plugins_by_req` e `urls_tested` retornados por `zap_scan` (`dast_executed = bool(scan_res.ok and scan_data.get("zap_daemon_used", False) and urls_tested > 0)`).

### 4. Prevenção de Auto-Colisão de Assinaturas no Scoper (`app/aci/workspace_aci.py`)

- Em `scan_workspace_surface`:
  - Ignorar o próprio arquivo `workspace_aci.py` na detecção de literais ou usar expressões regulares estritas de código real para `V1.3.1` (ex.: `r"(?:import\s+bleach|from\s+bleach\s+import|bleach\.clean\s*\(|DOMPurify\.sanitize\s*\()"` e chamadas reais a rotas WYSIWYG), evitando que as strings literais dentro de `workspace_aci.py` gerem falso indicador positivo de `V1.3.1` ao autoavaliar `app/`.

### 5. Comportamento do Botão de Autoavaliação e Feedback DAST na UI (`static/app.js` e `templates/index.html`)

- Em `static/app.js` (`#self-check-btn`):
  - Ao clicar em **"Autoavaliar Própria Ferramenta (`app/`)"**:
    - Definir `#workspace-subpath` como `"app"`.
    - Se o checkbox `#zap-authorized` estiver marcado e `#target-url` estiver vazio, preencher `#target-url` com `window.location.origin` (ex.: `http://localhost:8000`) para que o pipeline tente executar SAST + DAST.
    - Se `#zap-authorized` **não** estiver marcado, manter `#target-url` vazio e exibir no banner informativo que a autoavaliação está rodando em modo **Somente SAST**, razão pela qual os 6 requisitos que dependem do OWASP ZAP (`V1.2.1`–`V1.2.5`, `V1.5.1`) receberão `INCONCLUSIVE`.

## Project Structure

### Documentation (this feature)

```text
specs/001-asvs-v1-assessment/
├── plan.md              # Este arquivo (saída do comando /speckit.plan)
├── research.md          # Decisões técnicas da Fase 0 + Iteração 2
├── data-model.md        # Modelo de dados relacional e transições de estado (Fase 1)
├── quickstart.md        # Guia de execução e validação ponta a ponta (Fase 1)
├── contracts/           # Contratos formais de interface (Fase 1)
│   ├── http-and-sse-api.md
│   └── agents-and-aci.md
└── tasks.md             # Lista de tarefas (atualizada pelo comando /speckit.tasks)
```

### Source Code (repository root)

```text
app/
├── __init__.py
├── models.py            # SQLModel/Pydantic: Requirement, Run, Finding, Evidence, Verdict, ToolCall, AuditLog
├── database.py          # Engine SQLite (asvs.db), sessão, seed dos 345 requisitos do CSV com flag in_scope
├── verdict.py           # Função pura de veredito exigindo cobertura de todas as required_tools mapeadas
├── main.py              # Rotas REST + SSE, injeção de dependências (Depends) para sessão, runner e config
├── aci/
│   ├── __init__.py
│   ├── workspace_aci.py # scan_workspace_surface (sem auto-colisão de literais), list_files, read_snippet
│   ├── semgrep_aci.py   # run_rules, list_findings, show_evidence (shell=False, SARIF, máx. 50/página)
│   └── zap_aci.py       # zap_spider, zap_scan, zap_alerts (conectividade real ZAP daemon + allowlist)
└── agents/
    ├── __init__.py
    ├── orchestrator.py  # Coordenação sequencial/paralela (SAST || DAST), SSE, timeouts e cancelamento
    ├── scoper.py        # Mapeamento de linguagens, rotas e superfície aplicável aos 8 requisitos
    ├── sast_agent.py    # Execução controlada de regras Semgrep por req_id via semgrep_aci
    ├── dast_agent.py    # Execução controlada de spider/scan ZAP por req_id via zap_aci
    ├── triage_agent.py  # Deduplicação por fingerprint, correlação SAST+DAST e preservação de FP
    ├── verdict_agent.py # Consolidação dos 8 vereditos injetando required_tools em app/verdict.py
    └── reporter_agent.py# Métricas do dashboard, agregação por seção (V1.2, V1.3, V1.5) e exportação
```

## Complexity Tracking

Nenhuma violação à Constituição (`v1.1.0`) foi introduzida; o refinamento fortalece o cumprimento estrito do Princípio II.
