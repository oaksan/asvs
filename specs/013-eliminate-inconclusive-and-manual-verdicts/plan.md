# Plano de Implementação (SDD): Eliminação de Vereditos `INCONCLUSIVE` e `MANUAL_REQUIRED` (`app/` e `OWASP Juice Shop`)

**Branch**: `013-eliminate-inconclusive-and-manual-verdicts` | **Date**: 2026-10-21 | **Spec**: [spec.md](file:///home/user/felipe/speckit/asvs/specs/013-eliminate-inconclusive-and-manual-verdicts/spec.md)

---

## 1. Resumo Arquitetural

Esta feature atua em 4 camadas complementares para eliminar os vereditos `INCONCLUSIVE` e `MANUAL_REQUIRED` nas avaliações completas de `Autoavaliar Própria Ferramenta (app/)` e `OWASP Juice Shop`, preservando rigorosamente o Princípio II da Constituição (Honestidade Epistêmica):

1. **Coleta Completa de Contexto e Orientação Clara em `V1.3.1` (`app/aci/ai_aci.py`)**:
   - Remover o truncamento `[:60]` em `_collect_code_context_for_v1_3_1` que ocultava as linhas 120–124 de `app/main.py` (`autoescape=jinja2.select_autoescape(...)`).
   - Incluir extensões `.ts` e `.js` (ignorando `node_modules`, `dist`, `build`, `.git`, `.venv`) e extrair janelas de contexto (`±2 linhas`) em torno de indicadores relevantes (`autoescape`, `select_autoescape`, `bleach`, `nh3`, `DOMPurify`, `sanitizeHtml`, `bypassSecurityTrustHtml`, `innerHTML`, `|safe`).
   - Refinar o prompt do `AIEvaluatorAgent` para entregar claramente os indicadores de superfície e orientar a emissão fundamentada de `PASS` ou `FAIL` pelo próprio modelo, mantendo intacta a regra constitucional de `app/verdict.py` (que converte eventual `INCONCLUSIVE` ou ausência de IA em `MANUAL_REQUIRED`).
2. **Regras SAST Semgrep Multi-Linguagem (`config/semgrep_rules/*.yaml` + `config/req_tool_mapping.yaml`)**:
   - `V1.2.5`: Regra `v1-2-5-js-child-process-exec` para Node.js/TypeScript (`child_process.exec`, `execSync`, `spawn(..., {shell: true})`).
   - `V1.3.1`: Regra `v1-3-1-js-angular-unsanitized-html` para TypeScript/JavaScript (`bypassSecurityTrustHtml(...)`).
   - `V1.5.1`: Regra `v1-5-1-js-xxe-libxml-noent` para Node.js/TypeScript (`parseXml(..., { ..., noent: true, ... })` e `parseXmlString(..., { ..., noent: true, ... })`).
3. **Scanner de Superfície Multi-Linguagem e Evidência Positiva de Não-Exposição (`app/aci/workspace_aci.py`)**:
   - Ignorar diretórios de terceiros/build (`node_modules`, `dist`, `build`, `coverage`, `.angular`) em `scan_workspace_surface`.
   - Expandir os detectores de superfície de `V1.2.5`, `V1.3.1` e `V1.5.1` para reconhecer construções JS/TS além de Python.
   - Quando `code_files_count > 0` e 100% dos arquivos de código do escopo forem inspecionados sem chamadas de execução de comando de SO inseguras (`V1.2.5`) ou sem parsers XML inseguros (`V1.5.1`), registrar indicador positivo auditável de não-exposição, permitindo que `compute_requirement_verdict` emita `PASS` em vez de `INCONCLUSIVE`.
4. **Hardening de Cabeçalhos HTTP em `app/main.py`**:
   - Adicionar `X-Content-Type-Options: nosniff` e `Content-Security-Policy` no middleware HTTP de `app/main.py` para eliminar os alertas passivos `10021` e `10038` do OWASP ZAP ao escanear `http://localhost:8000`.

---

## 2. Constituição Check (Gate Validation)

- **Princípio I (Escopo ASVS V1 L1)**: Mantém estritamente os 8 requisitos do Capítulo V1 Nível 1.
- **Princípio II (Honestidade Epistêmica)**:
  - `PASS` em `V1.2.5` e `V1.5.1` exige que `code_files_count > 0` (arquivos de código reais foram inspecionados pelo Semgrep e pelo `scan_workspace_surface`) e que 0 vulnerabilidades tenham sido detectadas no SAST e no DAST. Se um diretório vazio (`code_files_count == 0`) for analisado, `INCONCLUSIVE` continua sendo emitido!
  - `MANUAL_REQUIRED` em `V1.3.1` continua sendo emitido obrigatoriamente quando `ai_configured=False` ou quando a chamada à API de IA falha.
- **Princípio III (Orquestração Determinística)**: Sem alteração de banco ou fluxo SSE.
- **Princípio IV (Guardrails ACI)**: Semgrep permanece invocado com `shell=False` e lista de argumentos; leitura de arquivos confinada a `resolve_confined_path`.

---

## 3. Arquivos Modificados

1. [app/aci/ai_aci.py](file:///home/user/felipe/speckit/asvs/app/aci/ai_aci.py)
   - `_collect_code_context_for_v1_3_1`: Suporte a `.ts` e `.js`, exclusão de `node_modules`/`dist`/`build`, leitura de todas as linhas do arquivo com janela de contexto `±2 linhas` ao redor dos matches, e priorização de arquivos de aplicação (`main.py`, rotas, templates, componentes) sobre arquivos de teste.
   - `run_ai_evaluation`: Atualização do `system_prompt` para orientar decisão conclusiva (`PASS` ou `FAIL`) quando arquivos do projeto foram inspecionados.
2. [app/aci/workspace_aci.py](file:///home/user/felipe/speckit/asvs/app/aci/workspace_aci.py)
   - `scan_workspace_surface`: Exclusão de `node_modules`, `dist`, `build`, `coverage`; adição de padrões JS/TS para `V1.2.5`, `V1.3.1` e `V1.5.1`; registro de evidência positiva de superfície verificada para `V1.2.5`, `V1.3.1` e `V1.5.1` quando `code_files_count > 0` e nenhuma construção insegura existir nos arquivos inspecionados.
3. [config/semgrep_rules/v1_2_injection.yaml](file:///home/user/felipe/speckit/asvs/config/semgrep_rules/v1_2_injection.yaml)
   - Nova regra `v1-2-5-js-child-process-exec`.
4. [config/semgrep_rules/v1_3_sanitization.yaml](file:///home/user/felipe/speckit/asvs/config/semgrep_rules/v1_3_sanitization.yaml)
   - Nova regra `v1-3-1-js-angular-unsanitized-html`.
5. [config/semgrep_rules/v1_5_deserialization.yaml](file:///home/user/felipe/speckit/asvs/config/semgrep_rules/v1_5_deserialization.yaml)
   - Nova regra `v1-5-1-js-xxe-libxml-noent`.
6. [config/req_tool_mapping.yaml](file:///home/user/felipe/speckit/asvs/config/req_tool_mapping.yaml)
   - Registro das 3 novas regras Semgrep em `V1.2.5`, `V1.3.1` e `V1.5.1`.
7. [app/main.py](file:///home/user/felipe/speckit/asvs/app/main.py)
   - Adição de `X-Content-Type-Options: nosniff` e `Content-Security-Policy` no middleware HTTP.
8. [tests/test_feature_013_conclusive_verdicts.py](file:///home/user/felipe/speckit/asvs/tests/test_feature_013_conclusive_verdicts.py)
   - Suíte TDD cobrindo todos os cenários de `app/` e `OWASP Juice Shop`.

