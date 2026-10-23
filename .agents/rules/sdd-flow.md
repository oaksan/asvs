# Roteiro de Orquestração SDD e Gates

Esta regra orienta o fluxo operacional do ciclo SDD executado pelo condutor principal:

1. **Separação de Papéis**: O condutor orquestra as fases usando os comandos em `.gemini/commands/` e invoca os especialistas específicos para cada tarefa.
2. **Revisões com Bloqueio (Gates)**: Nenhuma fase do ciclo SDD avança para a próxima sem a verificação do `constitution-guardian` e o consentimento explícito do operador.
3. **Isolamento de Escopo**:
   - `test-author` escreve exclusivamente em `tests/`.
   - `backend-implementer` atua prioritariamente em `app/`.
   - `frontend-implementer` atua em `templates/` e `static/`.
   - `sast-rules-engineer` atua em `config/semgrep/`.
   - `dast-zap-engineer` atua em `app/aci/zap_aci.py` e arquivos docker.
   - Os agentes de revisão (`aci-security-reviewer`, `llm-security-reviewer`, `constitution-guardian`) são estritamente de leitura.

