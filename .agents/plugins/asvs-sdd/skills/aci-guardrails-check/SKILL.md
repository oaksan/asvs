---
name: aci-guardrails-check
description: Varredura de segurança focada em invocações externas, arquivos e conformidade ACI no código-fonte.
---

# Skill: aci-guardrails-check

Esta skill executa verificações estáticas para identificar violações nos módulos de interface com ferramentas (`app/aci/` e `app/agents/`).

## Verificações Operacionais
1. **Auditoria de Subprocess**:
   - Procurar ocorrências de `shell=True`, `os.system` ou concatenações de strings em comandos.
   - Garantir que todos os argumentos sejam passados como `list[str]`.
2. **Auditoria de Escopo de Arquivos**:
   - Verificar chamadas `Path(...)` e conferir se há validação de confinamento dentro do workspace.
3. **Auditoria de Exposição de Chaves**:
   - Verificar se `api_key` ou segredos são passados em query strings, logs (`logger.info`), retornos de API ou inserções no banco SQLite.

