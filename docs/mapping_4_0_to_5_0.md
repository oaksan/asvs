# Tabela de Equivalência: OWASP ASVS 4.0 Testing Guide → OWASP ASVS 5.0 (Capítulo V1 - Level 1)

**Fonte Normativa ASVS 5.0**: `docs/OWASP_Application_Security_Verification_Standard_5_0_0_en.csv`  
**Guia de Teste de Referência (ASVS 4.0)**: `https://github.com/BlazingWind/OWASP-ASVS-4.0-testing-guide`  
**Escopo Avaliativo**: `chapter_id = 'V1'` (*Encoding and Sanitization*) e `L = 1` (8 requisitos).

> [!IMPORTANT]
> Conforme o Princípio I da Constituição do projeto, **não se presume equivalência 1:1** entre o ASVS 4.0 (onde *Validation, Sanitization and Encoding* constituíam o Capítulo **V5**) e o ASVS 5.0 (onde *Encoding and Sanitization* foram reestruturados no Capítulo **V1**). Cada linha abaixo é explicitamente classificada como `"confirmada"` ou `"a validar"`.

---

## 1. Mapeamento dos 8 Requisitos em Escopo (`V1 L1`)

| `req_id` (ASVS 5.0) | Seção (ASVS 5.0) | Descrição Resumida (ASVS 5.0) | Referência ASVS 4.0 (Testing Guide) | Status da Equivalência | Procedimento Derivado e Ferramentas Aplicáveis |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **V1.2.1** | `V1.2` Injection Prevention | Output encoding relevante para o contexto de resposta HTTP, documento HTML ou XML (elementos HTML, atributos, comentários, CSS ou cabeçalhos HTTP). | `V5.3.1`, `V5.3.3` | `a validar` | **Por que `a validar`**: O ASVS 5.0 unifica em `V1.2.1` múltiplos subcontextos que estavam distribuídos entre `V5.3.1` e `V5.3.3` no ASVS 4.0. **Verificação**: Semgrep (`v1-2-1-jinja2-autoescape-off`, `v1-2-1-markupsafe-safe-filter`, `v1-2-1-dom-innerhtml-sink`) + ZAP (`40012` Reflected XSS, `40014` Persistent XSS, `10038` CSP/Header checks). |
| **V1.2.2** | `V1.2` Injection Prevention | Ao construir URLs dinamicamente, codificar dados não confiáveis segundo o contexto (URL encoding / base64url) e permitir apenas protocolos seguros (bloquear `javascript:`, `data:`). | `V5.3.1` (URL context), `V5.1.5` (URL Redirects) | `a validar` | **Por que `a validar`**: O ASVS 5.0 combina codificação contextual de parâmetros de URL (`V5.3.1`) com restrição de esquemas seguros e prevenção de *open redirect* (`V5.1.5`). **Verificação**: Semgrep (`v1-2-2-unsafe-url-scheme`, `v1-2-2-open-redirect-unencoded-url`) + ZAP (`10028` Open Redirect, `40012` XSS em parâmetros de URL). |
| **V1.2.3** | `V1.2` Injection Prevention | Usar codificação ou escape de saída ao construir dinamicamente conteúdo JavaScript (incluindo JSON) para evitar injeção de JS/JSON. | `V5.3.2` | `confirmada` | **Por que `confirmada`**: Correspondência semântica direta com o controle `V5.3.2` do ASVS 4.0 sobre *Output Encoding for JavaScript/JSON*. **Verificação**: Semgrep (`v1-2-3-inline-script-interpolation`, `v1-2-3-unsafe-json-script-dump`) + ZAP (`40012` XSS em contexto JS/JSON). |
| **V1.2.4** | `V1.2` Injection Prevention | Consultas a bancos de dados (SQL, HQL, NoSQL, Cypher) utilizam queries parametrizadas, ORMs ou entity frameworks contra injeção (incluindo stored procedures). | `V5.3.4`, `V5.3.5` | `confirmada` | **Por que `confirmada`**: Os procedimentos de teste de parametrização de queries e prevenção de SQLi/NoSQLi de `V5.3.4`/`V5.3.5` no guia 4.0 aplicam-se integralmente a `V1.2.4`. **Verificação**: Semgrep (`v1-2-4-sql-string-concatenation`, `v1-2-4-sqlalchemy-raw-text-concat`) + ZAP (`40018` SQL Injection). |
| **V1.2.5** | `V1.2` Injection Prevention | Proteção contra *OS command injection* utilizando chamadas de SO parametrizadas ou codificação contextual de linha de comando. | `V5.3.8` | `confirmada` | **Por que `confirmada`**: Equivalência direta com `V5.3.8` do ASVS 4.0 (*OS Command Injection*). **Verificação**: Semgrep (`v1-2-5-subprocess-shell-true`, `v1-2-5-os-system-execution`) + ZAP (`90020` Remote OS Command Injection). |
| **V1.3.1** | `V1.3` Sanitization | Toda entrada HTML não confiável (de editores WYSIWYG ou similares) é sanitizada com biblioteca ou recurso de framework seguro e reconhecido. | `V5.2.1` | `confirmada` | **Por que `confirmada`**: Equivalência direta com `V5.2.1` do ASVS 4.0. **Verificação**: Semgrep (`v1-3-1-unsanitized-rich-html`) + `MANUAL_REQUIRED` quando houver superfície de entrada HTML rica cuja política de tags permitidas não possa ser provada apenas estaticamente. |
| **V1.3.2** | `V1.3` Sanitization | Evitar o uso de `eval()` ou outras formas de execução dinâmica de código (como SpEL); onde não houver alternativa, sanitizar qualquer entrada antes da execução. | `V5.2.4` | `confirmada` | **Por que `confirmada`**: Equivalência direta com `V5.2.4` do ASVS 4.0 (*Avoid `eval()` and dynamic code execution*). **Verificação**: Semgrep (`v1-3-2-python-eval-exec`, `v1-3-2-js-eval-function`). |
| **V1.5.1** | `V1.5` Safe Deserialization | Configurar parsers XML de forma restritiva e desabilitar recursos inseguros como resolução de entidades externas para prevenir ataques XXE. | `V5.5.2` | `confirmada` | **Por que `confirmada`**: Equivalência direta com `V5.5.2` do ASVS 4.0 (*Restrictive XML parser configuration / XXE prevention*). **Verificação**: Semgrep (`v1-5-1-xml-external-entities-enabled`, `v1-5-1-stdlib-xml-unsafe-parser`) + ZAP (`90023` XML External Entity Attack). |

---

## 2. Notas de Autoavaliação da Ferramenta (`ASVS-Self-Assesment-Tool` — Iteração 2 / Constituição `v1.1.0`)

- **V1.2.1** (`tools: ["semgrep", "zap"]`): Templates Jinja2 configurados com `autoescape=True`; frontend `static/app.js` utiliza criação segura de nós DOM (`textContent` / `createElement`) sem uso de `innerHTML`. Em execução **Somente SAST**, recebe `INCONCLUSIVE` (0 achados ativos, aguardando confirmação dinâmica ZAP `40012`/`40014`/`10038`); com ZAP executado (`baseline` ou `active`), recebe `PASS`.
- **V1.2.2** (`tools: ["semgrep", "zap"]`): Validação estrita de URLs contra esquemas `http://` e `https://` e `allowlist` de hosts antes de qualquer requisição. Em **Somente SAST**, recebe `INCONCLUSIVE`; com ZAP executado (`10028`/`40012`), recebe `PASS`.
- **V1.2.3** (`tools: ["semgrep", "zap"]`): Dados dinâmicos transmitidos via endpoints JSON estruturados (`application/json`) e consumidos via `JSON.parse` / `fetch`, sem interpolação em tags `<script>`. Em **Somente SAST**, recebe `INCONCLUSIVE`; com ZAP executado (`40012`), recebe `PASS`.
- **V1.2.4** (`tools: ["semgrep", "zap"]`): Persistência 100% parametrizada via `SQLModel` / `SQLAlchemy` ORM sem concatenação de strings SQL. Em **Somente SAST** ou **ZAP Baseline Passivo**, recebe `INCONCLUSIVE` (pois o plugin `40018` SQL Injection é ativo); com **ZAP Active Scan** autorizado, recebe `PASS`.
- **V1.2.5** (`tools: ["semgrep", "zap"]`): Todas as invocações ao Semgrep CLI em `app/aci/semgrep_aci.py` utilizam `subprocess.run([...], shell=False)` com lista de argumentos validada. Em **Somente SAST** ou **ZAP Baseline Passivo**, recebe `INCONCLUSIVE` (plugin `90020` é ativo); com **ZAP Active Scan** autorizado, recebe `PASS`.
- **V1.3.1** (`tools: ["semgrep"]` + revisão manual): A ferramenta não expõe editor HTML rico/WYSIWYG; portanto, em autoavaliação de `app/` (sem auto-colisão de literais internos do scanner), recebe `MANUAL_REQUIRED` com `0 FAIL`.
- **V1.3.2** (`tools: ["semgrep"]`): Zero uso de `eval()`, `exec()` ou `Function()` em todo o código Python e JavaScript; recebe `PASS` tanto em modo **Somente SAST** (`12.5% PASS`) quanto em modo **SAST + DAST**.
- **V1.5.1** (`tools: ["semgrep", "zap"]`): Nenhum parser XML vulnerável a XXE utilizado. Em **Somente SAST** ou **ZAP Baseline Passivo**, recebe `INCONCLUSIVE` (plugin `90023` XXE é ativo); com **ZAP Active Scan** autorizado, recebe `PASS`.


