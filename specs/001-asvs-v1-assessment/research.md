# Phase 0 Research: Pipeline e Dashboard Web de Autoavaliação OWASP ASVS 5.0 (V1 L1)

**Feature**: `001-asvs-v1-assessment`  
**Date**: 2026-10-12  
**Status**: Completed (0 `NEEDS CLARIFICATION` remaining)

---

## 1. Formato de Saída do Semgrep: SARIF vs. JSON Nativo

- **Decision**: Executar o Semgrep CLI gerando saída primária em **SARIF 2.1.0** (`--sarif`), com suporte secundário ao JSON nativo (`--json`) apenas para telemetria de arquivos inspecionados (`paths.scanned`) quando necessário, ou extraindo a lista de arquivos escaneados via `workspace_aci` + invocação estruturada. Na prática, o `semgrep_aci.py` utilizará `--json` ou `--sarif` de forma que o parser normalize os resultados para o schema interno Pydantic, priorizando **SARIF 2.1.0** como artefato auditável persistido em disco e combinando metadados de cobertura de arquivos.
- **Rationale**:
  1. O padrão **SARIF (OASIS Static Analysis Results Interchange Format v2.1.0)** é exigido pela Constituição (Princípio V) e pela especificação de fontes de dados, fornecendo estrutura padronizada para `ruleId`, `message`, `locations[].physicalLocation` (`artifactLocation.uri`, `region.startLine`, `region.endLine`, `region.snippet.text`), `fingerprints` (útil para deduplicação determinística na triagem) e `properties.tags` / severidade.
  2. Para atender à **Regra da Evidência Positiva** (Princípio II), precisamos comprovar não apenas "zero achados", mas também "quais regras rodaram e sobre quantos/quais arquivos relevantes". Combinar o artefato SARIF com a contagem explícita de arquivos escaneados por linguagem/superfície (`Scoper` + `semgrep_aci`) garante que `"0 achados para a regra X em N arquivos"` seja sempre determinístico.
- **Alternatives considered**:
  - *Apenas JSON proprietário do Semgrep (`--json`)*: Rejeitado como formato único de artefato porque perde interoperabilidade com ferramentas de auditoria SARIF e contraria a preferência explícita da especificação por SARIF.
  - *Texto plano (`stdout` padrão do Semgrep)*: Rejeitado por exigir parsing frágil via expressões regulares e dificultar a extração exata de snippets e fingerprints.

---

## 2. OWASP ZAP: Modo Baseline Passivo vs. Scan Ativo e Integração com Daemon

- **Decision**: Executar o **OWASP ZAP em contêiner Docker em modo daemon** (`zap.sh -daemon -host 0.0.0.0 -port 8080`), acessado a partir de `app/aci/zap_aci.py` via chamadas **REST API assíncronas com `httpx`** (com suporte compatível a `python-owasp-zap-v2.4`). O modo **Baseline Passivo** (`spider` tradicional + espera pela fila do `pscan` passivo sem enviar payloads de ataque) é o padrão obrigatório (`default`). O **Modo Ativo** (`ascan` restrito apenas às políticas/plugins mapeados para `V1 L1`) permanece desabilitado por padrão e exige tanto `authorized = True` quanto validação de `target_url` na `allowlist`.
- **Rationale**:
  1. **Segurança da própria ferramenta (Princípio IV)**: O scan passivo inspeciona cabeçalhos HTTP, respostas HTML/JSON/XML e parâmetros descobertos pelo Spider sem injetar payloads destrutivos. O modo ativo envia payloads reais (XSS, SQLi, Command Injection, XXE) e só deve ocorrer mediante escolha explícita do avaliador, checkbox de autorização assinado e URL pertencente à `allowlist` (ex.: `http://vulnerable-app:8000`, `http://localhost:*`, `http://127.0.0.1:*`).
  2. **Uso de `httpx` contra a API REST do ZAP (`/JSON/...`)**: Evita bloqueio do loop de eventos assíncrono do FastAPI/SSE, permite timeouts granulares por requisição, fácil mock em testes unitários (`pytest-asyncio`) e controle fino sobre quais scanners ativos (`ascan/action/enableScanners`) pertencem exclusivamente aos requisitos `V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5` e `V1.5.1` (inspirado no arquivo `ASVS.policy` do repositório `BlazingWind/OWASP-ASVS-4.0-testing-guide`).
- **Alternatives considered**:
  - *Executar container efêmero `zap-baseline.py` a cada run via Docker-in-Docker*: Rejeitado por adicionar alto overhead de inicialização (15–30s por execução) e exigir montagem insegura do socket Docker (`/var/run/docker.sock`) dentro do container da aplicação web.
  - *Habilitar Active Scan Completo (todas as regras ZAP) quando o modo ativo for selecionado*: Rejeitado por aumentar drasticamente o tempo de execução e gerar alertas fora do escopo `V1 L1`. Apenas os IDs de plugins mapeados em `config/req_tool_mapping.yaml` são ativados.

---

## 3. Estratégia de Truncamento, Paginação e Feedback Informativo nas ACIs (SWE-agent)

- **Decision**: Implementar três módulos ACI (`app/aci/workspace_aci.py`, `app/aci/semgrep_aci.py`, `app/aci/zap_aci.py`) onde cada comando retorna um objeto estruturado (`ACIResult[T]`) contendo:
  - `summary_message: str` (sempre preenchida; ex.: `"0 achados para a regra v1-2-4-sqli em 14 arquivos Python"` ou `"Página 1/3 (mostrando 50 de 128 achados para V1.2.1)"`);
  - `items: list[T]` limitado a **`MAX_PAGE_SIZE = 50`** registros por chamada;
  - `page: int`, `page_size: int = 50`, `total_items: int`, `total_pages: int`, `has_next: bool`;
  - Truncamento de trechos de código (`snippet`) a no máximo **20 linhas** (ou 1.000 caracteres) e corpos HTTP (`request/response`) a **2.048 caracteres** nas listagens, reservando a inspeção detalhada ao comando `show_evidence(evidence_id)`.
- **Rationale**:
  1. Conforme demonstrado por Yang et al. (*SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering*), despejar saídas brutas (como milhares de linhas de SARIF ou dumps HTTP completos do ZAP) degrada a capacidade decisória do agente e esgota a janela de contexto.
  2. Comandos silenciosos (retorno vazio `""` ou `[]` sem contexto) induzem agentes a repetir chamadas ou presumir falha da ferramenta. Retornar mensagens explícitas com o número de arquivos ou URLs inspecionados fornece a base para a **Regra da Evidência Positiva** (diferenciando "regra executada em 12 arquivos com 0 alertas" de "0 arquivos encontrados para a linguagem").
  3. Toda invocação de comando ACI é gravada na tabela `ToolCall` (`run_id`, `agent_name`, `command`, `args_json`, `duration_ms`, `status`, `output_summary`).
- **Alternatives considered**:
  - *Retornar todos os achados em memória e deixar o agente filtrar*: Rejeitado por violar diretamente o Princípio III da Constituição.
  - *Truncar silenciosamente sem metadados de paginação*: Rejeitado porque impediria a triagem e a contagem exata de vulnerabilidades em alvos ruidosos.

---

## 4. Política de Histórico dos Agentes e Persistência de Estado

- **Decision**: Adotar uma arquitetura **orientada a estado em banco de dados (`asvs.db`) com colapso de observações antigas**:
  1. Os 7 agentes (`Orchestrator`, `Scoper`, `SAST Agent`, `DAST Agent`, `Triage/Correlation Agent`, `Verdict Agent`, `Reporter Agent`) trocam dados exclusivamente por meio de contratos tipados **Pydantic** (`AgentInput` / `AgentOutput`) e registros persistidos em SQLite (`Run`, `ToolCall`, `Finding`, `Evidence`, `Verdict`).
  2. Dentro do ciclo de execução de um agente, mantém-se apenas uma janela deslizante das últimas `K = 5` observações detalhadas da ACI; todas as observações anteriores são colapsadas em uma linha de resumo (`"[Observação colapsada: comando X executado em T ms -> resumo Y]"`).
- **Rationale**:
  1. Segue fielmente o mecanismo de *history folding/collapsing* do SWE-agent (Yang et al.), mantendo o histórico enxuto e previsível.
  2. Como todo achado, evidência e chamada de ferramenta é imediatamente persistido no SQLite via SQLModel, o pipeline torna-se resiliente a falhas, auditável a posteriori e capaz de transmitir eventos SSE em tempo real sem depender de memória volátil de conversação.
- **Alternatives considered**:
  - *Manter o log completo de todas as etapas concatenado em memória*: Rejeitado por crescimento quadrático de contexto e perda de rastreabilidade estruturada.

---

## 5. Equivalência ASVS 4.0 Testing Guide → ASVS 5.0 (Capítulo V1 Level 1)

- **Decision**: Documentar em `docs/mapping_4_0_to_5_0.md` e parametrizar em `config/req_tool_mapping.yaml` o mapeamento não-1:1 entre o Capítulo **V5** do OWASP ASVS 4.0 (e artefatos do guia `BlazingWind/OWASP-ASVS-4.0-testing-guide`, como `ASVS.policy` e scripts ZAP) e o Capítulo **V1 (Level 1)** do OWASP ASVS 5.0:

| ASVS 5.0 `req_id` | Seção 5.0 | Referência ASVS 4.0 (Testing Guide) | Status da Equivalência | Cobertura no Pipeline |
| :--- | :--- | :--- | :--- | :--- |
| **V1.2.1** | V1.2 Injection Prevention | V5.3.1, V5.3.3 (Output encoding HTML/XML/CSS/Headers & XSS) | `a validar` *(consolida múltiplos contextos do 4.0)* | Semgrep (`autoescape off`, `innerHTML`, `\|safe`, `Markup`) + ZAP (Reflected/Stored XSS, Header/CSP checks) |
| **V1.2.2** | V1.2 Injection Prevention | V5.3.1 (URL encoding) + V5.1.5 (URL Redirects) | `a validar` *(une encoding de URL e protocolo seguro `javascript:`/`data:`)* | Semgrep (`open-redirect`, esquemas `javascript:`/`data:`) + ZAP (Open Redirect, DOM/URL XSS) |
| **V1.2.3** | V1.2 Injection Prevention | V5.3.2 (JavaScript / JSON Output Encoding) | `confirmada` | Semgrep (interpolação em `<script>`, JSON inline não escapado) + ZAP (XSS em contexto JS/JSON) |
| **V1.2.4** | V1.2 Injection Prevention | V5.3.4, V5.3.5 (Parameterized Queries / SQLi / NoSQLi) | `confirmada` | Semgrep (SQL/NoSQL por f-string, `%`, `.format`, `+`) + ZAP (SQL Injection plugins) |
| **V1.2.5** | V1.2 Injection Prevention | V5.3.8 (OS Command Injection Prevention) | `confirmada` | Semgrep (`subprocess` com `shell=True`, `os.system`, `os.popen`) + ZAP (OS Command Injection plugin) |
| **V1.3.1** | V1.3 Sanitization | V5.2.1 (HTML Sanitization for WYSIWYG / Untrusted HTML) | `confirmada` | Semgrep (detecção de renderização de HTML rico sem `bleach`/`nh3`/`DOMPurify`) + `MANUAL_REQUIRED` quando inconclusivo |
| **V1.3.2** | V1.3 Sanitization | V5.2.4 (Avoid `eval()` / Dynamic Code Execution) | `confirmada` | Semgrep (`eval()`, `exec()`, `Function()`, expressão dinâmica insegura) |
| **V1.5.1** | V1.5 Safe Deserialization | V5.5.2 (Restrictive XML Parser / XXE Prevention) | `confirmada` | Semgrep (`xml.etree`/`lxml`/`minidom`/` pulldom` sem `defusedxml` ou com `resolve_entities=True`) + ZAP (XXE plugin) |

- **Rationale**: No ASVS 4.0, codificação, validação e sanitização ficavam no Capítulo **V5**, enquanto no ASVS 5.0 foram reestruturadas no Capítulo **V1** (*Encoding and Sanitization*). Marcar `V1.2.1` e `V1.2.2` como `"a validar"` (por fundirem controles distintos do 4.0) e os demais como `"confirmada"` cumpre rigorosamente o Princípio I da Constituição.
- **Alternatives considered**:
  - *Assumir correspondência direta por número de capítulo (V1 4.0 → V1 5.0)*: Rejeitado porque V1 no ASVS 4.0 era *Architecture, Design and Threat Modeling*, enquanto V1 no ASVS 5.0 é *Encoding and Sanitization*.

---

## 6. Frontend Fluent 2 Design System, Skill `microsoft/fluentui` e Gráficos Leves

- **Decision**: Construir o frontend em `templates/index.html`, `static/app.js` e `static/theme.css` utilizando **Fluent UI Web Components** (`@fluentui/web-components` e `@fluentui/tokens` via CDN ESM) e variáveis CSS oficiais dos Design Tokens Fluent 2 (consultando as diretrizes do skill `microsoft/fluentui` / `token-lookup` listado em `https://www.skills.sh/`). Os gráficos (donut de vereditos e barras por seção `V1.2`, `V1.3`, `V1.5`) serão renderizados em **SVG nativo acessível** (`role="img"`, `<title>`, `<desc>`) estilizado com os tokens semânticos Fluent (`--colorPaletteGreenForeground1`, `--colorPaletteRedForeground1`, `--colorPaletteMarigoldForeground1`, `--colorPaletteBlueForeground2`, `--colorNeutralBackground1`, etc.).
- **Rationale**:
  1. Atende ao Princípio V da Constituição sem exigir cadeia de build Node/Webpack complexa para servir a aplicação FastAPI.
  2. Gráficos em SVG nativo com tokens CSS adaptam-se automaticamente à troca entre **tema claro (`webLightTheme`) e tema escuro (`webDarkTheme`)**, além de permitir leitura por tecnologias assistivas (WCAG 2.2 AA).
  3. O template Jinja2 terá `autoescape=True` forçado e toda manipulação dinâmica no `static/app.js` usará `textContent` / criação segura de nós DOM (`createElement`), jamais `innerHTML` com dados externos, garantindo que a própria ferramenta passe no requisito `V1.2.1`.
- **Alternatives considered**:
  - *Bibliotecas pesadas de gráficos em Canvas sem suporte a CSS variables*: Rejeitadas por dificultarem acessibilidade via leitor de tela e sincronia imediata com tokens de tema claro/escuro.


---

## 7. Cobertura Obrigatória por Ferramenta Mapeada (`required_tools`) e Conectividade Real do OWASP ZAP (Iteração 2)

- **Decision**:
  1. Incluir `required_tools: list[str]` (carregado de `config/req_tool_mapping.yaml` -> `requirements[req_id].tools`) no contrato `RequirementVerdictInput` em `app/verdict.py`.
  2. Em `evaluate_requirement_verdict`, exigir conjunção lógica (`AND`) sobre todas as ferramentas declaradas em `required_tools`: se `"zap" in inp.required_tools` e `not has_dast_positive`, o requisito (quando tiver `0` achados ativos) DEVE receber **`INCONCLUSIVE`** (e nunca `PASS`), preservando a evidência parcial do Semgrep mas explicando na justificativa (`rationale`) que a validação dinâmica via OWASP ZAP é obrigatória para confirmar o requisito.
  3. Em `app/aci/zap_aci.py`, somente reportar `executed_plugins_by_req` quando o daemon REST do OWASP ZAP (`ZAP_BASE_URL`) responder efetivamente (`zap_daemon_used == True`), eliminando falsos positivos de cobertura gerados por *fallback* HTTP sem o motor do ZAP.
  4. Em `app/aci/workspace_aci.py`, restringir a detecção de superfície de `V1.3.1` a imports/chamadas reais (ex.: `import bleach`, `bleach.clean(`, `DOMPurify.sanitize(`) e excluir o próprio `workspace_aci.py` de auto-colisão literal ao autoavaliar `app/`.
- **Rationale**:
  - Na `Run #3` (autoavaliação de `app/` sem URL alvo), a etapa DAST foi pulada (`DAST - SKIPPED`) e os 8 requisitos receberam `PASS` (`100%`) porque `evaluate_requirement_verdict` utilizava `has_sast_positive or has_dast_positive`. Para os 6 requisitos que dependem de `["semgrep", "zap"]` (`V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.2.4`, `V1.2.5`, `V1.5.1`), apenas o Semgrep não é suficiente para atestar conformidade plena sem o OWASP ZAP.
- **Alternatives considered**:
  - *Permitir `PASS` com confiança `MEDIUM` apenas com Semgrep para todos os 8 requisitos*: Rejeitado pelo usuário e pela Emenda `v1.1.0` da Constituição (Princípio II), pois oculta que o OWASP ZAP não foi executado para requisitos que dependem de verificação dinâmica.
