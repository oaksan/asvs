---
name: sdd-multiagent-flow
description: Procedimento passo a passo para orquestração e delegação entre agentes no ciclo Spec-Driven Development.
---

# Skill: sdd-multiagent-flow

Orientações para o `sdd-conductor` coordenar os 11 agentes especialistas durante o ciclo SDD:

1. **Fase Specify**: Invocar `asvs-mapper` e opcionalmente `threat-modeler`. Finalizar com parecer do `constitution-guardian`.
2. **Fase Plan**: Invocar `solution-architect` e revisar viabilidade técnica.
3. **Fase Tasks & TDD**: Invocar `test-author` para redigir a suíte de testes antes da implementação.
4. **Fase Implement**: Delegar paralelamente para `backend-implementer` e `frontend-implementer`. Acionar especialistas de ferramentas conforme o escopo (`sast-rules-engineer`, `dast-zap-engineer`).
5. **Fase Review**: Executar varreduras de leitura com `aci-security-reviewer` e `llm-security-reviewer`. Obter liberação do `constitution-guardian` antes de solicitar aprovação do usuário.

