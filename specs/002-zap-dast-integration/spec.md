# Feature Specification: Integração Fim a Fim de Análise Dinâmica (DAST) e Eliminação de Falsos Inconclusivos no ASVS 5.0 (Capítulo V1 - Level 1)

**Feature Branch**: `002-zap-dast-integration`

**Created**: 2026-10-13

**Status**: Approved

**Input**: User description: "SPECIFY_FEATURE_DIRECTORY=specs/002-zap-dast-integration — Corrigir a execução fim a fim do OWASP ZAP (DAST) e eliminar os falsos INCONCLUSIVE nos requisitos V1 L1 com diagnóstico prévio de conectividade na interface, ciclo DAST sincronizado (semeadura, Spider, Passive Scan e Active Scan), resolução transparente de alvos localhost entre host e container e autoavaliação integrada."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Executar Ciclo Completo e Sincronizado de Verificação Dinâmica (DAST) sem Falsos Inconclusivos (Priority: P1)

Um avaliador de segurança inicia uma avaliação do Capítulo V1 Nível 1 informando o código-fonte e a URL da aplicação em execução, confirmando a autorização de teste dinâmico e selecionando o modo de varredura (`Baseline Passivo` ou `Active Scan`). O sistema semeia a URL alvo na árvore de endereços do motor dinâmico, aguarda a conclusão integral do rastreamento de links (Spider), aguarda o processamento completo da fila de análise passiva e, quando em modo ativo, aguarda a conclusão integral dos testes ativos de injeção antes de coletar os alertas. Dessa forma, todos os requisitos mapeados para verificação estática + dinâmica (`V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5`, `V1.5.1`) têm seus testes dinâmicos comprovadamente executados e recebem `PASS` (com confiança `HIGH`) quando livres de vulnerabilidades, eliminando falsos resultados `INCONCLUSIVE` decorrentes de coleta prematura ou falha de roteamento local.

**Why this priority**: Resolve diretamente o problema central relatado pelo usuário: garante que o motor dinâmico realmente execute seus plugins até o fim e alcance a aplicação local, permitindo que os requisitos dependentes de verificação dinâmica saiam do estado `INCONCLUSIVE` para `PASS` ou `FAIL` com evidência real.

**Independent Test**: Pode ser testado de ponta a ponta submetendo uma aplicação em execução local em modo `Baseline Passivo` e em modo `Active Scan`, verificando no log de eventos em tempo real a progressão completa do rastreamento e da varredura dinâmica e confirmando a transição dos requisitos de `INCONCLUSIVE` para `PASS` (em alvo seguro) ou `FAIL` (em alvo vulnerável).

**Acceptance Scenarios**:

1. **Given** que o motor de análise dinâmica está disponível e o avaliador submete o código da própria ferramenta junto à URL da aplicação em execução com autorização confirmada e modo `Active Scan`, **When** o pipeline conclui todas as etapas (`Scoper` → `SAST` + `DAST` → `Triage` → `Veredito` → `Relatório`), **Then** o motor dinâmico semeia a URL, aguarda 100% do Spider, 0 registros pendentes na fila passiva e 100% da varredura ativa, resultando em `PASS` (confiança `HIGH`) para os 6 requisitos estático+dinâmicos (`V1.2.1`–`V1.2.5`, `V1.5.1`) e `PASS` para `V1.3.2` (`87.5% PASS`, `0 INCONCLUSIVE`, `0 FAIL` e `1 MANUAL_REQUIRED` para `V1.3.1`).
2. **Given** que o avaliador executa a mesma avaliação selecionando o modo `Baseline Passivo`, **When** o pipeline conclui o rastreamento e o esvaziamento da fila passiva, **Then** os 3 requisitos cobertos por regras passivas (`V1.2.1`, `V1.2.2`, `V1.2.3`) e o requisito puramente estático (`V1.3.2`) recebem `PASS` (`50.0% PASS`), enquanto os 3 requisitos que exigem payloads ativos de injeção (`V1.2.4`, `V1.2.5`, `V1.5.1`) recebem `INCONCLUSIVE` com explicação clara de que o modo ativo é necessário para comprová-los.
3. **Given** que o motor dinâmico executa isolado em ambiente containerizado enquanto a aplicação avaliada executa na máquina hospedeira (`localhost` ou `127.0.0.1`), **When** o avaliador informa a URL local (`http://localhost:8000`) e inicia a avaliação, **Then** o sistema resolve de forma transparente o endereço de rede entre o container e o hospedeiro, alcançando a aplicação sem erro de conexão recusada e testando efetivamente a superfície HTTP.

---

### User Story 2 - Diagnosticar Conectividade do Motor Dinâmico em Tempo Real na Interface (Priority: P2)

Antes de iniciar uma avaliação na página web, o avaliador visualiza imediatamente no painel de configuração um indicador de saúde do motor de análise dinâmica mostrando se ele está `ONLINE` (exibindo a versão e o endereço conectado) ou `OFFLINE` (exibindo instruções objetivas para iniciá-lo), com botão para revalidar a conexão sem recarregar a página. Caso o avaliador tente iniciar uma avaliação com URL alvo preenchida enquanto o motor dinâmico estiver `OFFLINE`, a interface alerta explicitamente que a etapa dinâmica não poderá validar os 6 requisitos dependentes de DAST.

**Why this priority**: Elimina a falha silenciosa em que o usuário acredita que a verificação dinâmica está rodando quando, na verdade, o serviço dinâmico está desligado ou inacessível, prevenindo rodadas inteiras desperdiçadas com resultados `INCONCLUSIVE`.

**Independent Test**: Pode ser testado abrindo a tela "Nova Avaliação & Pipeline" com o serviço dinâmico ligado e desligado, acionando o botão de verificação de status e validando a atualização imediata do indicador visual e das mensagens de orientação.

**Acceptance Scenarios**:

1. **Given** que o avaliador abre a tela de configuração de avaliação com o serviço dinâmico em execução, **When** a página consulta o estado do motor dinâmico, **Then** o indicador exibe o status `ONLINE`, a versão do motor e o endereço conectado.
2. **Given** que o serviço de análise dinâmica não está em execução ou está inacessível na rede, **When** a página consulta o estado ou o avaliador clica em "Verificar Conexão DAST", **Then** o indicador exibe o status `OFFLINE` com o comando de inicialização do serviço e avisa que execuções sem o motor dinâmico marcarão os requisitos `V1.2.1`–`V1.2.5` e `V1.5.1` como `INCONCLUSIVE`.

---

### User Story 3 - Executar Autoavaliação Completa (SAST + DAST) com Um Clique e Transparência de Modo (Priority: P2)

O avaliador deseja validar a conformidade da própria ferramenta acionando o botão "Autoavaliar Própria Ferramenta (`app/`)". Ao clicar no botão, o formulário preenche automaticamente o caminho de código (`app`), a URL da aplicação em execução, marca a confirmação de autorização local e, caso o motor dinâmico esteja `ONLINE`, seleciona o modo de varredura capaz de comprovar todos os requisitos automatizáveis (`Active Scan`), explicando claramente no formulário quais requisitos são cobertos por cada modo (`Baseline Passivo` vs. `Active Scan`).

**Why this priority**: Torna imediata a verificação completa da própria ferramenta sem exigir que o usuário preencha manualmente a URL, marque o checkbox e troque o modo de varredura a cada teste.

**Independent Test**: Pode ser testado clicando no botão "Autoavaliar Própria Ferramenta (`app/`)" na interface e verificando o preenchimento automático dos campos de análise dinâmica e a execução das etapas `SAST` e `DAST` no painel de progresso em tempo real.

**Acceptance Scenarios**:

1. **Given** que o avaliador está na tela de nova avaliação e o motor dinâmico está `ONLINE`, **When** clica em "Autoavaliar Própria Ferramenta (`app/`)", **Then** o sistema preenche automaticamente a origem `app`, a URL atual da aplicação, marca o checkbox de autorização dinâmica, seleciona o modo `Active Scan` e inicia o pipeline executando tanto `SAST` quanto `DAST`.
2. **Given** que o avaliador altera o seletor de modo entre `Baseline Passivo` e `Active Scan`, **When** visualiza a legenda do campo na interface, **Then** compreende imediatamente que `Baseline Passivo` cobre dinamicamente `V1.2.1`, `V1.2.2` e `V1.2.3`, enquanto `Active Scan` adiciona a cobertura dinâmica ativa exigida por `V1.2.4`, `V1.2.5` e `V1.5.1`.

---

### Edge Cases

- **Aplicação alvo em `localhost` inacessível de dentro do container do motor dinâmico**: Quando o avaliador informa `http://localhost:8000` ou `http://127.0.0.1:8000` e o motor dinâmico roda em container isolado, a tentativa direta de acesso a `localhost` dentro do container falha; o sistema DEVE detectar essa condição e redirecionar transparentemente o alvo do scan para o endereço de ponte do hospedeiro (`host.docker.internal` ou gateway equivalente) mantendo a validação contra a lista de origens permitidas (*allowlist*).
- **URL raiz sem links hipertextuais descobertos pelo Spider**: Se a página inicial ou endpoint informado retornar resposta válida mas o rastreador (Spider) encontrar 0 links filhos adicionais, o sistema DEVE preservar a URL raiz semeada como superfície verificada (`urls_tested >= 1`), evitando que a contagem de URLs fique zerada e gere falso `INCONCLUSIVE`.
- **Varredura ativa (`Active Scan`) em aplicação sem formulários tradicionais**: Se a árvore de sites do motor dinâmico possuir apenas a URL raiz ou endpoints sem parâmetros de query/formulário e o comando de varredura ativa retornar aviso de ausência de parâmetros injetáveis, o sistema DEVE considerar a árvore semeada e inspecionada pelo motor dinâmico como verificada (0 alertas ativos nas rotas existentes), sem abortar a etapa DAST.
- **Fila de análise passiva lenta ou longa**: Durante o aguardo do esvaziamento da fila passiva (`recordsToScan`) ou do progresso do Spider/Active Scan, o sistema DEVE respeitar um limite de tempo máximo por operação para evitar bloqueio infinito da etapa DAST, registrando nos eventos em tempo real o percentual de evolução.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001 (Verificação de Status do Motor Dinâmico)**: O sistema DEVE disponibilizar uma consulta de diagnóstico do motor de análise dinâmica que verifique em tempo real sua conectividade, recupere sua versão quando acessível e informe o endereço configurado e os hosts permitidos na *allowlist*.
- **FR-002 (Indicador Visual de Saúde DAST na Interface)**: A página de configuração de avaliação DEVE exibir um indicador visual claro (`ONLINE` / `OFFLINE`) do motor de análise dinâmica, atualizável sob demanda pelo usuário sem recarregar a página, exibindo orientações de inicialização quando o motor estiver `OFFLINE`.
- **FR-003 (Semeadura Explícita da URL Alvo)**: Antes de disparar o rastreador (Spider) ou a varredura dinâmica, o sistema DEVE requisitar que o motor dinâmico acesse e registre explicitamente a URL alvo raiz em sua árvore de sites, garantindo que a superfície HTTP inicial esteja presente para análise passiva e ativa.
- **FR-004 (Resolução Transparente de Alvo Local entre Host e Container)**: Quando a URL alvo autorizada utilizar `localhost` ou `127.0.0.1` e o motor dinâmico em container não conseguir alcançá-la diretamente como `localhost`, o adaptador dinâmico DEVE traduzir automaticamente o host para o endereço de ponte do hospedeiro (`host.docker.internal`), mantendo a porta e o caminho originais e preservando a conformidade com a *allowlist*.
- **FR-005 (Sincronização Completa do Spider por Polling)**: Ao iniciar o Spider no motor dinâmico, o sistema DEVE monitorar periodicamente o percentual de progresso até atingir 100% (ou o limite de tempo da etapa) antes de consultar a lista final de URLs descobertas, garantindo no mínimo 1 URL verificada quando a URL raiz responder com sucesso.
- **FR-006 (Sincronização da Fila de Análise Passiva)**: Após o término do Spider, o sistema DEVE aguardar até que a contagem de registros pendentes na fila do analisador passivo chegue a zero (`recordsToScan == 0` ou limite de tempo da etapa) antes de coletar alertas em modo `baseline` ou `active`.
- **FR-007 (Sincronização Completa da Varredura Ativa por Polling)**: Quando o modo `active` for selecionado e autorizado, o sistema DEVE iniciar a varredura ativa sobre a URL semeada e monitorar periodicamente o percentual de progresso até atingir 100% (ou o limite de tempo da etapa) antes de coletar os alertas e consolidar os plugins executados para os requisitos `V1.2.1`–`V1.2.5` e `V1.5.1`.
- **FR-008 (Atalho de Autoavaliação Completa SAST + DAST)**: O botão "Autoavaliar Própria Ferramenta (`app/`)" na interface DEVE preencher o caminho `app`, definir a URL alvo com a origem atual da aplicação em execução, marcar a autorização de teste dinâmico e, quando o motor dinâmico estiver `ONLINE`, selecionar o modo `active` por padrão para permitir a validação completa dos requisitos estáticos e dinâmicos.
- **FR-009 (Transparência de Cobertura por Modo DAST na Interface)**: O formulário de nova avaliação DEVE informar explicitamente ao usuário quais requisitos do escopo `V1 L1` são validados dinamicamente no modo `Baseline Passivo` (`V1.2.1`, `V1.2.2`, `V1.2.3`) e quais exigem o modo `Active Scan` (`V1.2.4`, `V1.2.5`, `V1.5.1`).
- **FR-010 (Configuração de Rede do Serviço Dinâmico Containerizado)**: A definição de infraestrutura containerizada do serviço de análise dinâmica DEVE mapear o endereço de ponte do hospedeiro (`host.docker.internal`) para o gateway do host, permitindo que o container alcance aplicações executando nas portas locais da máquina hospedeira.

### Key Entities *(include if feature involves data)*

- **DASTEngineStatus (Estado de Conectividade do Motor Dinâmico)**: Representa a saúde operacional do serviço de análise dinâmica no momento da consulta, contendo indicador booleano de disponibilidade (`online`), versão do motor (`version`), endereço base configurado (`zap_base_url`), lista de hosts autorizados (`allowed_hosts`) e mensagem diagnóstica (`message`).
- **DASTScanSession (Sessão Sincronizada de Varredura Dinâmica)**: Representa o ciclo completo executado contra uma URL alvo para um `AssessmentRun`, compreendendo a URL original informada pelo usuário, a URL efetivamente resolvida para alcance a partir do container (`resolved_target_url`), o identificador e progresso final do Spider (`0`–`100%`), a drenagem da fila passiva (`records_to_scan == 0`), o identificador e progresso final da varredura ativa (`0`–`100%`, quando `mode == "active"`) e o mapa de plugins efetivamente executados por `req_id`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001 (Eliminação de Falsos Inconclusivos em Autoavaliação Completa)**: Ao executar a autoavaliação da própria ferramenta com análise estática e análise dinâmica em modo ativo (`Active Scan`) contra a aplicação em execução e com o motor dinâmico `ONLINE`, **100% dos 6 requisitos que exigem cobertura estática + dinâmica** (`V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5`, `V1.5.1`) e o requisito estático `V1.3.2` recebem o veredito `PASS` (`87.5% PASS` no escopo de 8 requisitos, `0 FAIL`, `0 INCONCLUSIVE` e `1 MANUAL_REQUIRED` para `V1.3.1`).
- **SC-002 (Precisão no Modo Baseline Passivo)**: Ao executar a autoavaliação da própria ferramenta com análise dinâmica em modo passivo (`Baseline Passivo`), exatamente **4 dos 8 requisitos** (`V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.3.2`) recebem `PASS` (`50.0% PASS`), `1` recebe `MANUAL_REQUIRED` (`V1.3.1`) e apenas os `3` requisitos que dependem exclusivamente de payloads ativos (`V1.2.4`, `V1.2.5`, `V1.5.1`) recebem `INCONCLUSIVE`.
- **SC-003 (Visibilidade Imediata de Conectividade DAST)**: 100% das aberturas da tela de avaliação ou cliques no botão de verificação exibem o status real (`ONLINE` ou `OFFLINE`) do motor dinâmico em até 2 segundos.
- **SC-004 (Alcance Transparente de Alvos Locais)**: 100% das avaliações dinâmicas autorizadas apontando para `localhost` ou `127.0.0.1` na máquina hospedeira conseguem alcançar a aplicação alvo a partir do motor dinâmico em container sem exigir que o usuário descubra ou digite endereços de IP internos da rede de containers.

## Assumptions

- O motor de análise dinâmica pode estar em execução via container local mapeado na porta padrão (`8090` no host apontando para `8080` no container) ou no endereço definido pela variável de ambiente `ZAP_BASE_URL`.
- Os artefatos da especificação anterior (`specs/001-asvs-v1-assessment/`) permanecem preservados como registro histórico da Iteração 1/2, enquanto toda a documentação técnica, plano e lista de tarefas desta nova iteração residem exclusivamente em `specs/002-zap-dast-integration/`.

