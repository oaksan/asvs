# Especificação de Funcionalidade (SDD): Eliminação de Vereditos `INCONCLUSIVE` e `MANUAL_REQUIRED` em Avaliações Completas (`app/` e `OWASP Juice Shop`)

**Feature Branch**: `013-eliminate-inconclusive-and-manual-verdicts`  
**Created**: 2026-10-21  
**Status**: Ready for Implementation  
**Input**: *"poderia avaliar e sugerir o sdd para eliminar o INCONCLUSIVE e MANUAL_REQUIRED ao menos de Autoavaliar Própria Ferramenta (app/) e OWASP Juice Shop ?"*

---

## 1. Diagnóstico Empírico das Execuções Reais (`asvs.db`)

A auditoria forense dos dados persistidos no SQLite (`asvs.db`) para **Run #205 (`Autoavaliar Própria Ferramenta - app/`)** e **Run #210 (`OWASP Juice Shop`)** revelou as causas-raiz exatas para cada veredito `MANUAL_REQUIRED` e `INCONCLUSIVE`:

### 1.1. Caso 1: `Autoavaliar Própria Ferramenta (app/)` — Run #205
| Requisito | Veredito na Run #205 | Causa-Raiz Identificada |
| :--- | :--- | :--- |
| **`V1.3.1`** (Sanitização de HTML Rico / WYSIWYG) | **`MANUAL_REQUIRED`** | Em `app/aci/ai_aci.py` (`_collect_code_context_for_v1_3_1`, linha 439), a função lia apenas as **primeiras 60 linhas** de cada arquivo (`content.splitlines()[:60]`). Em `app/main.py`, a configuração real do Jinja2 (`autoescape=jinja2.select_autoescape(["html", "xml"], default_for_string=True, default=True)`) está nas **linhas 120–124**! Como o `gpt-5.4` recebeu apenas a linha 57 (`from app.agents.reporter_agent import ...`), respondeu `INCONCLUSIVE` por falta de trecho completo, e `app/verdict.py` converteu `INCONCLUSIVE` da IA em `MANUAL_REQUIRED`. |
| **`V1.2.1`** & **`V1.2.3`** *(Bônus de Hardening)* | **`FAIL`** (DAST ZAP) | O container `http://localhost:8000` não emitia os cabeçalhos HTTP `X-Content-Type-Options: nosniff` (ZAP Plugin `10021`) nem `Content-Security-Policy` (ZAP Plugin `10038`), gerando os únicos 2 `FAIL` na autoavaliação da própria ferramenta. |

### 1.2. Caso 2: `OWASP Juice Shop` (`juice-shop-master.zip` + `http://localhost:3000`) — Run #210
| Requisito | Veredito na Run #210 | Causa-Raiz Identificada |
| :--- | :--- | :--- |
| **`V1.2.5`** (Prevenção de OS Command Injection) | **`INCONCLUSIVE`** | `scan_workspace_surface` (`app/aci/workspace_aci.py`, linhas 427–437) e `config/semgrep_rules/v1_2_injection.yaml` buscavam apenas chamadas Python (`subprocess.`, `os.system`, `os.popen`, `shlex.`). Como o Juice Shop é **Node.js / TypeScript**, `surface_count` ficou `0` e `positive_indicators` ficou `[]`, levando `app/verdict.py` a emitir `INCONCLUSIVE`. |
| **`V1.5.1`** (Prevenção de XXE em Parsers XML) | **`INCONCLUSIVE`** | `scan_workspace_surface` (`app/aci/workspace_aci.py`, linhas 476–494) e `config/semgrep_rules/v1_5_deserialization.yaml` buscavam apenas bibliotecas XML de Python (`defusedxml`, `ElementTree`, `minidom`, `lxml`). O Juice Shop é TypeScript e utiliza `libxmljs` (`libxml.parseXml(xmlString, { noblanks: true, noent: true, nocdata: true })` em `routes/fileUpload.ts`, que inclusive habilita substituição de entidades externas via `noent: true`!). |
| **`V1.3.1`** (Sanitização de HTML Rico / WYSIWYG) | **`MANUAL_REQUIRED`** | `_collect_code_context_for_v1_3_1` (`app/aci/ai_aci.py`, linha 410) filtrava apenas `{".py", ".html", ".jinja", ".jinja2", ".toml", ".txt"}`, **ignorando todos os arquivos `.ts` e `.js`** do Juice Shop (como `frontend/src/app/...` com `bypassSecurityTrustHtml` e `domSanitizer`), além de truncar em 60 linhas e carecer de regra Semgrep JS/TS para `bypassSecurityTrustHtml` / `[innerHTML]`. |

---

## 2. User Scenarios & Testing *(mandatory)*

### User Story 1 - Extração Completa de Contexto Multi-Linguagem e Decisão Determinística em `V1.3.1` (Priority: P1)

Como engenheiro de segurança executando uma avaliação com IA configurada (`AIEvaluatorAgent`) e SAST sobre `app/` ou `OWASP Juice Shop`, quero que a coleta de contexto de `V1.3.1` inspecione todas as linhas de arquivos Python, Templates e JavaScript/TypeScript (`.py`, `.ts`, `.js`, `.html`, `.jinja`, `.jinja2`) extraindo janelas de contexto ao redor das evidências (`±3 linhas`) e que regras Semgrep + IA emitam sempre um veredito conclusivo (`PASS` ou `FAIL`), reservando `MANUAL_REQUIRED` exclusivamente para quando o provedor de IA não estiver configurado ou estiver indisponível.

**Why this priority**: Elimina 100% dos falsos `MANUAL_REQUIRED` em `V1.3.1` tanto em projetos Python/Jinja2 (`app/`) quanto em projetos TypeScript/Angular/Node.js (`OWASP Juice Shop`).

**Independent Test**: Executar `_collect_code_context_for_v1_3_1("app")` e verificar que as linhas 120–124 de `app/main.py` (`select_autoescape`) estão presentes no snippet; executar sobre um projeto TypeScript/Angular com `bypassSecurityTrustHtml` e verificar que tanto o Semgrep (`v1-3-1-js-angular-unsanitized-html`) quanto o coletor de contexto capturam a evidência.

**Acceptance Scenarios**:

1. **Given** o diretório `app/` da própria ferramenta, **When** `_collect_code_context_for_v1_3_1("app")` é executado, **Then** o trecho das linhas 118–126 de `app/main.py` contendo `autoescape=jinja2.select_autoescape` DEVE ser incluído nos `code_snippets`, permitindo que o `AIEvaluatorAgent` emita `PASS`.
2. **Given** um código-fonte contendo `.ts` ou `.js` (como `OWASP Juice Shop`) com uso de `bypassSecurityTrustHtml` ou `sanitizeHtml` / `DOMPurify`, **When** o SAST e o `_collect_code_context_for_v1_3_1` são executados, **Then** os arquivos `.ts`/`.js` DEVEM ser inspecionados (sem truncamento nas primeiras 60 linhas do arquivo) e a regra Semgrep `v1-3-1-js-angular-unsanitized-html` DEVE detectar `bypassSecurityTrustHtml`, resultando em veredito conclusivo (`FAIL` no Juice Shop e `PASS` em `app/`).
3. **Given** uma avaliação de `V1.3.1` onde a IA está configurada, **When** `_collect_code_context_for_v1_3_1` entrega o contexto completo (incluindo `autoescape=jinja2.select_autoescape` em `app/main.py` ou `bypassSecurityTrustHtml` em arquivos `.ts`) e o `system_prompt` orienta a avaliação objetiva dessa evidência, **Then** o próprio `AIEvaluatorAgent` DEVE ter contexto suficiente para emitir `PASS` ou `FAIL` de forma fundamentada, mantendo intacta a regra constitucional em `app/verdict.py` de converter eventual `INCONCLUSIVE` ou ausência de IA em `MANUAL_REQUIRED`.

---

### User Story 2 - Cobertura Multi-Linguagem (Python + JS/TS) e Evidência Positiva de Não-Exposição para `V1.2.5` e `V1.5.1` (Priority: P1)

Como engenheiro de segurança avaliando aplicações Python (`app/`) ou Node.js/TypeScript (`OWASP Juice Shop`), quero que o scanner de superfície (`scan_workspace_surface`) e as regras Semgrep de `V1.2.5` (OS Command Injection) e `V1.5.1` (XXE / XML Parsing) suportem construções JavaScript/TypeScript e registrem evidência positiva verificada quando todos os arquivos de código do escopo forem inspecionados com zero chamadas inseguras de SO ou parsers XML vulneráveis.

**Why this priority**: Elimina os vereditos `INCONCLUSIVE` em `V1.2.5` e `V1.5.1` no `OWASP Juice Shop` e em qualquer aplicação que não invoque comandos de SO ou não utilize parsers XML inseguros.

**Independent Test**: Executar `scan_workspace_surface` e Semgrep sobre `OWASP Juice Shop` (ou fixtures JS/TS equivalentes) e validar que `V1.2.5` e `V1.5.1` produzem vereditos conclusivos (`PASS` ou `FAIL`) com 0 `INCONCLUSIVE`.

**Acceptance Scenarios**:

1. **Given** um projeto Node.js/TypeScript ou Python com `code_files_count > 0`, **When** `scan_workspace_surface` analisa `V1.2.5`, **Then** DEVE inspecionar padrões Python (`subprocess.`, `os.system`, `os.popen`, `shlex.`) e JS/TS (`child_process`, `exec(`, `execSync(`, `spawn(`, `spawnSync(`, `execFile(`) e, caso o projeto possua 0 chamadas perigosas ou não invoque comandos de SO em nenhum dos arquivos de código inspecionados, DEVE registrar indicador positivo de superfície verificada livre de Command Injection.
2. **Given** um projeto Node.js/TypeScript que utiliza `libxmljs.parseXml(..., { noent: true })` (como `routes/fileUpload.ts` no `OWASP Juice Shop`) ou `exec(` com concatenação em `child_process`, **When** o Semgrep é executado, **Then** as novas regras `v1-5-1-js-xxe-libxml-noent` e `v1-2-5-js-child-process-exec` DEVEM detectar as vulnerabilidades como `FAIL` (ou `PASS` se seguro/ausente), eliminando o `INCONCLUSIVE`.
3. **Given** um projeto com `code_files_count > 0` que não utiliza parsers XML inseguros, **When** `scan_workspace_surface` analisa `V1.5.1`, **Then** DEVE inspecionar padrões Python e JS/TS (`parseXml`, `libxmljs`, `xml2js`, `DOMParser`, `SAXParser`) e registrar indicador positivo caso nenhum parser XML inseguro exista nos arquivos de código inspecionados.

---

### User Story 3 - Hardening de Cabeçalhos HTTP em `app/main.py` para `8/8 PASS` na Autoavaliação (Priority: P2)

Como desenvolvedor executando a autoavaliação (`Autoavaliar Própria Ferramenta`) com SAST + DAST Ativo + IA sobre `app/` e `http://localhost:8000`, quero que a própria aplicação envie os cabeçalhos defensivos `X-Content-Type-Options: nosniff` e `Content-Security-Policy` para que o OWASP ZAP não reporte alertas passivos `10021` e `10038` contra `http://localhost:8000`.

**Why this priority**: Além de eliminar o `MANUAL_REQUIRED` em `V1.3.1`, garante que a autoavaliação da própria ferramenta alcance **100% de aprovação (`8/8 PASS`)** com zero `FAIL`, zero `INCONCLUSIVE` e zero `MANUAL_REQUIRED`.

**Independent Test**: Fazer uma requisição `GET /` na aplicação FastAPI e verificar a presença dos cabeçalhos `X-Content-Type-Options: nosniff` e `Content-Security-Policy`.

**Acceptance Scenarios**:

1. **Given** o servidor FastAPI em `app/main.py`, **When** qualquer resposta HTTP é retornada pela aplicação, **Then** os cabeçalhos `X-Content-Type-Options: nosniff` e `Content-Security-Policy` (compatível com os recursos locais e Fluent UI da própria ferramenta) DEVEM estar presentes na resposta.

---

## 3. Requirements *(mandatory)*

### Functional Requirements

- **FR-001 (Inspeção Completa de Arquivos e Suporte JS/TS em `_collect_code_context_for_v1_3_1`)**: A função `_collect_code_context_for_v1_3_1` em `app/aci/ai_aci.py` DEVE suportar as extensões `{".py", ".ts", ".js", ".html", ".jinja", ".jinja2", ".toml", ".txt"}` (ignorando diretórios como `node_modules`, `dist`, `build`, `.git`, `.venv`, `vendor`, `coverage`) e DEVE varrer **todas as linhas** de cada arquivo (removendo o limite prematuro `[:60]`), extraindo janelas de contexto (`±2 linhas`) ao redor das linhas que contenham indicadores de sanitização/renderização (`autoescape`, `select_autoescape`, `bleach`, `nh3`, `DOMPurify`, `sanitizeHtml`, `bypassSecurityTrustHtml`, `innerHTML`, `[innerHTML]`, `|safe`, `| safe`, `markupsafe`, `Markup`).
- **FR-002 (Entrega de Contexto Completo e Prompt Determinístico do `AIEvaluatorAgent` em `V1.3.1`)**:
  - O `system_prompt` e o `user_prompt` em `run_ai_evaluation` (`app/aci/ai_aci.py`) DEVEM fornecer os trechos completos de configuração de template/sanitização (sem o truncamento nas primeiras 60 linhas) juntamente com os indicadores positivos e achados SAST da superfície `V1.3.1`, orientando o modelo a emitir `PASS` quando o `autoescape` contextual estiver ativo e não houver sinks de HTML rico não sanitizado, ou `FAIL` quando houver renderização não sanitizada (ex.: `bypassSecurityTrustHtml`, `|safe` inseguro).
  - Em estrita observância ao Princípio II da Constituição, `app/verdict.py` NÃO DEVE sobrescrever artificialmente um veredito `INCONCLUSIVE` da IA para `PASS`; caso a IA não esteja configurada ou emita `INCONCLUSIVE`, a conversão para `MANUAL_REQUIRED` permanece inalterada.
- **FR-003 (Novas Regras Semgrep Multi-Linguagem para `V1.2.5`, `V1.3.1` e `V1.5.1`)**:
  - `config/semgrep_rules/v1_2_injection.yaml`: Adicionar regra `v1-2-5-js-child-process-exec` (`languages: [javascript, typescript]`) para detectar execução insegura de comandos de SO em Node.js/TS (`child_process.exec(...)`, `execSync(...)`, etc.) e registrá-la em `config/req_tool_mapping.yaml`.
  - `config/semgrep_rules/v1_3_sanitization.yaml`: Adicionar regra `v1-3-1-js-angular-unsanitized-html` (`languages: [javascript, typescript]`) para detectar `bypassSecurityTrustHtml(...)` e atribuições diretas de HTML rico sem sanitização em JS/TS e registrá-la em `config/req_tool_mapping.yaml`.
  - `config/semgrep_rules/v1_5_deserialization.yaml`: Adicionar regra `v1-5-1-js-xxe-libxml-noent` (`languages: [javascript, typescript]`) para detectar `parseXml(..., { ..., noent: true, ... })` / `parseXmlString(..., { ..., noent: true, ... })` em JS/TS e registrá-la em `config/req_tool_mapping.yaml`.
- **FR-004 (Detecção de Superfície Multi-Linguagem e Evidência Positiva de Não-Exposição em `scan_workspace_surface`)**:
  - Em `app/aci/workspace_aci.py`:
    - Ignorar diretórios pesados de dependências/build (`node_modules`, `dist`, `build`, `coverage`, `.angular`) durante a varredura de superfície para máxima performance e precisão.
    - Para **`V1.2.5`**: detectar superfícies Python e JS/TS (`child_process`, `exec(`, `execSync(`, `spawn(`, `execFile(`). Quando `code_files_count > 0` e nenhuma chamada insegura de comando de SO for encontrada nos arquivos inspecionados (ou quando chamadas parametrizadas/ausência de comandos de SO forem verificadas), registrar evidência positiva em `V1.2.5` para que projetos sem uso de `subprocess`/`child_process` recebam `PASS` (e não `INCONCLUSIVE`).
    - Para **`V1.3.1`**: detectar superfícies Python/Jinja e JS/TS (`DOMPurify`, `sanitizeHtml`, `bypassSecurityTrustHtml`, `innerHTML`, `autoescape`, `select_autoescape`). Quando `code_files_count > 0` e não houver sinks de HTML rico sem sanitização, registrar indicador positivo de superfície verificada.
    - Para **`V1.5.1`**: detectar superfícies Python e JS/TS (`libxmljs`, `parseXml`, `parseXmlString`, `xml2js`, `DOMParser`, `SAXParser`, `noent`). Quando `code_files_count > 0` e nenhum parser XML com entidades externas habilitadas for encontrado nos arquivos inspecionados, registrar evidência positiva de superfície verificada livre de XXE.
- **FR-005 (Middleware de Cabeçalhos HTTP Defensivos em `app/main.py`)**:
  - Adicionar cabeçalhos `X-Content-Type-Options: nosniff` e `Content-Security-Policy` nas respostas HTTP de `app/main.py` para eliminar os alertas passivos `10021` e `10038` do OWASP ZAP durante a autoavaliação de `http://localhost:8000`.

---

## 4. Success Criteria *(mandatory)*

- **SC-001 (`Autoavaliar Própria Ferramenta - app/`)**: Em uma execução completa (SAST + DAST Ativo + IA configurada), os 8 requisitos do ASVS V1 L1 DEVEM resultar em **8 `PASS`**, **0 `FAIL`**, **0 `INCONCLUSIVE`** e **0 `MANUAL_REQUIRED`**.
- **SC-002 (`OWASP Juice Shop`)**: Em uma execução completa (SAST com `juice-shop-master.zip` + DAST Ativo em `http://localhost:3000` + IA configurada), todos os 8 requisitos do ASVS V1 L1 DEVEM resultar em vereditos conclusivos (**`PASS`** ou **`FAIL`**), com **0 `INCONCLUSIVE`** e **0 `MANUAL_REQUIRED`**.
- **SC-003 (Preservação da Honestidade Epistêmica — Princípio II)**: Quando a IA **não** estiver configurada (`ai_configured=False`), `V1.3.1` DEVE continuar emitindo `MANUAL_REQUIRED` (caso o SAST não tenha falhado); quando um escopo vazio (`0 arquivos de código`) for submetido sem DAST, os requisitos DEVEM continuar emitindo `INCONCLUSIVE`.

