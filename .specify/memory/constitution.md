<!--
Sync Impact Report
- Version change: 1.2.0 → 1.3.0
- Modified principles:
  - IV. Segurança da Própria Ferramenta e Guardrails Operacionais (INEGOCIÁVEL) (guardrail universal e incondicional de autorização DAST, e guardrail mandatório de pré-configuração de IA / AI Gate antes de iniciar qualquer avaliação)
- Added sections:
  - Guardrail de Autorização DAST Incondicional no Princípio IV (obrigatório para toda e qualquer execução de avaliação)
  - Guardrail de Pré-requisito de Inteligência Artificial (AI Gate) no Princípio IV (bloqueio mandatória pré-pipeline caso a IA não esteja configurada)
  - Backend Enforcement estrito em POST /api/runs (HTTP 403 / HTTP 412)
- Removed sections: None
- Templates requiring updates:
  - ✅ .specify/templates/plan-template.md (lê dinamicamente a constituição)
  - ✅ .specify/templates/spec-template.md (compatível)
  - ✅ .specify/templates/tasks-template.md (compatível)
- Follow-up TODOs: None
-->
# ASVS-Self-Assesment-Tool Constitution

## Core Principles

### I. Domínio Normativo, Escopo Restrito (V1 L1) e Referências

- A fonte normativa única de requisitos DEVE ser o arquivo CSV oficial do OWASP ASVS 5.0.0 em
  `docs/OWASP_Application_Security_Verification_Standard_5_0_0_en.csv` (presente no repositório
  como `docs/OWASP_Application_Security_Verification_Standard_5.0.0_en.csv`), contendo
  obrigatoriamente as colunas: `chapter_id`, `chapter_name`, `section_id`, `section_name`,
  `req_id`, `req_description`, `L`.
- O catálogo completo de capítulos `V1` a `V17` (345 requisitos, onde `V17` corresponde a WebRTC,
  conforme referência `https://sth.sh/en/compliance/owasp-asvs/`) DEVE ser carregado integralmente
  no banco de dados.
- O **escopo de avaliação** desta versão do sistema DEVE restringir-se exclusivamente a
  `chapter_id = 'V1'` (*Encoding and Sanitization*) e `L = 1`, totalizando exatamente 8 requisitos:
  `V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5`, `V1.3.1`, `V1.3.2` e `V1.5.1`. Nenhum outro
  capítulo ou nível PODE ser avaliado sem uma nova emenda formal a esta Constituição.
- O guia de teste de referência DEVE ser o *OWASP ASVS 4.0 Testing Guide*
  (`https://github.com/BlazingWind/OWASP-ASVS-4.0-testing-guide`). O sistema/agente DEVE
  consultá-lo para derivar procedimentos de verificação e DEVE manter uma tabela explícita de
  equivalência `4.0 → 5.0` em `docs/mapping_4_0_to_5_0.md`, marcando cada linha como `"confirmada"`
  ou `"a validar"`. É PROIBIDO presumir equivalência 1:1 entre versões sem validação explícita.
- As ferramentas de verificação automatizada do pipeline DEVEM ser **Semgrep** (SAST),
  **OWASP ZAP** (DAST) e o **AI Evaluator Agent** (IA/LLM para inspeção contextual de requisitos
  qualitativos).
- O desenho de interação dos agentes DEVE fundamentar-se no artigo de referência de Yang et al.,
  *"SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering"*
  (`docs/Yang_et_al_SWE-agent.pdf` /
  `docs/Yang et al. - SWE-agent Agent-Computer Interfaces Enable Automated Software Engineering.pdf`).

*Justificativa*: Delimitar estritamente o escopo avaliativo aos 8 requisitos V1 L1 garante
profundidade, precisão de regras SAST/DAST/IA e rastreabilidade completa entre ASVS 4.0 e 5.0,
mantendo o modelo de dados pronto para expansão futura aos 345 requisitos.

### II. Modelo de Veredito Baseado em Evidência Positiva e Cobertura Obrigatória por Ferramenta Mapeada

- Cada requisito avaliado DEVE receber exatamente um dos quatro vereditos normativos:
  `PASS` | `FAIL` | `INCONCLUSIVE` | `MANUAL_REQUIRED`.
- **Regra da Evidência Positiva**: A simples ausência de achados (zero alertas) NÃO equivale a
  `PASS`. O veredito `PASS` DEVE exigir evidência positiva verificável em todas as ferramentas
  mapeadas para o requisito **e** cobertura explicitamente declarada. Sem cobertura suficiente, o
  veredito resultante DEVE ser `INCONCLUSIVE`.
- **Cobertura Obrigatória por Ferramenta Mapeada (`config/req_tool_mapping.yaml`)**:
  - Quando um requisito tiver `tools: ["semgrep", "zap"]` mapeados em `config/req_tool_mapping.yaml`
    (requisitos `V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5` e `V1.5.1`), o veredito `PASS`
    DEVE exigir obrigatoriamente evidência positiva de **AMBAS** as ferramentas
    (`has_sast_positive == True` **E** `has_dast_positive == True`).
  - Se a etapa DAST (`OWASP ZAP`) não for executada (`SKIPPED`), se o daemon do ZAP estiver
    inacessível, ou se os plugins ZAP mapeados para o requisito não forem executados (ex.:
    requisitos `V1.2.4`, `V1.2.5` e `V1.5.1`, cujos plugins ZAP são exclusivamente ativos, quando a
    avaliação for executada apenas em modo passivo `baseline`), o requisito NÃO PODE receber `PASS`
    apenas com o Semgrep: DEVE receber obrigatoriamente `INCONCLUSIVE` (desde que possua `0` achados
    ativos; se houver achados ativos no Semgrep ou no ZAP, o veredito DEVE continuar sendo `FAIL`).
  - Requisitos cujo mapeamento dependa de análise estática e qualitativa (como `V1.3.1` referente a
    sanitização de HTML rico/WYSIWYG e políticas de renderização segura) PODEM ser avaliados de forma
    automatizada assistida pelo `AI Evaluator Agent`. Caso o modelo de IA esteja configurado, o agente
    inspeciona o código e contexto emitindo `PASS`, `FAIL` ou `INCONCLUSIVE`. Caso o modelo de IA não
    esteja configurado ou a análise seja inconclusiva, o veredito DEVE ser `MANUAL_REQUIRED`.
  - Requisitos exclusivamente estáticos (`tools: ["semgrep"]`, como `V1.3.2` sobre eval/exec) PODEM
    receber `PASS` sem execução do OWASP ZAP quando a superfície for verificada com zero achados.
- Todo veredito emitido DEVE citar obrigatoriamente:
  1. `req_id` (ex.: `V1.2.4`, `V1.3.1`);
  2. Ferramentas e agentes utilizados (`Semgrep`, `OWASP ZAP`, `AI Evaluator Agent`);
  3. IDs das regras Semgrep, plugins ZAP e/ou modelo de IA utilizado;
  4. Evidências concretas (trecho de código, `arquivo:linha`, par HTTP `request/response`, ou justificativa do modelo de IA);
  5. Nível de confiança atribuído;
  6. Limitações conhecidas da verificação realizada.
- A métrica agregada da avaliação DEVE reportar o percentual (`%`) de requisitos `PASS` sobre o
  total de 8 requisitos em escopo, acompanhado da contagem absoluta detalhada por veredito
  (`PASS`, `FAIL`, `INCONCLUSIVE`, `MANUAL_REQUIRED`).

*Justificativa*: Em segurança de aplicações, silêncio de ferramenta por falta de escopo ou omissão da
análise dinâmica ou contextual gera falsos negativos críticos. A combinação de Semgrep, OWASP ZAP e
AI Evaluator Agent permite comprovação cumulativa automatizada, fundamentada e livre de aprovações
prematuras, viabilizando conformidade total quando comprovada.

### III. Arquitetura Multiagente Orientada a ACI (SWE-agent)

- Cada agente DEVE interagir com o ambiente exclusivamente por meio de uma **Agent-Computer
  Interface (ACI)** própria, composta por um conjunto pequeno de comandos simples, bem
  documentados e com ações compactas.
- As saídas de ferramentas DEVEM ser sempre resumidas e truncadas antes de entregues ao agente
  (ex.: máximo de 50 achados por chamada, com suporte a paginação). É PROIBIDO despejar relatórios
  brutos de SAST/DAST diretamente no contexto dos agentes.
- O feedback da ACI DEVE ser sempre informativo: comandos que não encontrem resultados DEVEM
  retornar mensagem explícita (ex.: `"0 achados para a regra X em N arquivos"`), nunca saída vazia.
- **Guardrails de ACI**: Toda chamada DEVE validar entradas antes da execução:
  - O alvo do OWASP ZAP DEVE constar na `allowlist` autorizada e possuir autorização explícita;
  - Caminhos de sistema de arquivos DEVEM estar estritamente confinados ao workspace;
  - Comandos de sistema operacional DEVEM ser montados como lista de argumentos (`list[str]`),
    NUNCA por concatenação de strings ou invocação de shell;
  - Chamadas ao AI Evaluator Agent DEVEM usar prompts estritos com saídas estruturadas via Pydantic;
  - Erros de validação ou execução DEVEM devolver mensagem corretiva estruturada ao agente.
- **Histórico Enxuto e Estado Externo**: Observações antigas no histórico do agente DEVEM ser
  colapsadas, e todo o estado do pipeline DEVE residir no banco SQLite (`asvs.db`), nunca retido
  apenas no contexto conversacional dos agentes.
- O pipeline DEVE ser composto pelos seguintes **8 agentes especializados**, cada qual com papel
  definido, ACI dedicada e contrato de entrada/saída tipado via **Pydantic**:
  1. `Orchestrator`
  2. `Scoper`
  3. `SAST Agent` (Semgrep)
  4. `DAST Agent` (OWASP ZAP)
  5. `Triage/Correlation Agent`
  6. `AI Evaluator Agent` (IA/LLM para verificação contextual de V1.3.1 e requisitos qualitativos)
  7. `Verdict Agent`
  8. `Reporter Agent`

*Justificativa*: Inspirado em Yang et al. (SWE-agent), interfaces enxutas com guardrails,
truncamento determinístico e estado persistido em banco previnem degradação de contexto,
alucinações e execuções inseguras.

### IV. Segurança da Própria Ferramenta e Guardrails Operacionais (INEGOCIÁVEL)

- **Guardrail de Autorização DAST Incondicional**:
  - O aceite explícito do termo: *"Declaro que possuo autorização explícita para executar testes dinâmicos (DAST / OWASP ZAP) contra a URL alvo informada acima."* é pré-requisito universal e obrigatório para submissão de QUALQUER execução do pipeline (seja avaliação manual ou atalho de autoavaliação, com ou sem URL alvo inicialmente preenchida), estabelecendo o termo formal e inegociável de responsabilidade do operador.
  - O formulário web DEVE impedir a submissão no cliente (com destaque visual em vermelho no container, foco imediato no checkbox e anúncio acessível via `aria-live="polite"`) caso o checkbox não esteja marcado.
  - O backend DEVE rejeitar com `HTTP 403 Forbidden` qualquer requisição em `POST /api/runs` onde `zap_authorized != True`, impedindo a criação do registro de Run.
  - O modo ativo do ZAP DEVE estar desabilitado por padrão no formulário, mantendo o scan *baseline* passivo como padrão (`default`).
- **Guardrail de Pré-requisito de Inteligência Artificial (AI Gate)**:
  - A ferramenta NÃO PODE iniciar nenhuma execução de avaliação sem que o provedor de IA generativa (modelo e chave de API sob política Write-Only) esteja ativamente configurado em memória volátil (`AISecretStore.is_configured() == True`). Isso assegura que o `AIEvaluatorAgent` nunca seja ignorado ou caia silenciosamente em `MANUAL_REQUIRED` por omissão de configuração do operador.
  - No frontend, caso a IA não esteja configurada, os botões de início devem impedir a submissão, exibir banner de aviso com token Fluent e direcionar o foco para o painel de configuração de IA.
  - No backend, o endpoint `POST /api/runs` DEVE rejeitar qualquer requisição com `HTTP 412 Precondition Failed` caso `AISecretStore.is_configured()` seja `False`, não permitindo a criação de Runs sem o motor de IA pronto para execução.
- **Política Estrita Write-Only para Credenciais de IA (Zero Leakage)**:
  - Credenciais, chaves de API (`api-key`) e segredos de modelos de IA DEVEM ser tratados sob política estrita Write-Only (somente escrita): após inseridas pelo usuário, a `api-key` NUNCA pode ser visualizada, resgatada, logada ou retornada em nenhuma resposta de API REST.
  - Endpoints de consulta de status de IA DEVEM retornar exclusivamente indicativo booleano de configuração, nome do modelo e valor mascarado (ex.: `"••••••••"`).
  - É TERMINANTEMENTE PROIBIDO registrar chaves de API em arquivos de banco de dados (`asvs.db`), tabelas de log ou auditoria (`audit_log`), relatórios exportados (`HTML` / `JSON`) ou no histórico transmitido aos clientes via SSE ou WebSockets.
  - A interface DEVE disponibilizar teste prévio de conectividade com o modelo de IA que valide a chave e a comunicação sem expor a credencial em caso de falha.
- A própria ferramenta DEVE cumprir integralmente os requisitos do **ASVS V1 L1** que ela avalia:
  - É PROIBIDA a execução de shell com entrada do usuário (`shell=False` obrigatório);
  - É PROIBIDO o uso de `eval()`, `exec()` ou execução dinâmica equivalente (V1.3.2);
  - Toda saída renderizada em HTML/DOM/URL/JS DEVE ser contextualmente escapada ou sanitizada (V1.2.1, V1.2.2, V1.2.3, V1.3.1);
  - Todas as consultas ao banco de dados DEVEM ser parametrizadas via ORM/SQLModel (V1.2.4);
  - Toda desserialização DEVE usar formatos e parsers seguros (V1.5.1).

*Justificativa*: Uma ferramenta de avaliação de segurança ASVS não pode introduzir vetores de RCE, Command Injection, XSS, SQLi, SSRF, execuções dinâmicas não autorizadas, falhas na avaliação qualitativa por omissão de IA ou vazamento de credenciais e chaves de inteligência artificial.

### V. Stack Técnica Padronizada e Design System Fluent 2

- O backend DEVE utilizar **Python 3.12**, **FastAPI**, **SQLModel/Pydantic** e **SQLite**
  (`asvs.db`), com execução do pipeline em background e transmissão de progresso em tempo real via
  **Server-Sent Events (SSE)**.
- A integração de ferramentas DEVE utilizar **Semgrep CLI** (saída em formato SARIF/JSON),
  **OWASP ZAP em Docker** (modo daemon exposto via API REST) e integração direta com APIs de IA
  (Google Gemini / OpenAI compatível) com isolamento seguro de chaves em memória.
- O frontend DEVE utilizar **HTML5** e **Fluent 2 Design System** (Fluent UI Web Components via CDN
  e design tokens oficiais). Antes de projetar ou implementar a UI, a equipe/agente DEVE instalar
  ou consultar o skill oficial de Fluent listado em `https://www.skills.sh/` — especificamente o
  pacote **`microsoft/fluentui`** (`npx skills add microsoft/fluentui`, incluindo as skills
  `token-lookup` e `v9-component`, além de `microsoft/fluentui-system-icons` quando aplicável) — e
  seguir estritamente seus tokens, componentes e diretrizes de acessibilidade.
- A interface DEVE suportar alternância de **tema claro e escuro** e atender ao nível de
  conformidade **WCAG 2.2 AA**.
- As visualizações gráficas DEVEM ser leves, implementadas em **SVG ou Canvas** utilizando
  exclusivamente as cores dos tokens Fluent: gráfico de rosca (*donut*) de distribuição de
  vereditos e gráfico de barras por seção (`V1.2`, `V1.3`, `V1.5`).

*Justificativa*: Padronizar a stack evita dependências pesadas de SPA no frontend, garante
acessibilidade nativa (WCAG 2.2 AA) via Fluent 2 tokens e mantém o backend assíncrono simples e
auditável.

### VI. Seeds Normativos e Mapeamento Versionado de Regras

- Na inicialização do banco (`asvs.db`), o sistema DEVE executar a carga inicial obrigatória
  (*seed*) do CSV do ASVS 5.0 contendo os 345 requisitos (`V1`–`V17`), calculando e persistindo a
  flag booleana `in_scope = (chapter_id == 'V1' and L == 1)`.
- O vínculo entre cada `req_id` em escopo e os respectivos identificadores de regras Semgrep,
  plugins OWASP ZAP e agentes de IA DEVE ser mantido em arquivo declarativo e versionado em
  `config/req_tool_mapping.yaml`.

*Justificativa*: Separar o catálogo normativo e o mapeamento de regras do código-fonte garante
auditabilidade e permite atualizar regras Semgrep/ZAP/IA sem alterar a lógica nuclear dos agentes.

## Especificação da Stack Técnica e Requisitos de Interface

| Camada | Tecnologia / Padrão Obrigatório | Restrições e Configurações |
| :--- | :--- | :--- |
| **Backend & API** | Python 3.12 + FastAPI | Execução assíncrona de pipeline em background; streaming de eventos via SSE (`text/event-stream`). |
| **Persistência & Modelos** | SQLModel + Pydantic + SQLite (`asvs.db`) | Estado integral do pipeline persistido em SQLite; contratos estritos de I/O entre agentes validados por Pydantic. |
| **Motor SAST** | Semgrep CLI | Invocação segura por lista de argumentos (`shell=False`); saída estruturada em SARIF/JSON; truncamento via ACI. |
| **Motor DAST** | OWASP ZAP (Docker Daemon + REST API) | Provisionado via `docker-compose`; scan passivo (*baseline*) por padrão; scan ativo bloqueado sem autorização explícita e allowlist. |
| **Motor de Avaliação IA** | AI Evaluator Agent (API REST Segura) | Gerenciamento de credenciais Write-Only em memória; prompts de sistema estritos; handshake prévio de teste. |
| **Frontend & UI** | HTML5 + Fluent 2 Design System | Fluent UI Web Components via CDN + Design Tokens (`microsoft/fluentui` em `https://www.skills.sh/`); temas claro/escuro; WCAG 2.2 AA. |
| **Gráficos** | SVG / Canvas nativo | Cores extraídas dos tokens Fluent; gráfico *donut* de vereditos (8 requisitos) e barras por seção (`V1.2`, `V1.3`, `V1.5`). |

## Catálogo de Dados, Equivalência Normativa e Contratos do Pipeline

1. **Artefatos Normativos e de Configuração Obrigatórios**:
   - `docs/OWASP_Application_Security_Verification_Standard_5_0_0_en.csv` (ou alias local
     `docs/OWASP_Application_Security_Verification_Standard_5.0.0_en.csv`): 345 linhas de
     requisitos (`V1`–`V17`), das quais apenas os 8 requisitos com `chapter_id == 'V1'` e `L == 1`
     recebem `in_scope = True`.
   - `docs/mapping_4_0_to_5_0.md`: Tabela explícita de equivalência entre o *OWASP ASVS 4.0 Testing
     Guide* e os requisitos V1 L1 do ASVS 5.0 (`V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5`,
     `V1.3.1`, `V1.3.2`, `V1.5.1`), com coluna de status restrita a `"confirmada"` ou
     `"a validar"`.
   - `config/req_tool_mapping.yaml`: Mapeamento versionado associando cada `req_id` às ferramentas
     requeridas (`tools`), regras Semgrep, plugins ZAP, avaliação IA, superfície esperada e
     critérios de evidência positiva.
2. **Fluxo e Contratos Multiagente**:
   - Todo passo executado por `Orchestrator`, `Scoper`, `SAST Agent`, `DAST Agent`,
     `Triage/Correlation Agent`, `AI Evaluator Agent`, `Verdict Agent` e `Reporter Agent` DEVE
     registrar seu estado em `asvs.db` e emitir eventos de progresso consumíveis via SSE.
   - A autoavaliação da própria ferramenta contra os 8 requisitos de `V1 L1` é critério de aceite
     obrigatório antes de qualquer release.

## Governance

- **Supremacia Constitucional**: Esta Constituição sobrepõe-se a quaisquer convenções ad-hoc,
  planos de implementação ou decisões locais de código. Qualquer divergência em especificações
  (`spec.md`), planos (`plan.md`) ou tarefas (`tasks.md`) DEVE ser corrigida para alinhar-se a este
  documento.
- **Procedimento de Emenda**: Alterações no escopo de avaliação (atualmente restrito a `V1` e
  `L = 1`), no modelo de veredito, nos guardrails de segurança ou na stack técnica exigem uma
  emenda explícita a `.specify/memory/constitution.md`, acompanhada de justificativa documentada,
  atualização do relatório de impacto e revisão dos artefatos dependentes (`docs/mapping_4_0_to_5_0.md`
  e `config/req_tool_mapping.yaml`).
- **Política de Versionamento (SemVer)**:
  - `MAJOR`: Remoção ou redefinição incompatível de princípios, expansão/alteração do escopo
    normativo de avaliação (`V1 L1`) ou flexibilização de restrições de segurança.
  - `MINOR`: Adição de novo princípio ou seção governante, expansão material de diretrizes
    operacionais, novos agentes nucleares ou inclusão de guardrails de credenciais/segurança.
  - `PATCH`: Esclarecimentos textuais, refinamentos não semânticos ou correções de digitação.
- **Revisão de Conformidade**: Todo plano técnico (`/speckit.plan`), especificação
  (`/speckit.specify`) e revisão de código DEVE validar explicitamente a conformidade com os
  Princípios I a VI desta Constituição.

**Version**: 1.3.0 | **Ratified**: 2026-10-12 | **Last Amended**: 2026-10-13
