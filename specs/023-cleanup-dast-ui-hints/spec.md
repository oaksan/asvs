# Especificação de Funcionalidade (SDD Spec) — Feature 023: Simplificação Visual do Card DAST

**Identificador**: `023-cleanup-dast-ui-hints`  
**Título**: Limpeza de Textos Informativos Redundantes no Card 2 (Artefato DAST — Aplicação em Execução)  
**Autor**: `sdd-conductor`  
**Status**: Planejado (Aprovado com Ressalvas no Gate 1)  
**Versão Alvo**: `v023` (UI Version `023`)  
**Princípios Constitucionais Aplicáveis**: I (TDD), IV (Segurança e Guardrails DAST Inegociáveis), V (Fluent 2 e WCAG 2.2 AA).

---

## 1. Contexto e Motivação

No Card 2 da Guia 1 ("1. Nova Avaliação"), intitulado **"2. Artefato DAST — Aplicação em Execução"**, havia acúmulo de notas de rodapé técnicas e redundantes que poluíam a experiência do usuário e criavam sobrecarga cognitiva:
1. **Texto de Allowlist**: *"Allowlist permitida: 127.0.0.1, host.docker.internal, localhost, testserver, vulnerable-app, web. Alvos localhost/127.0.0.1 são resolvidos automaticamente pelo container ZAP."*
   - *Motivo para remoção*: A validação de allowlist é estritamente de retaguarda (server-side via `validate_dast_target`), e o placeholder do input (`placeholder="Ex.: http://localhost:3000 ou http://localhost:8000"`) já orienta adequadamente o operador. Caso uma URL externa seja inserida, o sistema responde com mensagem amigável no banner de feedback.
2. **Caixa de Modo Fixo**: *"Modo de Varredura Fixo: Active Scan (Ataque Ativo + Spider) — Cobertura dinâmica integral dos requisitos V1.2.1 a V1.2.5 e V1.5.1."*
   - *Motivo para remoção*: O cabeçalho do próprio Card já exibe permanentemente o badge oficial `<span class="badge badge-PASS">OWASP ZAP • Active Scan Fixo</span>`. O elemento `<input type="hidden" id="zap-mode" name="zap_mode" value="active">` continuará mantendo o envio fixo do modo ativo sem necessidade da caixa de texto duplicada.
3. **Nota Subjacente do Termo Legal**: *"Termo mandatório de conformidade legal e segurança operacional (Princípio IV). Bloqueia início de DAST sem autorização."*
   - *Motivo para remoção*: O label do checkbox já declara com clareza jurídica e técnica: *"Declaro que possuo autorização explícita para executar testes dinâmicos (DAST / OWASP ZAP) contra a URL alvo informada acima."*. A nota subjacente era apenas um comentário interno de especificação/design que gerava ruído.

---

## 2. Escopo & Não-Escopo

### No Escopo
- Remoção no template HTML (`templates/index.html`) dos 3 blocos de texto identificados dentro de `#dast-artifact-card`.
- Remoção do atributo `aria-describedby="dast-auth-hint"` do elemento `#zap-authorized`, mantendo a conformidade WCAG 2.2 AA (Critério 4.1.2) sem referências dangling no DOM.
- Preservação integral do contêiner `#dast-auth-container`, do checkbox `#zap-authorized` com `aria-required="true"`, do input oculto `#zap-mode` (`value="active"`) e do input `#target-url`.
- Atualização do cache-busting para `?v=023` e da constante `APP_UI_VERSION = "023"`.
- Testes automatizados TDD verificando a remoção dos textos e a preservação da integridade funcional e acessível dos elementos DAST.

### Fora do Escopo
- Nenhuma alteração nas regras de backend de validação de allowlist (`app/aci/zap_aci.py`).
- Nenhuma alteração no guardrail DAST mandatório (`zap_authorized=True`) de backend.
- Nenhuma alteração na orquestração do OWASP ZAP em Active Scan.

---

## 3. Requisitos Funcionais (FR)

- **FR-001**: O Bloco 2 ("2. Artefato DAST — Aplicação em Execução") NÃO DEVE conter o texto informativo de allowlist permitida nem a menção à resolução de `localhost`/`127.0.0.1`.
- **FR-002**: O Bloco 2 NÃO DEVE conter o quadro descritivo de modo fixo de varredura (*"Modo de Varredura Fixo: Active Scan (Ataque Ativo + Spider)..."*), mantendo o badge existente no cabeçalho do card e o input oculto `#zap-mode`.
- **FR-003**: O Bloco 2 NÃO DEVE conter a nota de texto `#dast-auth-hint` (*"Termo mandatório de conformidade legal..."*).
- **FR-004**: O checkbox `#zap-authorized` DEVE ter seu atributo `aria-describedby` removido, mantendo seu rótulo acessível via `<label for="zap-authorized">`.
- **FR-005**: O envio de avaliações DAST deve permanecer 100% operacional quando o usuário informa uma URL válida e marca o consentimento explícito.

---

## 4. Requisitos Não-Funcionais (NFR)

- **NFR-001 (Acessibilidade WCAG 2.2 AA)**: Nenhum elemento de formulário deve possuir referências ARIA quebradas (`aria-describedby` para IDs inexistentes).
- **NFR-002 (Princípio IV — Segurança Inegociável)**: O guardrail DAST (bloqueio de submissão sem autorização e bloqueio de URLs fora da allowlist) deve permanecer 100% íntegro tanto no frontend quanto no backend.
- **NFR-003 (Princípio V — Regra Anti-innerHTML)**: Nenhuma injeção de HTML dinâmico pode ser introduzida.

---

## 5. Casos de Teste e Cenários Given / When / Then

### Cenário 1: Inspeção Visual e Estrutural do Card DAST
- **Given** que a página principal `/` é renderizada,
- **When** o HTML retornado é inspecionado no elemento `#dast-artifact-card`,
- **Then** a string `"Allowlist permitida"` NÃO deve estar presente no HTML,
- **And** a string `"Modo de Varredura Fixo"` NÃO deve estar presente no HTML,
- **And** a string `"Termo mandatório de conformidade legal"` NÃO deve estar presente no HTML,
- **And** o elemento `#zap-authorized` NÃO deve conter o atributo `aria-describedby="dast-auth-hint"`,
- **And** o checkbox `#zap-authorized`, seu `<label>`, o badge `<span class="badge badge-PASS">OWASP ZAP • Active Scan Fixo</span>` e o input `<input type="hidden" id="zap-mode" value="active">` devem permanecer presentes e intactos.

### Cenário 2: Preservação do Guardrail DAST sem Consentimento
- **Given** que o usuário preenche uma URL alvo válida no campo `#target-url`,
- **When** o usuário tenta submeter o formulário sem marcar o checkbox `#zap-authorized`,
- **Then** a submissão deve ser impedida com realce de erro no `#dast-auth-container` e mensagem de bloqueio de segurança.

### Cenário 3: Submissão com Sucesso com Guardrail DAST Atendido
- **Given** que o usuário preenche uma URL alvo válida e marca o checkbox `#zap-authorized`,
- **When** o formulário é submetido,
- **Then** a requisição para a API inclui `zap_authorized=true` e `zap_mode=active`, sendo aceita pelo backend.

