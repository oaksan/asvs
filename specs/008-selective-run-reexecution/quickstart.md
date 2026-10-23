# Quickstart: 008-selective-run-reexecution

**Feature**: `008-selective-run-reexecution`  
**Purpose**: Guia operacional e de testes rápidos para a reexecução seletiva de avaliações.

---

## 1. Testes Automatizados (TDD)

```bash
# Executar a suíte de testes de reexecução seletiva
.venv/bin/pytest -v tests/test_selective_rerun.py
```

---

## 2. Reexecução Seletiva via API (cURL)

### Reexecutar Apenas Requisitos de IA e Python Exec (`V1.3.1` e `V1.3.2`):
```bash
curl -X POST "http://localhost:8000/api/runs/1/rerun" \
     -H "Content-Type: application/json" \
     -b "asvs_session=<seu_cookie_aqui>" \
     -d '{"req_ids": ["V1.3.1", "V1.3.2"]}'
```

### Reexecutar com Requisito Inválido (Esperado: 400 Bad Request):
```bash
curl -X POST "http://localhost:8000/api/runs/1/rerun" \
     -H "Content-Type: application/json" \
     -b "asvs_session=<seu_cookie_aqui>" \
     -d '{"req_ids": ["V9.9.9"]}'
```

---

## 3. Uso na Interface Web Fluent 2

1. Acesse o Dashboard de uma avaliação concluída.
2. Clique no botão **"Reexecução Seletiva..."**.
3. No modal que abrir, utilize os filtros:
   - **Veredito**: selecione `FAIL` para ver apenas requisitos reprovados.
   - **Ferramenta**: selecione `AI Evaluator` para focar em inspeção qualitativa.
4. Clique em **"Selecionar Filtrados"**.
5. Clique em **"Disparar Reexecução Seletiva"**.
6. Acompanhe pelo stepper na Guia 1: os estágios desnecessários serão pulados com `SKIPPED`, e os vereditos anteriores serão herdados automaticamente.

