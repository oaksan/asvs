# Feature Specification: Avaliador com IA (AI Evaluator Agent), Configuração Segura de Provedores e Bloqueio Mandatório de Autorização DAST

**Feature Branch**: `003-ai-evaluator-and-dast-guardrails`

**Created**: 2026-10-13

**Status**: Draft

**Input**: User description: "SPECIFY_FEATURE_DIRECTORY=specs/003-ai-evaluator-and-dast-guardrails — Crie a especificação da feature 003-ai-evaluator-and-dast-guardrails contemplando: 1. Bloqueio Estrito de Inicialização Sem Autorização DAST (UI e Backend rejeitam se houver target_url sem zap_authorized); 2. Avaliador com IA (AI Evaluator Agent) para analisar requisitos qualitativos como V1.3.1 eliminando MANUAL_REQUIRED para PASS comprovado; 3. Configuração Segura do Provedor de IA (nome do modelo + api-key write-only sem vazamento) com botão e endpoint de Teste de Conexão."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bloqueio Mandatório de Início de Avaliação sem Aceite Explícito de Autorização DAST (Priority: P1)

Um avaliador de segurança configura uma nova avaliação informando uma URL alvo para testes dinâmicos (DAST). O sistema impede terminantemente o início do pipeline tanto na interface web quanto no backend enquanto o checkbox formal de consentimento (*"Declaro que possuo autorização explícita para executar testes dinâmicos (DAST / OWASP ZAP) contra a URL alvo informada acima"*) não estiver explicitamente marcado. Caso o usuário tente disparar a avaliação sem o consentimento, a interface cancela o envio, aplica foco com destaque visual em vermelho no campo de autorização e emite alerta acessível via tecnologia assistiva. No backend, qualquer tentativa de requisição contendo URL alvo sem autorização é rejeitada com código HTTP 403 sem persistir a execução.

**Why this priority**: É um guardrail inegociável de segurança operacional e conformidade legal (Princípio IV da Constituição v1.2.0), prevenindo varreduras dinâmicas não autorizadas contra alvos web acidentais ou externos.

**Independent Test**: Pode ser testado preenchendo o campo de URL alvo e clicando em "Iniciar Avaliação V1 L1" ou no atalho "Autoavaliar Própria Ferramenta": a aplicação deve bloquear o envio e exibir alerta até que o checkbox seja marcado. Além disso, uma requisição direta à API REST sem o flag deve retornar HTTP 403.

**Acceptance Scenarios**:

1. **Given** que o avaliador preencheu o campo de URL alvo (`target_url`) no formulário de Nova Avaliação mas deixou desmarcado o checkbox de autorização (`zap_authorized = false`), **When** clica no botão "Iniciar Avaliação V1 L1" ou aciona o atalho "Autoavaliar Própria Ferramenta", **Then** a submissão é bloqueada no navegador, o checkbox recebe foco e borda de destaque vermelha (token Fluent), e uma mensagem de bloqueio é anunciada imediatamente via região `aria-live="polite"`.
2. **Given** que o cliente ou um script envia uma requisição `POST /api/runs` contendo `target_url` válida mas com `zap_authorized = false`, **When** o backend processa a requisição, **Then** a API responde com código HTTP 403 (Forbidden), detalhando que testes dinâmicos exigem confirmação explícita de autorização, e nenhuma execução (`Run`) é criada no banco de dados.
3. **Given** que o usuário informou a URL alvo E marcou devidamente o checkbox de autorização, **When** clica em iniciar a avaliação, **Then** o formulário é submetido com sucesso e o pipeline inicia normalmente.
4. **Given** que o usuário NÃO informou URL alvo (`target_url` vazio, modo somente SAST), **When** clica em iniciar a avaliação, **Then** o pipeline executa em modo exclusivamente estático sem exigir a marcação do checkbox de autorização dinâmica.

---

### User Story 2 - Configuração Segura Write-Only de Modelo de IA e Teste Prévio de Conectividade (Priority: P1)

Antes de iniciar uma avaliação ou a qualquer momento no painel de configuração, o avaliador acessa o card/modal de Provedor de IA para configurar o modelo generativo responsável pela análise qualitativa de código. O avaliador informa o identificador do modelo (ex.: `gemini-1.5-pro`, `gemini-2.0-flash`, `gpt-4o`) e insere sua chave de API (`api-key`) em campo protegido de senha. O sistema valida e testa a conexão sob demanda através do botão "Testar Conexão com IA", confirmando a conectividade em tempo real. Uma vez salva, a chave de API é mantida em memória sob política estrita *write-only*: ela jamais é exposta em chamadas de API, telas, relatórios ou logs, exibindo na interface apenas um status seguro mascarado.

**Why this priority**: Permite habilitar o motor de IA para resolver requisitos complexos mantendo proteção absoluta contra vazamento de credenciais (Princípio IV da Constituição v1.2.0).

**Independent Test**: Pode ser testado abrindo o painel de IA, inserindo uma chave e modelo, clicando em "Testar Conexão com IA", verificando o feedback de sucesso/latência, recarregando a página e confirmando que a chave nunca é retornada em texto puro pela API REST ou exposta na interface.

**Acceptance Scenarios**:

1. **Given** que o avaliador informa o modelo e a chave de API e clica em "Testar Conexão com IA", **When** o sistema realiza o handshake de diagnóstico com o provedor, **Then** a interface exibe feedback positivo com a latência de resposta e a confirmação do modelo conectado, sem refletir a chave na resposta.
2. **Given** que o avaliador submete credenciais inválidas ou um modelo inacessível no teste de conexão, **When** o handshake falha, **Then** o sistema exibe mensagem de erro diagnóstica explicativa sem exibir, concatenar ou registrar a chave de API nos detalhes do erro.
3. **Given** que a chave de IA foi gravada com sucesso, **When** a interface ou qualquer cliente consulta o endpoint de status da IA (`GET /api/ai/status`), **Then** o retorno informa apenas `configured: true`, o nome do modelo ativo e a chave mascarada (`"••••••••"`), sendo impossível recuperar a chave original por requisições HTTP.
4. **Given** que o sistema gera relatórios completos de auditoria (JSON, HTML ou telas de veredito), **When** inspecionados os arquivos e respostas, **Then** nenhuma chave de API ou credencial sensível consta nos metadados ou logs.

---

### User Story 3 - Avaliação Automatizada de Requisitos Qualitativos com AI Evaluator Agent (V1.3.1) (Priority: P2)

Ao executar uma avaliação completa em projeto seguro (como a própria ferramenta `app/`), o pipeline executa o novo agente `AI Evaluator Agent` (`AIEvaluatorAgent`) para analisar o requisito `V1.3.1` (verificação de uso de sanitizadores para HTML rico/WYSIWYG e políticas de renderização contextual). O agente analisa os trechos de código mapeados, templates e dependências através de ACI estruturada e, constatando a ausência de superfícies desprotegidas ou a presença de sanitização adequada, emite o veredito `PASS` com justificativa técnica detalhada e confiança calculada. Dessa forma, requisitos que anteriormente ficavam retidos em `MANUAL_REQUIRED` são resolvidos com fundamentação automatizada, permitindo que a avaliação atinja até 100.0% de aprovação (`PASS`).

**Why this priority**: Elimina a necessidade de intervenção humana manual para auditar conformidade em requisitos qualitativos do ASVS V1 L1, elevando a taxa de aprovação de alvos seguros de 87.5% para até 100.0% com transparência e evidências rastreáveis.

**Independent Test**: Pode ser testado executando a autoavaliação da ferramenta com o motor de IA habilitado e varredura ativa: verificar que `V1.3.1` transiciona de `MANUAL_REQUIRED` para `PASS`, atingindo 100.0% de conformidade (`8/8 PASS`).

**Acceptance Scenarios**:

1. **Given** que o modelo de IA está configurado e o pipeline executa contra uma aplicação segura sem vetores de injeção de HTML rico desprotegidos, **When** o `AIEvaluatorAgent` inspeciona as superfícies de template e código para `V1.3.1`, **Then** o agente emite veredito `PASS` com justificativa técnica citando os arquivos auditados e o modelo utilizado.
2. **Given** que o modelo de IA NÃO está configurado antes do início da avaliação, **When** o pipeline atinge a etapa de verificação de `V1.3.1`, **Then** o requisito recebe o veredito `MANUAL_REQUIRED` com orientação explícita de que a configuração do modelo de IA automatiza a validação deste requisito.
3. **Given** que o `AIEvaluatorAgent` detecta uma biblioteca vulnerável ou manipulação de HTML bruto sem sanitizador comprovado, **When** emite o resultado, **Then** o requisito recebe `FAIL` acompanhado das evidências do código analisado.

---

### Edge Cases

- **Tentativa de submissão via tecla Enter no campo de URL alvo**: Se o usuário pressionar Enter dentro do input de URL sem ter marcado o checkbox de autorização, o formulário DEVE capturar o evento de submit, cancelar o disparo e focar o checkbox com erro.
- **Interrupção de rede ou chave de API revogada durante o pipeline**: Se o modelo de IA falhar durante a execução do agente no pipeline (timeout, quota excedida ou erro 401), o sistema DEVE registrar o erro sem travar o pipeline e atribuir `INCONCLUSIVE` ou `MANUAL_REQUIRED` para `V1.3.1`, documentando a falha de comunicação na justificativa sem vazar o token.
- **Chave de API pré-configurada via variável de ambiente do servidor**: Caso o servidor inicialize com chaves de ambiente seguras (`AI_MODEL_API_KEY` e `AI_MODEL_NAME`), o sistema DEVE reconhecer o status como configurado por padrão mantendo a política *write-only* (sem exibir a chave na UI) e permitindo sobrescrita temporária pelo avaliador.
- **Espaços em branco acidentais na chave de API ou no nome do modelo**: O sistema DEVE realizar trim transparente nas credenciais antes de armazenar em memória ou testar a conexão.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001 (Bloqueio de Submissão no Cliente sem Autorização DAST)**: O formulário de avaliação DEVE bloquear a submissão e o início do pipeline quando o campo de URL alvo estiver preenchido e o checkbox de autorização dinâmica estiver desmarcado.
- **FR-002 (Feedback de Acessibilidade no Bloqueio DAST)**: Ao tentar submeter o formulário em desacordo com FR-001, a interface DEVE aplicar foco no checkbox, exibir contorno visual de erro e anunciar a mensagem de bloqueio em região acessível com `aria-live="polite"`.
- **FR-003 (Rejeição HTTP 403 no Backend sem Autorização DAST)**: A rota `POST /api/runs` DEVE validar a presença de `zap_authorized == True` sempre que `target_url` for fornecida, retornando status `403 Forbidden` e impedindo a criação da entidade `Run` caso a autorização não seja confirmada.
- **FR-004 (Painel de Configuração do Modelo de IA)**: A interface DEVE disponibilizar um painel de configuração para o motor de IA contendo campo de seleção/entrada do nome do modelo e campo de entrada de chave de API mascarado (`type="password"`).
- **FR-005 (Política Write-Only de Credenciais de IA)**: O sistema DEVE armazenar a chave de API em memória de forma estritamente *write-only*. Nenhum endpoint REST PODE retornar o valor real da chave após seu envio.
- **FR-006 (Endpoint de Consulta de Status da IA Mascarado)**: O sistema DEVE disponibilizar uma consulta de status (`GET /api/ai/status`) que retorne exclusivamente se a IA está configurada (`online`/`configured`), o nome do modelo ativo e a chave no formato mascarado (`"••••••••"`).
- **FR-007 (Gravação Segura de Chave de IA)**: O sistema DEVE disponibilizar um endpoint seguro (`POST /api/ai/config`) para definir o modelo e a chave de API em tempo de execução sem persistência em texto plano no banco de dados.
- **FR-008 (Teste de Conexão com Provedor de IA)**: O sistema DEVE disponibilizar um endpoint (`POST /api/ai/test-connection`) e botão correspondente na interface para testar a comunicação com o modelo de IA, retornando sucesso com tempo de resposta em milissegundos ou falha descritiva sem expor a credencial.
- **FR-009 (Agente de Avaliação Assistida por IA - AIEvaluatorAgent)**: O sistema DEVE integrar ao pipeline multiagente o `AIEvaluatorAgent`, encarregado de analisar requisitos qualitativos que dependem de inspeção contextual (notadamente `V1.3.1`).
- **FR-010 (Resolução Automatizada do Veredito V1.3.1)**: Quando o modelo de IA estiver ativo, o `AIEvaluatorAgent` DEVE inspecionar o código e emitir o veredito correspondente (`PASS`, `FAIL` ou `INCONCLUSIVE`). Se a IA não estiver configurada, o veredito para `V1.3.1` DEVE permanecer `MANUAL_REQUIRED`.
- **FR-011 (Proteção Contra Vazamento em Relatórios e Logs)**: As saídas de relatórios exportados (HTML, JSON, PDF), logs de execução e eventos SSE NÃO PODEM conter a chave de API em texto puro.

### Key Entities *(include if feature involves data)*

- **AIServiceConfig**: Representa o estado em memória da configuração do provedor de inteligência artificial, contendo o nome do modelo (`model_name`), a chave de API segura (`api_key`, acessível internamente apenas pelos clientes de IA), indicador booleano de disponibilidade (`is_configured`) e data/hora da última validação bem-sucedida.
- **AIEvaluationRecord**: Representa a análise emitida pelo `AIEvaluatorAgent` para um requisito específico dentro de um `AssessmentRun`, compreendendo o requisito avaliado (`req_id`), o modelo de IA utilizado, a justificativa técnica elaborada, as evidências de arquivos inspecionados, o veredito atribuído (`PASS`/`FAIL`/`INCONCLUSIVE`) e o nível de confiança.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001 (Zero Execuções DAST Não Autorizadas)**: 100% das tentativas de início de avaliação com URL alvo preenchida sem o aceite do checkbox de autorização são bloqueadas no cliente e no servidor com status HTTP 403.
- **SC-002 (Eliminação Total de MANUAL_REQUIRED em Alvo Seguro)**: Em avaliações da ferramenta com análise estática, análise dinâmica ativa e motor de IA configurado, **100% dos 8 requisitos de V1 L1** recebem o veredito `PASS` (atingindo 100.0% de conformidade e 0 requisitos pendentes de revisão manual).
- **SC-003 (Zero Vazamento de Credenciais de IA)**: 100% das respostas de endpoints REST, arquivos exportados e logs registram a chave de API de IA como mascarada ou ausente, com zero ocorrências da chave original em texto puro.
- **SC-004 (Validação Imediata de Conectividade com IA)**: O teste de conexão com o modelo de IA responde em menos de 5 segundos, fornecendo confirmação clara de prontidão operacional antes de iniciar uma nova rodada de avaliação.

## Assumptions

- O usuário fornecerá uma chave de API válida compatível com provedores suportados (ex.: Google Gemini API ou compatível com protocolo padrão de IA generativa).
- As credenciais de IA configuradas via interface permanecem ativas na memória volátil da aplicação enquanto o processo do servidor backend estiver em execução.
- O requisito `V1.3.1` é o foco primário do agente de IA nesta iteração por ser o único requisito do escopo ASVS V1 L1 que exigia inspeção manual qualitativa.

