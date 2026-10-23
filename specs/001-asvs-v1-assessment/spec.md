# Feature Specification: Pipeline e Dashboard Web de Autoavaliação OWASP ASVS 5.0 (Capítulo V1 - Level 1)

**Feature Branch**: `001-asvs-v1-assessment`

**Created**: 2026-10-12

**Last Updated**: 2026-10-13

**Status**: Approved (Iteração 2 — Cobertura Obrigatória por Ferramenta Mapeada & Rigor DAST)

**Input**: User description: "Atualize a especificação da feature `001-asvs-v1-assessment` com os ajustes de precisão para o DAST (OWASP ZAP) e cálculo de vereditos dependente das ferramentas mapeadas."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Executar Avaliação Automatizada do ASVS V1 L1 com Acompanhamento em Tempo Real (Priority: P1)

Um avaliador de segurança deseja submeter o código-fonte de uma aplicação (por envio de arquivo `.zip` ou seleção de um caminho local autorizado no workspace) e, quando aplicável, informar a URL da aplicação em execução para verificação dinâmica, confirmando explicitamente a autorização de teste e escolhendo o modo de análise dinâmica (passivo *baseline* por padrão ou ativo). Ao iniciar a avaliação, o avaliador acompanha em tempo real o progresso de cada etapa do pipeline (`Scoper` → `SAST` → `DAST` → `Triage/Correlação` → `Veredito` → `Relatório`), podendo cancelar uma execução em andamento ou reexecutá-la de forma idempotente, e obtém ao final o veredito fundamentado (`PASS`, `FAIL`, `INCONCLUSIVE` ou `MANUAL_REQUIRED`) para cada um dos 8 requisitos do Capítulo V1 Nível 1, respeitando estritamente a cobertura obrigatória de todas as ferramentas mapeadas para cada requisito.

**Why this priority**: Constitui o fluxo central de valor da ferramenta, entregando a verificação automatizada ponta a ponta dos 8 requisitos em escopo com guardrails de segurança, exigência de evidência positiva e proibição de falsos `PASS` quando a etapa dinâmica não é executada.

**Independent Test**: Pode ser testado integralmente submetendo o alvo de teste deliberadamente vulnerável (*fixture*) e a própria ferramenta (com e sem análise dinâmica), acompanhando os eventos de progresso até a conclusão e validando que os 8 requisitos recebem vereditos precisos baseados nas ferramentas efetivamente executadas.

**Acceptance Scenarios**:

1. **Given** que o avaliador informa uma origem de código válida no workspace, uma URL alvo presente na lista permitida (*allowlist*), marca a confirmação de autorização e mantém o modo passivo *baseline*, **When** inicia a avaliação, **Then** o sistema executa sequencialmente `Scoper` → `SAST` → `DAST` → `Triage/Correlação` → `Veredito` → `Relatório` exibindo o progresso em tempo real e emite um veredito fundamentado para cada um dos 8 requisitos (`V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5`, `V1.3.1`, `V1.3.2`, `V1.5.1`).
2. **Given** que o pipeline avalia um requisito mapeado para verificação estática e dinâmica (`V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5` ou `V1.5.1`) onde tanto a análise estática quanto o motor de análise dinâmica executaram suas regras/plugins aplicáveis sobre a superfície relevante com zero achados ativos, **When** o veredito é consolidado, **Then** o requisito recebe `PASS` com nível de confiança `HIGH`, citando obrigatoriamente `req_id`, ambas as ferramentas utilizadas, identificadores de regras/plugins executados, evidência positiva de superfície verificada e limitações.
3. **Given** que o pipeline avalia um requisito mapeado para verificação estática e dinâmica (`V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5` ou `V1.5.1`) e a análise estática retorna zero achados ativos, ** porém** a etapa dinâmica foi ignorada (`DAST - SKIPPED`), o motor dinâmico estava desconectado ou nenhum plugin dinâmico mapeado para aquele requisito foi executado na superfície HTTP (como requisitos que dependem de plugins ativos quando executado apenas o modo passivo `baseline`), **When** o veredito é consolidado, **Then** o requisito recebe obrigatoriamente `INCONCLUSIVE` (e NUNCA `PASS`), com justificativa explícita informando que a validação dinâmica é necessária para confirmar o requisito.
4. **Given** que o pipeline avalia os requisitos mapeados exclusivamente para análise estática (`V1.3.2` e `V1.3.1`) em uma execução sem análise dinâmica (`DAST - SKIPPED`), **When** `V1.3.2` possui superfície de código verificada com zero achados ativos e `V1.3.1` não possui superfície real de entrada HTML rico/WYSIWYG com sanitizador comprovado, **Then** `V1.3.2` recebe `PASS` e `V1.3.1` recebe `MANUAL_REQUIRED` ou `INCONCLUSIVE` (nunca recebendo `PASS` por colisão com strings literais do próprio analisador).
5. **Given** que o pipeline é executado contra o alvo de teste deliberadamente vulnerável (*fixture*), **When** a etapa de veredito é concluída, **Then** todos os requisitos com vulnerabilidades plantadas recebem `FAIL` (independentemente de a etapa dinâmica ter sido executada ou ignorada) acompanhado das evidências correspondentes (`arquivo:linha` com trecho de código e/ou par `request/response`).
6. **Given** que o usuário aciona a ação de autoavaliação da própria ferramenta na interface, **When** o checkbox de autorização dinâmica estiver marcado, **Then** o formulário preserva a URL alvo informada (ou preenche automaticamente a origem atual da aplicação) para executar análise estática + dinâmica; caso o checkbox não esteja marcado, o sistema executa em modo somente estático alertando claramente que os 6 requisitos dependentes de verificação dinâmica resultarão em `INCONCLUSIVE`.
7. **Given** uma avaliação em andamento, **When** o usuário aciona o cancelamento ou solicita a reexecução posterior com os mesmos parâmetros, **Then** o cancelamento interrompe imediatamente as tarefas ativas registrando o status cancelado, e a reexecução cria uma nova avaliação consistente de forma idempotente sem corromper os dados anteriores.

---

### User Story 2 - Analisar Dashboard de Conformidade, Inspecionar Evidências e Realizar Triagem de Falsos Positivos (Priority: P2)

Após a conclusão de uma avaliação, o avaliador acessa o dashboard responsivo para visualizar os indicadores consolidados (`% PASS` sobre os 8 requisitos e contagens de `PASS`, `FAIL`, `INCONCLUSIVE` e `MANUAL_REQUIRED`), os gráficos de distribuição (rosca de vereditos e barras por seção `V1.2`, `V1.3` e `V1.5`) e a tabela filtrável dos 8 requisitos. Ao selecionar um requisito, o avaliador inspeciona seus achados deduplicados com severidade, confiança e evidência navegável (`arquivo:linha` ou `request/response`), podendo marcar ou desmarcar um achado como falso positivo mediante justificativa obrigatória registrada em trilha de auditoria, o que atualiza imediatamente o veredito e as métricas do painel respeitando a cobertura obrigatória por ferramenta mapeada.

**Why this priority**: Garante que a saída automatizada seja auditável por humanos, permitindo tratar falsos positivos com rastreabilidade completa e visualizar imediatamente o nível real de conformidade em V1 L1.

**Independent Test**: Pode ser testado carregando uma execução concluída com achados, aplicando filtros na tabela dos 8 requisitos, navegando até as evidências de código/HTTP e marcando um achado como falso positivo com justificativa para verificar o registro de auditoria e o recálculo automático do veredito.

**Acceptance Scenarios**:

1. **Given** uma avaliação concluída, **When** o avaliador abre o dashboard, **Then** visualiza os cartões de métricas (`% PASS`, `FAIL`, `INCONCLUSIVE`, `MANUAL_REQUIRED`), o gráfico de rosca de vereditos, o gráfico de barras por seção (`V1.2`, `V1.3`, `V1.5`) e a tabela dos 8 requisitos com filtros funcionais.
2. **Given** um requisito com achados identificados por múltiplas regras ou execuções sobre o mesmo ponto, **When** o avaliador abre o painel de evidências do requisito, **Then** visualiza os achados deduplicados contendo severidade, nível de confiança, regra/plugin de origem e a evidência navegável (`arquivo:linha` ou `request/response`).
3. **Given** um achado ativo classificado em um requisito com veredito `FAIL`, **When** o avaliador marca o achado como falso positivo informando uma justificativa textual válida, **Then** o sistema grava um registro de auditoria (timestamp, identificação do achado, justificativa), desconsidera o achado ativo e recalcula o veredito do requisito (`PASS` se todas as ferramentas mapeadas tiverem evidência positiva, ou `INCONCLUSIVE` se faltar cobertura dinâmica obrigatória) e o `% PASS`.
4. **Given** a tela de triagem de um achado, **When** o avaliador tenta marcá-lo como falso positivo deixando a justificativa em branco ou com menos de 5 caracteres, **Then** o sistema impede a operação e exige o preenchimento da justificativa.

---

### User Story 3 - Consultar Catálogo ASVS 5.0 (Escopo V1 L1 e Catálogo Completo V1–V17) e Equivalências 4.0 → 5.0 (Priority: P3)

> **Emenda (Feature 014)**: a tela/aba dedicada de catálogo foi removida da interface. A consulta aos 345 requisitos permanece disponível somente via API de leitura (`GET /api/requirements` e `GET /api/requirements/in-scope`) e a descrição normativa de cada requisito em escopo é exibida na aba de Resultados.

Um analista ou desenvolvedor deseja consultar os 8 requisitos avaliáveis do Capítulo V1 Nível 1 — visualizando sua seção, descrição normativa no ASVS 5.0, ferramentas e regras aplicáveis e o status de equivalência (`"confirmada"` ou `"a validar"`) com o guia de testes ASVS 4.0 — bem como explorar em modo somente leitura o catálogo completo de 345 requisitos (`V1`–`V17`, Níveis 1 a 3) para referência normativa.

**Why this priority**: Oferece transparência sobre os critérios normativos avaliados e contextualiza os 8 requisitos de V1 L1 dentro do universo completo dos 345 requisitos do OWASP ASVS 5.0.

**Independent Test**: Pode ser testado acessando a visualização de catálogo, alternando entre o filtro "Em Escopo (V1 L1 - 8 requisitos)" e "Catálogo Completo (V1–V17 - 345 requisitos)" e verificando os metadados de seção, descrição, nível e ferramentas mapeadas.

**Acceptance Scenarios**:

1. **Given** que o usuário acessa a tela de catálogo na visão "Em Escopo", **When** a listagem é carregada, **Then** são exibidos exatamente os 8 requisitos de `V1` com `L = 1` (`V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5`, `V1.3.1`, `V1.3.2`, `V1.5.1`) acompanhados de seção, descrição, ferramentas/regras aplicáveis e status de equivalência `4.0 → 5.0`.
2. **Given** que o usuário alterna para a consulta do "Catálogo Completo", **When** pesquisa ou filtra por capítulo (`V1` a `V17`) ou nível (`1`, `2`, `3`), **Then** o sistema exibe os 345 requisitos em modo somente leitura, indicando claramente quais pertencem ao escopo avaliativo ativo (`in_scope = true`) e quais são apenas catalogados (`in_scope = false`).

---

### User Story 4 - Comparar Histórico de Execuções e Exportar Relatórios (Priority: P3)

Após corrigir vulnerabilidades na aplicação avaliada ou habilitar a verificação dinâmica (DAST) em uma nova rodada do pipeline, o avaliador consulta o histórico de execuções, seleciona duas avaliações para comparar lado a lado a evolução dos vereditos e achados nos 8 requisitos, e exporta o relatório consolidado em formato JSON ou HTML estático (ou opcionalmente PDF) para compartilhamento e arquivamento de auditoria.

**Why this priority**: Permite comprovar a evolução da postura de segurança e da cobertura de verificação entre rodadas e materializar as evidências em artefatos portáveis de auditoria.

**Independent Test**: Pode ser testado selecionando duas execuções distintas no histórico para visualizar o quadro comparativo de diferenças e acionando a exportação para validar a integridade dos arquivos JSON e HTML estático gerados.

**Acceptance Scenarios**:

1. **Given** ao menos duas avaliações registradas no histórico, **When** o usuário seleciona ambas para comparação, **Then** o sistema exibe a variação de `% PASS`, a diferença de contagem por veredito e a mudança de status de cada um dos 8 requisitos (destacando melhorias, transições de `INCONCLUSIVE` para `PASS`/`FAIL`, regressões e achados resolvidos ou novos).
2. **Given** uma avaliação concluída, **When** o usuário solicita a exportação em JSON ou HTML estático, **Then** o sistema gera e entrega o arquivo completo contendo metadados da execução, métricas agregadas, tabela dos 8 vereditos com regras/evidências/limitações e trilha de auditoria de falsos positivos.

---

### Edge Cases

- **Arquivo `.zip` inválido ou malicioso**: Se o usuário enviar um arquivo corrompido, vazio, acima do tamanho limite ou contendo entradas com *path traversal* (`../`) ou links simbólicos apontando para fora do diretório de extração, o sistema DEVE rejeitar o pacote antes de iniciar o pipeline e exibir erro explicativo.
- **Caminho local fora do workspace**: Se o caminho local informado não existir ou resolver para fora da árvore autorizada do workspace, o guardrail de entrada DEVE bloquear a execução imediatamente.
- **Etapa dinâmica ignorada (`DAST - SKIPPED`) ou motor dinâmico inacessível**: Se a etapa dinâmica não for habilitada pelo usuário, se o serviço do analisador dinâmico não estiver acessível em rede, ou se a URL alvo não responder, o sistema DEVE registrar explicitamente essa condição sem forjar execução de plugins dinâmicos e DEVE atribuir `INCONCLUSIVE` a todos os requisitos sem achados ativos que dependem de cobertura dinâmica (`V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5`, `V1.5.1`).
- **Requisitos com plugins dinâmicos exclusivamente ativos em modo passivo (`baseline`)**: Quando a avaliação roda em modo passivo (`baseline`), requisitos cujos plugins dinâmicos mapeados são exclusivamente ativos (`V1.2.4`, `V1.2.5`, `V1.5.1`) não têm seus plugins dinâmicos executados; portanto, na ausência de achados estáticos, DEVEM receber `INCONCLUSIVE` explicando que o modo ativo (`active`) é necessário para comprovar a ausência de vulnerabilidade dinâmica nesses requisitos.
- **Auto-colisão de assinaturas ao analisar o próprio código da ferramenta**: Quando o avaliador submete o próprio diretório da ferramenta para autoavaliação, o mapeador de superfície NÃO PODE confundir strings literais constantes no código do próprio verificador com uso real de sanitizadores HTML (`V1.3.1`), evitando falsos vereditos `PASS`.
- **Volume elevado de achados**: Caso uma verificação gere mais de 50 achados em um requisito ou chamada, a camada de interface com os agentes DEVE truncar e paginar os resultados em blocos de no máximo 50 itens, evitando estouro de contexto ou travamento da interface.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001 (Catálogo Completo e Escopo V1 L1)**: O sistema DEVE carregar como semente inicial os 345 requisitos do catálogo OWASP ASVS 5.0 (`V1` a `V17`) marcando `in_scope = true` exclusivamente para `chapter_id = 'V1'` e `L = 1`, e disponibilizar tela e endpoint para listar detalhadamente os 8 requisitos em escopo (`V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5`, `V1.3.1`, `V1.3.2`, `V1.5.1`) com seção, descrição e ferramentas aplicáveis, além de consulta somente leitura aos 345 requisitos.
- **FR-002 (Tabela de Equivalência ASVS 4.0 → 5.0)**: O sistema DEVE manter e consultar uma tabela explícita de equivalência entre os procedimentos do guia de testes ASVS 4.0 e os 8 requisitos V1 L1 do ASVS 5.0, classificando cada mapeamento como `"confirmada"` ou `"a validar"`, sem presumir equivalência 1:1 implícita.
- **FR-003 (Configuração de Nova Avaliação e Autoavaliação)**: O sistema DEVE disponibilizar um formulário para iniciar uma nova avaliação contendo:
  1. Origem do código-fonte para análise estática (upload de arquivo `.zip` ou caminho de diretório dentro do workspace local);
  2. URL alvo da aplicação em execução para análise dinâmica;
  3. Checkbox obrigatório de confirmação explícita de autorização sobre o alvo;
  4. Seleção do modo de análise dinâmica (`baseline passivo` como opção padrão ou `ativo`);
  5. Botão de atalho para autoavaliação da própria ferramenta que preserve a URL alvo preenchida (ou preencha automaticamente a origem atual da aplicação quando o checkbox de autorização dinâmica estiver marcado), ou informe claramente no alerta de execução que uma rodada somente estática deixará como `INCONCLUSIVE` os 6 requisitos que dependem de verificação dinâmica.
- **FR-004 (Guardrails de Segurança e Validação de Entrada)**: Antes de executar qualquer ferramenta, o sistema DEVE validar todas as entradas: confinar caminhos de arquivos ao workspace, rejeitar pacotes `.zip` inseguros, exigir o checkbox de autorização e validar a URL alvo contra uma lista de alvos permitidos (*allowlist*) antes de qualquer comunicação dinâmica, devolvendo mensagens corretivas em caso de violação.
- **FR-005 (Pipeline Multiagente com Streaming de Progresso)**: O servidor DEVE executar o pipeline de avaliação em segundo plano seguindo as etapas `Scoper` → `SAST` → `DAST` → `Triage/Correlação` → `Veredito` → `Relatório`, transmitindo eventos em tempo real para a página web com o status de cada etapa, contagem parcial de achados e mensagens informativas.
- **FR-006 (Camada de Interface Agente-Computador - ACI e Conectividade Real DAST)**: Todo acesso dos agentes às ferramentas de análise estática e dinâmica DEVE ocorrer exclusivamente por meio de uma camada ACI com comandos simples e documentados, saídas resumidas e paginadas (máximo de 50 achados por chamada), retorno explícito quando não houver achados (ex.: `"0 achados para a regra X em N arquivos"`, nunca saída vazia) e execução de processos sem concatenação de comandos em *shell*. A interface dinâmica (`zap_aci`) DEVE verificar a conectividade real com o motor de análise dinâmica (OWASP ZAP) e NUNCA contabilizar uma simples requisição HTTP de *fallback* (sem o motor ZAP ativo) como execução válida de plugins dinâmicos.
- **FR-007 (Cobertura de Verificação e Ferramentas Obrigatórias para os 8 Requisitos V1 L1)**: O sistema DEVE avaliar os 8 requisitos em escopo exigindo as ferramentas declaradas no mapeamento normativo:
  - **V1.2.1** (`tools: ["semgrep", "zap"]` — Codificação contextual HTML/HTTP/XML): verificação estática de autoescape, `innerHTML` e `|safe` **E** verificação dinâmica de XSS/headers (passiva ou ativa);
  - **V1.2.2** (`tools: ["semgrep", "zap"]` — URLs dinâmicas e protocolos seguros): verificação estática de *open redirect* e esquemas `javascript:`/`data:` **E** verificação dinâmica de redirecionamento/XSS;
  - **V1.2.3** (`tools: ["semgrep", "zap"]` — JavaScript e JSON dinâmicos): verificação estática de interpolação em `<script>` e serialização JSON inline **E** verificação dinâmica;
  - **V1.2.4** (`tools: ["semgrep", "zap"]` — Consultas SQL/NoSQL parametrizadas): verificação estática de queries concatenadas/interpoladas **E** verificação dinâmica ativa de injeção de SQL;
  - **V1.2.5** (`tools: ["semgrep", "zap"]` — Proteção contra injeção de comandos de SO): verificação estática de `shell=True`/`os.system` **E** verificação dinâmica ativa de *command injection*;
  - **V1.3.1** (`tools: ["semgrep"]` + fallback manual — Sanitização de HTML rico/WYSIWYG): verificação estática de uso real de biblioteca sanitizadora sobre entrada HTML rica, emitindo `MANUAL_REQUIRED` ou `INCONCLUSIVE` quando não houver superfície real ou confirmação automatizada plena (sem falsos positivos por literais internos do scanner);
  - **V1.3.2** (`tools: ["semgrep"]` — Proibição de `eval()` e execução dinâmica): verificação estática exclusiva sobre os módulos Python/JS do projeto;
  - **V1.5.1** (`tools: ["semgrep", "zap"]` — Prevenção contra XXE em parsers XML): verificação estática de parsers XML inseguros **E** verificação dinâmica ativa de XXE.
- **FR-008 (Triagem, Deduplicação e Navegação de Evidências)**: O sistema DEVE deduplicar achados equivalentes, agrupá-los por requisito (`req_id`), exibir severidade e confiança, e permitir inspecionar a evidência concreta de cada achado (`arquivo:linha` com trecho de código para análise estática; método, URL e `request/response` para análise dinâmica).
- **FR-009 (Marcação Manual de Falsos Positivos com Auditoria)**: O usuário DEVE poder marcar ou reverter manualmente qualquer achado como falso positivo mediante justificativa obrigatória; o sistema DEVE registrar cada operação em trilha de auditoria persistente e recalcular imediatamente o veredito do requisito afetado.
- **FR-010 (Emissão de Veredito Dependente das Ferramentas Mapeadas)**: O sistema DEVE atribuir a cada um dos 8 requisitos o veredito `PASS`, `FAIL`, `INCONCLUSIVE` ou `MANUAL_REQUIRED` segundo as regras estritas do Princípio II da Constituição (v1.1.0):
  1. Se houver qualquer achado ativo (`active_findings_count > 0` em SAST ou DAST) → **`FAIL`**;
  2. Para requisitos mapeados para `["semgrep", "zap"]` (`V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5`, `V1.5.1`): se houver `0` achados ativos, o veredito **`PASS`** exige obrigatoriamente evidência positiva estática (`has_sast_positive == True`) **E** evidência positiva dinâmica real do OWASP ZAP (`has_dast_positive == True`). Caso o DAST tenha sido ignorado (`SKIPPED`), o daemon ZAP esteja inacessível ou nenhum plugin ZAP mapeado para o requisito tenha sido executado, o veredito DEVE ser **`INCONCLUSIVE`**;
  3. Para requisitos mapeados exclusivamente para `["semgrep"]`: `V1.3.2` recebe **`PASS`** apenas com evidência positiva estática (`has_sast_positive == True`), e `V1.3.1` recebe **`MANUAL_REQUIRED`** (ou `INCONCLUSIVE`) quando não houver superfície real de entrada HTML rico/WYSIWYG com sanitizador comprovadamente aplicado.
- **FR-011 (Dashboard, Gráficos e Comparação entre Execuções)**: A interface DEVE apresentar:
  1. Cartões de métricas agregadas (`% PASS` sobre 8 requisitos e contagens de `PASS`, `FAIL`, `INCONCLUSIVE` e `MANUAL_REQUIRED`);
  2. Gráfico de rosca (*donut*) de distribuição de vereditos e gráfico de barras por seção (`V1.2`, `V1.3`, `V1.5`);
  3. Tabela dos 8 requisitos com filtros por veredito, seção e ferramenta;
  4. Painel/modal detalhado de evidências por achado;
  5. Histórico de avaliações salvas e modo de comparação entre duas execuções selecionadas.
- **FR-012 (Exportação de Relatório)**: O sistema DEVE permitir exportar o relatório completo de uma avaliação nos formatos **JSON** e **HTML estático** (com suporte a impressão **PDF**).
- **FR-013 (Timeouts, Cancelamento e Idempotência)**: O sistema DEVE impor limites de tempo por etapa de execução, permitir o cancelamento limpo pelo usuário a qualquer momento e garantir que a reexecução de uma avaliação seja idempotente.
- **FR-014 (Acessibilidade WCAG 2.2 AA e Temas Claro/Escuro)**: A aplicação web DEVE cumprir os critérios de acessibilidade WCAG 2.2 Nível AA, suportar operação completa via teclado e oferecer alternância entre tema claro e tema escuro.
- **FR-015 (Alvo de Teste Vulnerável e Autoverificação Precisa)**: O repositório DEVE conter um alvo de teste deliberadamente vulnerável (*fixture*) para validar a detecção automatizada de `FAIL` nos 8 requisitos em escopo, e o próprio código da ferramenta DEVE resultar em `0 FAIL` quando submetido ao pipeline, distinguindo claramente o que foi comprovado por SAST (`V1.3.2` → `PASS`) do que requer DAST (`V1.2.1`–`V1.2.5`, `V1.5.1` → `INCONCLUSIVE` quando executado sem ZAP ativo) ou revisão manual (`V1.3.1` → `MANUAL_REQUIRED`).

### Key Entities *(include if feature involves data)*

- **Requirement (Requisito ASVS)**: Item do catálogo normativo ASVS 5.0 (345 registros, `V1`–`V17`), com atributos `chapter_id`, `chapter_name`, `section_id`, `section_name`, `req_id`, `req_description`, `level` (`L`) e flag `in_scope` (`true` apenas para os 8 requisitos `V1` com `L = 1`).
- **RuleMapping & EquivalenceRecord (Mapeamento de Regras e Equivalência 4.0 → 5.0)**: Estrutura que relaciona cada `req_id` em escopo à lista obrigatória de ferramentas (`required_tools`: `["semgrep", "zap"]` ou `["semgrep"]`), regras estáticas, plugins dinâmicos passivos/ativos, critérios de superfície/cobertura e referências do guia de testes ASVS 4.0 com status `"confirmada"` ou `"a validar"`.
- **AssessmentRun (Execução de Avaliação)**: Registro de uma rodada do pipeline contendo parâmetros de entrada (caminho/arquivo de código, URL alvo, confirmação de autorização, modo passivo/ativo), status da execução, progresso por etapa, timestamps e métricas agregadas (`% PASS` e totais por veredito).
- **Finding (Achado)**: Vulnerabilidade ou alerta normalizado e deduplicado associado a uma `AssessmentRun` e a um `req_id`, contendo ferramenta geradora, ID da regra/plugin, severidade, confiança, evidência (`arquivo:linha`/trecho ou `request/response`) e estado de falso positivo.
- **FalsePositiveAudit (Auditoria de Falso Positivo)**: Registro imutável vinculado a um `Finding` que documenta quem/quando marcou ou desmarcou o achado como falso positivo e a justificativa obrigatória fornecida.
- **RequirementVerdict (Veredito do Requisito)**: Resultado consolidado de cada um dos 8 requisitos em uma `AssessmentRun` (`PASS`, `FAIL`, `INCONCLUSIVE`, `MANUAL_REQUIRED`), incluindo lista de ferramentas exigidas vs. ferramentas efetivamente executadas, regras/plugins executados, evidências positivas e negativas, cobertura declarada, nível de confiança, justificativa e limitações.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001 (Eficácia de Detecção em Alvo Vulnerável)**: Em execuções contra o alvo de teste deliberadamente vulnerável (*fixture*), o pipeline identifica 100% dos cenários de falha plantados para o escopo V1 L1, emitindo o veredito `FAIL` com evidência exata (`arquivo:linha` ou `request/response`) para cada um dos 8 requisitos.
- **SC-002 (Rigor da Cobertura Obrigatória por Ferramenta Mapeada)**: Em execuções onde a etapa dinâmica não é realizada (`DAST - SKIPPED`) ou o motor dinâmico não executa os plugins mapeados para o requisito, **0%** dos 6 requisitos que dependem de verificação dinâmica (`V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5`, `V1.5.1`) recebem `PASS`; 100% deles (quando sem achados estáticos) recebem obrigatoriamente `INCONCLUSIVE`.
- **SC-003 (Autoconformidade V1 L1 e Fidelidade de Escopo)**: Ao submeter o próprio código-fonte da ferramenta a uma execução somente estática, 100% dos 8 requisitos resultam livres de vulnerabilidades (`0 FAIL`), sendo `V1.3.2` classificado como `PASS`, `V1.3.1` como `MANUAL_REQUIRED` e os 6 requisitos dependentes de DAST como `INCONCLUSIVE` (podendo transitar para `PASS` quando o motor dinâmico executa os plugins correspondentes contra a aplicação em execução).
- **SC-004 (Responsividade do Progresso e Controle de Execução)**: 100% das mudanças de etapa do pipeline são apresentadas na interface em até 2 segundos após sua ocorrência no servidor, e o acionamento de cancelamento encerra a execução em andamento em no máximo 5 segundos.
- **SC-005 (Produtividade na Triagem, Comparação e Exportação)**: Um avaliador consegue inspecionar os 8 vereditos, filtrar achados, registrar um falso positivo auditado com recálculo imediato de métricas, comparar duas execuções históricas e exportar o relatório em JSON e HTML estático em menos de 3 minutos.
- **SC-006 (Controle de Escala na Saída de Ferramentas)**: 100% das consultas de resultados realizadas pelos agentes retornam no máximo 50 achados por página e apresentam mensagem textual explícita quando a contagem de achados é igual a zero.
- **SC-007 (Conformidade de Acessibilidade e Temas)**: 100% das visualizações da página web atendem aos critérios de contraste, semântica, foco visível e operação por teclado do padrão WCAG 2.2 Nível AA, tanto no tema claro quanto no tema escuro.

## Out of Scope

- Avaliação ativa ou emissão de vereditos para os capítulos `V2` a `V17` e para os Níveis `L = 2` e `L = 3` do ASVS 5.0 (esses itens permanecem estritamente em modo de consulta somente leitura no catálogo).
- Refatoração ou correção automática de código-fonte (*auto-remediation* / geração de patches).
- Avaliação automatizada de requisitos puramente organizacionais, documentais ou de governança externa ao código e à aplicação em execução.

## Assumptions

- O ambiente de execução é local ou controlado por equipe de segurança autorizada, onde o usuário possui acesso legítimo ao código-fonte avaliado (via diretório no workspace ou pacote `.zip` de até 100 MB) e aos alvos web listados na *allowlist*.
- O usuário pode executar uma avaliação fornecendo apenas a origem do código-fonte (sem URL alvo em execução) quando desejar realizar somente a verificação estática; nesse cenário, a etapa dinâmica é registrada como ignorada (`SKIPPED`) e os 6 requisitos que exigem confirmação dinâmica (`tools: ["semgrep", "zap"]`) recebem obrigatoriamente `INCONCLUSIVE` caso não possuam falhas estáticas, jamais recebendo `PASS` sem a execução real dos plugins dinâmicos mapeados.
- A exportação de relatórios nos formatos JSON e HTML estático é obrigatória para todas as execuções concluídas, enquanto a exportação direta em PDF é atendida via folha de estilo de impressão a partir do HTML/dashboard.
