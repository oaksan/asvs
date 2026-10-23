---
name: zap-baseline
description: Procedimento operacional estrito para execução de testes dinâmicos (DAST) via OWASP ZAP em modo baseline/passivo, com validação obrigatória de consentimento explícito e allowlist.
---

# Skill: zap-baseline

Esta skill implementa o procedimento seguro para automação e execução do OWASP ZAP no ASVS Self-Assessment Tool.

## 1. Pré-condições Mandatórias
Antes de qualquer chamada à API do ZAP ou inicialização de scan:
1. **Consentimento Explícito**: O parâmetro `zap_authorized` DEVE ser `True`. Caso seja `False` ou ausente, a operação deve ser abortada imediatamente com erro `403 Forbidden`.
2. **Validação de Allowlist**: O domínio e porta da URL alvo devem constar na lista autorizada (`app/aci/zap_aci.py`). Alvos externos ou não permitidos devem ser bloqueados.
3. **Container Saudável**: Verificar se o container ZAP está em execução na porta configurada (padrão 8080) através de handshake prévio (`/JSON/core/view/version/`).

## 2. Modos de Varredura
- **Baseline / Scan Passivo (Padrão)**: Coleta e análise de tráfego sem injeção agressiva de payloads.
- **Scan Ativo (Restrito)**: Requer autorização explícita adicional e jamais deve ser executado em ambientes de produção ou sem isolamento.

## 3. Truncamento e Sanitização de Resultados
- Alertas retornados pelo ZAP devem ser resumidos e agrupados por CWE / `alert_id`.
- O número máximo de achados por requisição deve ser truncado em 50 para evitar sobrecarga de contexto.
- Em caso de zero alertas, retornar mensagem explícita e clara (ex.: `"0 achados ZAP para a URL informada"`).

