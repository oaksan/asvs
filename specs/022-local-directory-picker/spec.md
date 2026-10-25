# Especificação de Funcionalidade (SDD): Seleção de Diretório Local do Código-Fonte (Botão "Procurar...")

**Feature Branch**: `022-local-directory-picker`  
**Created**: 2026-10-24  
**Status**: Ready for Implementation (Aprovado com Condições por Threat Modeler e Constitution Guardian)  
**Input**: *"em 1. Nova Avaliação, em 1. Artefato SAST — Código-Fonte, substitua o Caminho em Workspace Local para Caminho em Diretório Local. Ao selecionar essa opcao, faça com que tenha um botão de Procurar..., semelhante ao que existe para Arquivo .ZIP do Código-Fonte, mas que seja para Procurar o diretório do código fonte em disco local."*

---

## 1. Contexto e Diagnóstico

Hoje o card **"1. Artefato SAST — Código-Fonte"** da aba **1. Nova Avaliação** oferece duas origens:

| Opção atual | Comportamento |
|---|---|
| `Caminho em Workspace Local` (`workspace_path`) | Campo de texto livre ("Caminho Relativo no Workspace", ex.: `tests/vulnerable_app`). Só funciona para pastas **dentro da raiz do projeto ASVS** (ou do container Docker). |
| `Upload de Arquivo .ZIP` (`zip_upload`) | Campo `<input type="file">` com botão nativo **"Procurar..."** que envia o `.zip` para `POST /api/runs/upload`. |

**Problema**: para avaliar um projeto que está em qualquer pasta do disco do usuário, ele precisa digitar um caminho relativo ao workspace (que desconhece) ou compactar o projeto manualmente em `.zip`.

### 1.1 Restrição Técnica e Concepção de Arquitetura (Navegador + Docker)

> [!IMPORTANT]
> Por salvaguarda de sandbox, **nenhum navegador web expõe o caminho absoluto de arquivos locais** (ex.: `/home/user/meu-app` ou `C:\Projetos\app`). Além disso, em ambientes conteinerizados Docker, o backend não tem acesso direto ao sistema de arquivos do host do usuário sem montagem prévia.

A arquitetura estabelecida para seleção de diretório local adota a API padrão de navegadores modernos:
1. Utilização de `<input type="file" id="source-directory" webkitdirectory directory multiple>` acionado por botão com estilização Fluent 2 ("Procurar...").
2. O navegador lê os metadados e conteúdos mantendo a estrutura relativa de pastas através da propriedade `webkitRelativePath` (ex.: `meu-app/src/main.py`).
3. O frontend filtra diretórios de dependências e controle de versão (`node_modules`, `.git`, `.venv`, `__pycache__`, etc.) e arquivos de segredos órfãos (`.env`, `*.key`, `*.pem`) para prevenir vazamento e sobrecarga.
4. O frontend transmite os arquivos e seus caminhos relativos higienizados para o novo endpoint de ingestão `POST /api/runs/upload-directory`.
5. O backend valida rigorosamente cada segmento de caminho (contra path traversal, caracteres especiais, nomes de dispositivo Windows e symlinks) e grava os arquivos em pasta confinada dentro de `.workspace_uploads/dir_<upload_id>`, iniciando a avaliação com `source_type="directory_upload"`.

---

## 2. Objetivos da Feature 022

1. **Renomear a Opção**: No seletor `<select id="source-type">`, substituir o texto e valor de `Caminho em Workspace Local` (`workspace_path`) por **`Caminho em Diretório Local`** (`directory_upload`), tornando-a a opção selecionada por padrão.
2. **Substituir o Campo de Texto por Botão "Procurar..."**:
   - Remover da interface do usuário o campo de digitação de texto `#workspace-subpath`.
   - Adicionar o seletor de diretório com botão "Procurar..." estilizado de forma harmonizada com o campo de upload `.ZIP`.
3. **Resumo Informativo e Acessível**: Exibir resumo em tempo real da seleção: nome da pasta raiz, quantidade de arquivos elegíveis, contagem de arquivos/pastas ignorados e tamanho total aproximado, via `textContent` em região `role="status" aria-live="polite"` (sem `innerHTML`).
4. **Filtro Preventivo de Segredos e Dependências**:
   - Descartar automaticamente no cliente e no servidor pastas de infraestrutura/dependências: `node_modules`, `.git`, `.venv`, `venv`, `__pycache__`, `.idea`, `.vscode`, `dist`, `build`.
   - Descartar arquivos de chaves privadas e segredos locais: `.env`, `*.key`, `*.pem`, `id_rsa`, `.aws`, `.ssh`.
5. **Novo Endpoint REST `POST /api/runs/upload-directory`**:
   - Valida autenticação e pré-requisitos (IA configurada + consentimento DAST) antes de gravação persistente.
   - Aplica limites estritos de segurança: máximo de 15.000 arquivos, máximo de 5 MB por arquivo individual e limite global de 300 MB por upload.
   - Confinamento absoluto: validação com `is_relative_to` e rejeição de qualquer tentativa de traversal (`..`, caminhos absolutos, dispositivos Windows).
6. **Compatibilidade Regressiva**: O endpoint `POST /api/runs` continua aceitando payloads com `source_type="workspace_path"` internamente para testes automatizados e scripts de automação.

---

## 3. User Scenarios & Acceptance Criteria (Given / When / Then)

### User Story 1 — Seleção Visual de Diretório Local do Projeto (P1)
Como analista de segurança,  
quero clicar no botão "Procurar..." e selecionar a pasta do meu projeto no disco local,  
para iniciar a análise de segurança ASVS sem precisar digitar caminhos manuais nem criar arquivos .ZIP.

#### Acceptance Scenarios:
1. **Given** a aba "1. Nova Avaliação",  
   **When** visualizo o card "1. Artefato SAST — Código-Fonte",  
   **Then** o seletor de origem exibe como padrão "Caminho em Diretório Local" e o texto "Caminho em Workspace Local" não está visível.
2. **Given** a opção "Caminho em Diretório Local" ativa,  
   **When** inspeciono os controles,  
   **Then** visualizo o rótulo "Diretório do Código-Fonte" acompanhado do controle de seleção de pasta ("Procurar...").
3. **Given** o clique em "Procurar..." e a seleção de uma pasta de projeto (ex.: `meu-app`),  
   **When** a seleção é confirmada pelo usuário no diálogo nativo do sistema operacional,  
   **Then** a interface exibe o resumo textual formatado: `📁 meu-app — X arquivos selecionados (Y ignorados, Z MB)`.
4. **Given** uma pasta de projeto selecionada e pré-requisitos cumpridos,  
   **When** o formulário é submetido em "Iniciar Avaliação",  
   **Then** os arquivos são transmitidos para `POST /api/runs/upload-directory`, uma nova execução com `source_type="directory_upload"` é criada e o stepper visual avança para a fase de análise.

### User Story 2 — Validações de Entrada e Bloqueio de Estados Inválidos (P1)
Como operador da ferramenta,  
quero receber orientações e bloqueios imediatos se tentar iniciar uma avaliação sem pasta ou com dados inválidos,  
para corrigir os parâmetros antes do envio.

#### Acceptance Scenarios:
1. **Given** a opção "Caminho em Diretório Local" selecionada,  
   **When** clico em "Iniciar Avaliação" sem selecionar nenhuma pasta,  
   **Then** o card SAST é destacado com erro e a aplicação exibe: *"Artefato SAST obrigatório: Selecione o diretório do código-fonte antes de iniciar a avaliação."*
2. **Given** a seleção de uma pasta vazia ou contendo exclusivamente diretórios ignorados (ex.: apenas `node_modules`),  
   **When** o resumo é processado,  
   **Then** a interface avisa que nenhum arquivo elegível foi localizado e bloqueia o início da avaliação.
3. **Given** uma pasta que exceda 15.000 arquivos ou 300 MB após filtragem,  
   **When** validada no cliente ou rejeitada no backend,  
   **Then** a operação é interrompida com mensagem clara informando os limites suportados.

### User Story 3 — Blindagem e Guardrails de Upload de Diretório (Princípio IV)
Como auditor de segurança do sistema,  
quero garantir que o processamento do upload de diretório seja imune a ataques de path traversal, exaustão de recursos e escrita arbitrária,  
para manter a integridade inegociável do ambiente.

#### Acceptance Scenarios:
1. **Given** uma requisição contendo caminhos com tentativas de escape (`../`, `..\`, `/etc/passwd`, `C:\`, `\\net\share` ou bytes nulos),  
   **When** processada em `POST /api/runs/upload-directory`,  
   **Then** o backend rejeita a requisição integral com HTTP 400 e nenhum arquivo parcial permanece gravado em disco (limpeza via rollback).
2. **Given** um usuário tentando enviar upload sem autorização DAST (`zap_authorized=false`) ou sem provedor de IA configurado,  
   **When** a requisição atinge o backend,  
   **Then** o servidor responde respectivamente HTTP 403 ou HTTP 412 antes de persistir arquivos no diretório confinado.
3. **Given** uma requisição não autenticada,  
   **When** submetida ao endpoint,  
   **Then** o backend rejeita com HTTP 401 Unauthorized.
4. **Given** arquivos individuais que excedam 5 MB,  
   **When** recebidos no fluxo de upload de diretório,  
   **Then** são ignorados ou rejeitados pelo limite seguro, prevenindo esgotamento de memória.

---

## 4. Requisitos de Contratos e Endpoints

### 4.1 Endpoint `POST /api/runs/upload-directory`
- **Método**: `POST`
- **Content-Type**: `multipart/form-data`
- **Campos**:
  - `files`: Lista de arquivos (`UploadFile`).
  - `paths`: Lista paralela de strings representando o caminho relativo higienizado de cada arquivo (`webkitRelativePath`).
  - `target_url`: String opcional com a URL da aplicação em execução.
  - `zap_authorized`: Booleano obrigatório indicando consentimento explícito para DAST.
  - `zap_mode`: String (`"baseline"` ou `"active"`).
- **Respostas**:
  - `HTTP 202 Accepted`: Retorna `{"ok": True, "run_id": int, "status": "PENDING", ...}`.
  - `HTTP 400 Bad Request`: Parâmetros ausentes, tentativa de path traversal, mismatch entre listas de arquivos e caminhos, ou limites excedidos.
  - `HTTP 401 Unauthorized`: Sessão inexistente ou expirada.
  - `HTTP 403 Forbidden`: Falta de consentimento explícito `zap_authorized`.
  - `HTTP 412 Precondition Failed`: IA não configurada.

---

## 5. Critérios de Sucesso e Verificação

- **SC-001**: O analista consegue selecionar qualquer pasta do disco local através do botão "Procurar...", visualizando o resumo da pasta e iniciando a avaliação sem erros.
- **SC-002**: O termo "Caminho em Workspace Local" é 100% substituído por "Caminho em Diretório Local" na interface do usuário.
- **SC-003**: 100% dos testes unitários e de integração cobrindo o novo endpoint, validações de path traversal, limites e persistência confinado são aprovados.
- **SC-004**: Zero regressões na suíte global de testes do ASVS Tool.
