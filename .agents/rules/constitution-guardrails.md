# Regras Mandatórias de Guardrails ACI e Segurança

Esta regra está permanentemente ativa para todos os agentes trabalhando no projeto.

## 1. Confinamento e Chamadas de Sistema Operacional
- É terminantemente proibido o uso de `shell=True` no módulo `subprocess` ou chamadas `os.system` / `os.popen`.
- Todo comando externo deve ser construído exclusivamente como lista imutável de strings (`list[str]`).
- Todos os caminhos de arquivos recebidos via API ou parâmetros devem ser resolvidos com `pathlib.Path.resolve()` e verificados com `path.is_relative_to(workspace_root)`.

## 2. Guardrails DAST / OWASP ZAP
- Nenhuma operação DAST pode ser disparada se a flag de consentimento explícito `zap_authorized` for `False` ou estiver ausente.
- A URL alvo deve ser validada contra a lista de alvos permitidos (`allowlist`).
- Scans ativos são proibidos por padrão; a ferramenta opera em modo passivo/baseline seguro.

## 3. Gestão e Isolamento de Chaves (AI Secrets)
- Credenciais e tokens de modelos LLM devem residir exclusivamente na classe `AISecretStore` em memória volátil.
- É vedado o armazenamento de chaves no banco `asvs.db`, escrita em arquivos temporários ou persistência em variáveis de ambiente globais de processo.
- As saídas de API, relatórios e logs gerados devem sempre mascarar segredos como `"••••••••"`.

