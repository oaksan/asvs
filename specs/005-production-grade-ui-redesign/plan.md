# Implementation Plan: 005-production-grade-ui-redesign

**Branch**: `005-production-grade-ui-redesign`  
**Spec Reference**: [`specs/005-production-grade-ui-redesign/spec.md`](spec.md)  
**Status**: Ready for Tasks / TDD  
**Constitution Reference**: ASVS-Self-Assessment Tool v1.3.0 (Princípio V: Interface Fluent 2 / WCAG 2.2 AA e Princípio I: Especificação Estrita)

---

## 1. Technical Context & Scope

- **Linguagens e Tecnologias**: HTML5, Jinja2, JavaScript ES6 nativo, Microsoft Fluent 2 Web Components CDN (`@fluentui/web-components@2.6.1`), CSS Tokens Fluent (`static/theme.css`).
- **Arquivos Afetados**:
  1. `templates/index.html`: Cabeçalhos, tabelas de Catálogo e painel de IA.
  2. `static/app.js`: Funções de renderização dinâmica de tabela de requisitos e vereditos.
  3. `tests/test_ui_presentation.py`: Novo teste automatizado em pytest para verificar a integridade da renderização e ausência de ruídos do ASVS 4.0.
- **Arquivos Preservados (Sem Alterações)**:
  - `app/models.py` e `app/database.py` (modelos de dados e schemas Pydantic mantidos intactos para estabilidade da API REST).

---

## 2. Constitution Check (Princípios I a VI)

| Princípio | Avaliação de Impacto | Status |
| :--- | :--- | :---: |
| **I. Especificação e TDD** | A feature possui spec completa com critérios Given/When/Then e terá testes prévios antes da edição. | **CONFORME** |
| **II. Automação ASVS 5.0** | Foco exclusivo e estrito no OWASP ASVS 5.0 V1 L1, eliminando confusão com a versão 4.0 legada. | **CONFORME** |
| **III. Arquitetura e Contratos** | Contratos de API REST preservados; nenhuma alteração destrutiva em modelos SQLModel. | **CONFORME** |
| **IV. Guardrails e Segurança** | O checkbox obrigatório `#zap-authorized` e o gate de IA volátil (`AISecretStore`) permanecem inalterados e mandatórios. | **CONFORME** |
| **V. Fluent 2 e Acessibilidade** | Todas as alterações respeitam os tokens Fluent (`var(--colorNeutral...)`), atributos ARIA e suporte a tema claro/escuro. | **CONFORME** |
| **VI. Seeds e Mapeamento** | Mapeamento declarativo mantido em `config/req_tool_mapping.yaml`. | **CONFORME** |

*Veredito do Constitution Guardian*: **APROVADO SEM RESSALVAS**.

---

## 3. Detailed Architecture & Design

### 3.1 Template Jinja2 (`templates/index.html`)
1. **Catálogo de Requisitos (`#panel-catalog`)**:
   - Deletar a coluna `<th>Equivalência ASVS 4.0</th>` no `<thead>`.
   - Ajustar texto de introdução: remover *"e status de equivalência com o guia de testes ASVS 4.0"*.
2. **Formulário de Início (`#panel-assessment`)**:
   - Substituir `<code>{{ in_scope_req_ids | join(', ') }}</code>` e menções aos agentes de runtime por resumo executivo claro.
   - Refatorar `#zap-status-panel` em formato de chip discreto de conectividade.
3. **Painel de IA (`#ai-config-panel`)**:
   - Rótulo do container: *"Motor de Análise Cognitiva de Código (ASVS V1.3.1)"*.
   - Mensagem de descrição: *"Configure a chave de API para avaliação semântica de sanitização e renderização segura. As credenciais residem exclusivamente em memória volátil de sessão."*

### 3.2 Cliente JavaScript (`static/app.js`)
1. **`renderInScopeCatalog(data)`**:
   - Remover criação da célula `tdMap` contendo `item.asvs_4_0_ref` e `item.mapping_status`.
   - Garantir que a linha contenha exatamente 4 células alinhadas com o novo cabeçalho.
2. **`renderVerdictsTable(verdicts)`**:
   - Excluir a criação do elemento descritivo que concatenava `"ASVS 4.0: " + (v.asvs_4_0_refs || []).join(", ")`.
   - Exibir na primeira coluna apenas `v.req_id` em negrito e o nome legível da seção.

---

## 4. Estratégia de Testes Automatizados (TDD)
- Criar `tests/test_ui_presentation.py`:
  - Fazer requisição `GET /` e verificar que:
    1. A resposta HTTP é 200 OK.
    2. O termo `"Equivalência ASVS 4.0"` **NÃO** está presente no HTML gerado.
    3. O texto cru de concatenação de IDs não polui a descrição do formulário.
    4. O checkbox `#zap-authorized` e o input `#ai-api-key` continuam presentes com seus atributos de acessibilidade.

