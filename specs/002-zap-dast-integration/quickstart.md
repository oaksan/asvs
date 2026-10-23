# Quickstart & Guia de Validação: Integração Fim a Fim do OWASP ZAP (`002-zap-dast-integration`)

**Feature**: [spec.md](./spec.md)  
**Contracts**: [zap-dast-and-status-api.md](./contracts/zap-dast-and-status-api.md)

---

## 1. Subir o Daemon do OWASP ZAP via Docker Compose

Para que a etapa DAST execute os plugins dinâmicos sobre a aplicação alvo, inicie o container do OWASP ZAP:

```bash
docker compose up -d zap
```

Verifique se o daemon ZAP terminou de inicializar e está respondendo na porta `8090`:

```bash
curl -s http://localhost:8090/JSON/core/view/version/
# Esperado: {"version":"2.15.0"} (ou versão estável instalada na imagem)
```

---

## 2. Iniciar o Servidor Web FastAPI (`ASVS-Self-Assesment-Tool`)

```bash
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Consulte o novo endpoint de diagnóstico de conectividade do ZAP:

```bash
curl -s http://localhost:8000/api/zap/status | python3 -m json.tool
```

- Quando o container `zap` está ativo, retorna `"online": true` e a versão do ZAP.
- Na interface web (`http://localhost:8000`), o badge **"Status OWASP ZAP (DAST)"** exibe `ONLINE` em verde.

---

## 3. Executar Autoavaliação Completa (SAST + DAST) na Interface Web

1. Acesse `http://localhost:8000`.
2. Verifique que o indicador **Status OWASP ZAP (DAST)** está `ONLINE`.
3. Clique no botão **"Autoavaliar Própria Ferramenta (`app/`)"**:
   - O sistema preenche automaticamente `workspace_subpath = "app"`, `target_url = "http://localhost:8000"`, marca o checkbox de autorização DAST e seleciona `Active Scan` (quando o ZAP está `ONLINE`).
4. O container do ZAP acessa a aplicação no host (traduzindo `localhost:8000` → `host.docker.internal:8000` caso necessário), executa o Spider até 100%, esvazia a fila passiva (`recordsToScan == 0`) e conclui o Active Scan até 100%.
5. **Resultado esperado ao final do pipeline**:
   - **`87.5% PASS`** (`7 PASS`, `0 FAIL`, `0 INCONCLUSIVE`, `1 MANUAL_REQUIRED` para `V1.3.1`).
   - No modo **`Baseline Passivo`**, o resultado esperado é **`50.0% PASS`** (`4 PASS` para `V1.2.1`, `V1.2.2`, `V1.2.3`, `V1.3.2`; `3 INCONCLUSIVE` para `V1.2.4`, `V1.2.5`, `V1.5.1`; `1 MANUAL_REQUIRED` para `V1.3.1`).

---

## 4. Executar a Suíte Automatizada de Testes (`pytest`)

```bash
.venv/bin/pytest -v
```

A suíte valida os cenários de:
- Conectividade `ONLINE` e `OFFLINE` em `GET /api/zap/status`;
- Resolução automática `localhost -> host.docker.internal` quando o ZAP roda em container;
- Polling completo de `spider`, `pscan` e `ascan` em `zap_aci`;
- Transição dos vereditos entre `12.5% PASS` (Somente SAST), `50.0% PASS` (SAST + ZAP Baseline Passivo) e `87.5% PASS` (SAST + ZAP Active Scan).

