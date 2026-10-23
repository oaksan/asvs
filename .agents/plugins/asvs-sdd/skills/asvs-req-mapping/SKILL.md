---
name: asvs-req-mapping
description: Mapeia e valida requisitos normativos do ASVS 5.0 (Capítulo V1 Nível 1) contra o catálogo CSV e o arquivo de mapeamento de ferramentas.
---

# Skill: asvs-req-mapping

Esta skill orienta o mapeamento consistente entre requisitos normativos do ASVS 5.0 e as ferramentas de avaliação automatizada.

## 1. Verificação Normativa
- Carregar o catálogo de requisitos em `docs/OWASP_Application_Security_Verification_Standard_5.0.0_en.csv`.
- O escopo atual é restrito ao capítulo **V1** e nível **L1** (`chapter_id == 'V1'` e `L == 1`).

## 2. Associação Declarativa
- Toda nova regra ou requisito incluído deve ser registrado em `config/req_tool_mapping.yaml`.
- Cada requisito deve especificar:
  - `semgrep_rules`: lista de identificadores de regras SAST.
  - `zap_alert_ids`: lista de IDs de alertas do OWASP ZAP.
  - `ai_evaluator`: booleano indicando se requer análise qualitativa de IA.

