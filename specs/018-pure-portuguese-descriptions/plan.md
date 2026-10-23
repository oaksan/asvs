# Plano de Implementação: 018 — Descrição Exclusiva em Português para V1.2.1 a V1.5.1

## 1. Resumo Executivo
Esta feature elimina a redundância visual causada pelo bloco expansível "Texto original (ASVS 5.0, inglês)", garantindo que cada um dos requisitos em escopo (V1.2.1 a V1.5.1) exiba diretamente e exclusivamente seu texto completo em português.

## 2. Análise Técnica e Arquitetural
- **Frontend (`static/app.js`)**:
  - Modificar a função `appendRequirementDescription(container, v, className)` para:
    1. Obter o texto em português (`description_pt` ou catálogo em português).
    2. Adicionar diretamente `<div class="req-description" lang="pt-BR">` com a descrição em português completa.
    3. Remover a criação do nó `<details class="req-original">` e seu conteúdo em inglês.
- **Folhas de Estilo (`static/theme.css`)**:
  - Limpar regras CSS associadas a `.req-original` ou mantê-las inofensivas.
- **Cache-Busting & Versão (`templates/index.html` e `app/main.py`)**:
  - Atualizar `APP_UI_VERSION = "018"` em `app/main.py`.
  - Atualizar referências de assets para `?v=018` em `templates/index.html`.
- **Testes Automatizados (`tests/test_feature_018_pure_portuguese.py`)**:
  - Testar que a página inicial e os endpoints retornam `?v=018`.
  - Testar que `static/app.js` não contém `"Texto original (ASVS 5.0, inglês)"`.
  - Testar que `appendRequirementDescription` renderiza a descrição em português.

## 3. Conformidade com a Constituição do Projeto
- **Princípio I (Domínio Normativo)**: Mantido. O banco e o CSV original permanecem intactos como referência imutável.
- **Princípio II (Vereditos)**: Mantido. A lógica de veredito não sofre nenhuma alteração.
- **Princípio IV (Guardrails & Segurança)**: Mantido. Nenhuma chamada de shell, nenhum segredo exposto.
- **Acessibilidade (WCAG 2.2 AA)**: Melhorada, pois remove elementos expansíveis vazios ou redundantes para leitores de tela e mantém o atributo `lang="pt-BR"`.

## 4. Mapeamento de Mudanças por Arquivo

| Arquivo | Componente | Descrição da Modificação |
| :--- | :--- | :--- |
| `specs/018-pure-portuguese-descriptions/` | SDD | Especificação, plano e tarefas da feature. |
| `static/app.js` | UI Logic | Remoção do bloco `details.req-original` em `appendRequirementDescription`. |
| `app/main.py` | Backend | Atualização de `APP_UI_VERSION = "018"`. |
| `templates/index.html` | Template | Atualização do cache-busting para `?v=018`. |
| `tests/test_feature_018_pure_portuguese.py` | TDD | Testes de ausência de texto em inglês e presença de pt-BR puro. |
| `tests/test_ui_presentation.py` | Regressão UI | Atualização da expectativa de versão `?v=018`. |
| `tests/test_zip_upload_run.py` | Regressão | Atualização da expectativa de versão `?v=018`. |
