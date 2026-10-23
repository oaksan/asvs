---
name: constitution-check
description: Validação automatizada e checklist dos Princípios I a VI da Constituição do ASVS Self-Assessment Tool v1.3.0.
---

# Skill: constitution-check

Esta skill atua como mecanismo de auditoria para garantir conformidade contínua com a constituição do projeto.

## Checklist de Princípios

### Princípio I — Especificação Estrita e TDD
- Existe especificação com cenários Given/When/Then?
- Os testes em `tests/` cobrem os critérios de aceitação e falham antes da implementação?

### Princípio II — Automação e Mapeamento ASVS 5.0
- Requisitos em escopo respeitam `chapter_id == 'V1'` e `L == 1`?
- Mapeamento presente em `config/req_tool_mapping.yaml`?

### Princípio III — Arquitetura de Agentes e Isolamento ACI
- Os agentes respeitam contratos Pydantic estritos para entrada e saída?
- O estado está integralmente persistido em SQLite (`asvs.db`)?

### Princípio IV — Segurança e Guardrails
- Nenhum `shell=True` presente no diff?
- Confinamento ao workspace validado?
- Consentimento DAST e allowlist exigidos antes de executar ZAP?
- Chaves de IA gerenciadas via `AISecretStore` em memória volátil, mascaradas em `"••••••••"`?
- Saídas de ferramentas truncadas em ≤ 50 achados?

### Princípio V — Interface Fluent 2 e Acessibilidade
- Uso exclusivo de tokens Fluent 2 e Web Components?
- Suporte a tema claro e escuro presente?
- Conformidade WCAG 2.2 AA (contraste e atributos ARIA)?

