# Quickstart & Validation Guide: ASVS-Self-Assesment-Tool (V1 L1)

**Feature**: `001-asvs-v1-assessment`  
**Date**: 2026-10-13 (Iteração 2)  
**References**: [data-model.md](./data-model.md) | [http-and-sse-api.md](./contracts/http-and-sse-api.md) | [agents-and-aci.md](./contracts/agents-and-aci.md)

---

## 1. Pré-requisitos

- **Python**: `3.12+`
- **Semgrep CLI**: instalado no ambiente (`semgrep --version`)
- **Docker & Docker Compose**: para provisionamento do daemon OWASP ZAP (`http://localhost:8090`) e/ou execução containerizada
- **Skill de Frontend (Fluent 2)**: Antes de modificar ou validar componentes visuais, consultar o skill **`microsoft/fluentui`** (`npx skills add microsoft/fluentui`, incluindo `token-lookup` e `v9-component`) listado em `https://www.skills.sh/`.

---

## 2. Inicialização do Ambiente

### 2.1 Subir o serviço OWASP ZAP em modo Daemon (Docker Compose)

```bash
docker compose up -d zap
```

- O daemon ZAP responde na porta configurada (`http://localhost:8090/JSON/core/view/version/`).

### 2.2 Instalar dependências e iniciar a aplicação FastAPI

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Resultado esperado no Startup**:
- Criação automática das tabelas em `asvs.db` ([data-model.md](./data-model.md)).
- Seed automático de `docs/OWASP_Application_Security_Verification_Standard_5.0.0_en.csv` com **345 requisitos** totais (`V1`–`V17`), marcando `in_scope = True` exclusivamente para os **8 requisitos** de `V1` com `L = 1` (`V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5`, `V1.3.1`, `V1.3.2`, `V1.5.1`).

---

## 3. Cenários de Validação Ponta a Ponta

### Cenário 1: Verificação do Catálogo e Escopo V1 L1

```bash
curl -s http://localhost:8000/api/requirements/in-scope | jq '.total, (.items | map(.req_id))'
curl -s "http://localhost:8000/api/requirements?page=1&page_size=50" | jq '.total'
```

- **Resultado esperado**: `total = 8` no endpoint `/in-scope` listando exatamente `["V1.2.1", "V1.2.2", "V1.2.3", "V1.2.4", "V1.2.5", "V1.3.1", "V1.3.2", "V1.5.1"]` e `total = 345` no catálogo geral.

### Cenário 2: Execução do Pipeline contra o Alvo Vulnerável (`tests/vulnerable_app`)

1. Disparar uma nova avaliação via UI (`http://localhost:8000`) ou via REST ([http-and-sse-api.md](./contracts/http-and-sse-api.md)):

```bash
curl -X POST "http://localhost:8000/api/runs?sync=true" \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "workspace_path",
    "workspace_subpath": "tests/vulnerable_app",
    "target_url": null,
    "zap_authorized": false,
    "zap_mode": "baseline"
  }'
```

- **Resultado esperado**:
  - Todos os 8 requisitos (`V1.2.1` a `V1.5.1`) com vulnerabilidades plantadas em `tests/vulnerable_app/app.py` recebem veredito **`FAIL`** (`fail_count = 8`, `pass_percentage = 0.0%`) com evidências navegáveis (`arquivo:linha` + trecho de código).

### Cenário 3: Autoavaliação da Própria Ferramenta (`app/`) — Modo Somente SAST vs. SAST + DAST (OWASP ZAP)

1. **Execução Somente SAST** (`workspace_subpath = "app"`, `target_url = null` / `DAST - SKIPPED`):
   - **Resultado esperado (Constituição v1.1.0 — Princípio II)**:
     - **`0 FAIL`** (`fail_count = 0`);
     - **`V1.3.2`** (`tools: ["semgrep"]`) recebe **`PASS`** (`pass_count = 1`, `pass_percentage = 12.5%`);
     - **`V1.3.1`** (`tools: ["semgrep"]` + revisão manual de HTML rico) recebe **`MANUAL_REQUIRED`** (`manual_count = 1`);
     - Os **6 requisitos** mapeados para `["semgrep", "zap"]` (`V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5`, `V1.5.1`) recebem obrigatoriamente **`INCONCLUSIVE`** (`inconclusive_count = 6`), pois embora tenham `0` achados no Semgrep, dependem da execução do OWASP ZAP para confirmação dinâmica.
2. **Execução SAST + DAST com OWASP ZAP Ativo** (`target_url = "http://localhost:8000"`, `zap_authorized = true` e container `zap` ativo):
   - No modo `baseline` passivo, os requisitos com plugins passivos ZAP (`V1.2.1`, `V1.2.2`, `V1.2.3`) que passarem limpos transitam de `INCONCLUSIVE` para `PASS`, enquanto os requisitos com plugins exclusivamente ativos (`V1.2.4`, `V1.2.5`, `V1.5.1`) permanecem `INCONCLUSIVE` até que uma rodada em modo `active` seja executada sem alertas.

---

## 4. Execução da Suíte de Testes Automatizados

```bash
.venv/bin/pytest -v
```
