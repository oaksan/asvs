# Quickstart: Validação da Integração de IA, Proteção de Chaves e Guardrail DAST (`003-ai-evaluator-and-dast-guardrails`)

**Feature**: [spec.md](./spec.md)  
**Date**: 2026-10-13

---

## 1. Pré-Requisitos

1. Servidor web da aplicação em execução:
   ```bash
   .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
2. Container do OWASP ZAP em execução (para cenários com DAST):
   ```bash
   docker compose up -d zap
   ```

---

## 2. Cenário 1: Validação do Bloqueio Mandatório DAST (UI & Backend)

### Teste de Bloqueio no Backend
Tente iniciar uma avaliação informando URL alvo mas com autorização desmarcada:
```bash
curl -i -X POST http://localhost:8000/api/runs \
  -H "Content-Type: application/json" \
  -d '{"source_type": "workspace_path", "workspace_subpath": "app", "target_url": "http://localhost:8000", "zap_authorized": false}'
```
- **Resultado Esperado**:
  - Código HTTP: `403 Forbidden`
  - Resposta: `"Guardrail DAST acionado: execução dinâmica bloqueada porque o checkbox de autorização explícita não foi confirmado."`

### Teste de Bloqueio na Interface Web
1. Abra `http://localhost:8000` no navegador.
2. Preencha o campo "URL Alvo em Execução" com `http://localhost:8000`.
3. Deixe o checkbox de autorização desmarcado.
4. Clique em "Iniciar Avaliação V1 L1".
- **Resultado Esperado**: O formulário cancela o envio, aplica foco com contorno vermelho no checkbox de autorização e exibe alerta de segurança.

---

## 3. Cenário 2: Configuração Segura de IA e Teste de Conexão

### Testar Conexão via API
```bash
curl -i -X POST http://localhost:8000/api/ai/test-connection \
  -H "Content-Type: application/json" \
  -d '{"model_name": "gemini-2.0-flash", "api_key": "SUA_API_KEY"}'
```
- **Resultado Esperado**:
  - `{"ok": true, "model_name": "gemini-2.0-flash", "latency_ms": ..., "message": "Conexão com o modelo 'gemini-2.0-flash' estabelecida com sucesso (... ms)."}`

### Salvar Credenciais em Memória e Verificar Mascaramento
```bash
curl -X POST http://localhost:8000/api/ai/config \
  -H "Content-Type: application/json" \
  -d '{"model_name": "gemini-2.0-flash", "api_key": "SUA_API_KEY"}'

curl http://localhost:8000/api/ai/status
```
- **Resultado Esperado**:
  - Retorno: `{"configured": true, "model_name": "gemini-2.0-flash", "key_masked": "••••••••", "provider": "gemini"}`
  - Zero ocorrências da chave original em texto puro.

---

## 4. Cenário 3: Autoavaliação da Própria Ferramenta atingindo 100.0% PASS

Execute a avaliação completa sobre `app/` com DAST ativo e IA habilitada:
```bash
curl -X POST "http://localhost:8000/api/runs?sync=true" \
  -H "Content-Type: application/json" \
  -d '{"source_type": "workspace_path", "workspace_subpath": "app", "target_url": "http://localhost:8000", "zap_authorized": true, "zap_mode": "active"}'
```
- **Resultado Esperado**:
  - `metrics.pass_percentage`: **`100.0%`**
  - `metrics.pass_count`: **`8`**
  - `metrics.fail_count`: **`0`**
  - `metrics.inconclusive_count`: **`0`**
  - `metrics.manual_count`: **`0`**
  - O requisito `V1.3.1` recebe `PASS` emitido pelo `AIEvaluatorAgent`.

