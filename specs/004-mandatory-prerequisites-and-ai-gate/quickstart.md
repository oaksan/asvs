# Quickstart Guide: 004-mandatory-prerequisites-and-ai-gate

Este guia orienta a validação manual e automatizada dos dois guardrails operacionais de inicialização da ferramenta:
1. **Autorização DAST Universal** (`zap_authorized=True`)
2. **AI Prerequisite Gate** (`AISecretStore.is_configured()=True`)

---

## 1. Validação do Bloqueio sem Autorização DAST (HTTP 403)

### Pela Interface Web
1. Abra a aplicação em `http://localhost:8000`.
2. Certifique-se de que o checkbox *"Declaro que possuo autorização explícita para executar testes dinâmicos (DAST / OWASP ZAP) contra a URL alvo informada acima."* esteja desmarcado.
3. Clique em **"Iniciar Avaliação V1 L1"**.
4. **Resultado Esperado**:
   - O formulário não é enviado.
   - O container `#dast-auth-container` ganha contorno em vermelho (`.has-error`).
   - O foco do teclado é posicionado diretamente no checkbox `#zap-authorized`.
   - O banner de feedback anuncia o bloqueio.

### Pela API REST (cURL)
```bash
curl -X POST http://localhost:8000/api/runs \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "workspace_path",
    "workspace_subpath": "app",
    "zap_authorized": false
  }'
```
**Resposta Esperada**: `HTTP 403 Forbidden`
```json
{
  "detail": "Guardrail DAST acionado: É obrigatório declarar autorização explícita para testes dinâmicos antes de iniciar qualquer avaliação."
}
```

---

## 2. Validação do AI Prerequisite Gate (HTTP 412)

### Pela Interface Web
1. Com o checkbox DAST marcado, tente iniciar a avaliação sem ter configurado a chave de IA.
2. Clique em **"Iniciar Avaliação V1 L1"** ou **"Autoavaliar Própria Ferramenta"**.
3. **Resultado Esperado**:
   - O envio é cancelado.
   - O painel colapsável de IA é automaticamente expandido.
   - O campo `#ai-api-key` recebe o foco para digitação.
   - Uma mensagem com token Fluent alerta sobre a obrigatoriedade da configuração de IA.

### Pela API REST (cURL)
```bash
curl -X POST http://localhost:8000/api/runs \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "workspace_path",
    "workspace_subpath": "app",
    "zap_authorized": true
  }'
```
**Resposta Esperada**: `HTTP 412 Precondition Failed`
```json
{
  "detail": "Pré-requisito de IA não atendido: O provedor de IA generativa deve ser configurado (modelo e API Key em memória) antes de iniciar a avaliação."
}
```

---

## 3. Fluxo de Sucesso: Configuração + Autorização DAST

1. **Configurar a IA via API ou UI**:
```bash
curl -X POST http://localhost:8000/api/ai/config \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "gemini-2.0-flash",
    "api_key": "sua-chave-aqui"
  }'
```
2. **Disparar a Avaliação Autorizada**:
```bash
curl -X POST "http://localhost:8000/api/runs?sync=true" \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "workspace_path",
    "workspace_subpath": "app",
    "target_url": "http://localhost:8000",
    "zap_authorized": true,
    "zap_mode": "active"
  }'
```
**Resultado Esperado**: Execução aceita (`HTTP 202`), pipeline disparado e concluído com sucesso atingindo **100.0% PASS**.

