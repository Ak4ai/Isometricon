# REQ-PERF-002 — Geração de chunks em segundo plano

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `PR-002`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `requirements.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `PR-002` |
| **Nome** | Geração de chunks em segundo plano |
| **Tipo** | Performance |
| **Prioridade** | Essencial |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O sistema deve gerar e montar chunks em thread separada, sem bloquear o laço de renderização, e publicar cada resultado por fila.

### Condições de Aplicação

- o sistema opera com dados e carga compatíveis com o requisito

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `test_world_manager_result_queue_safe_without_gl`; `test_world_manager_reports_each_pending_streaming_stage`. |

---

## Justificativa (Rationale)

Garante resposta interativa e uso previsível de recursos.

---

## Critérios de Verificação e Aceitação

### Método de Verificação

- [ ] Inspeção / Revisão
- [ ] Teste
- [ ] Demonstração
- [ ] Análise
- [ ] Simulação

### Critérios de Aceitação (Gherkin)

```gherkin
Funcionalidade: Geração de chunks em segundo plano
  Cenário: Exercitar Geração de chunks em segundo plano
    Dado que o sistema opera com dados e carga compatíveis com o requisito
    Quando a condição de desempenho é exercitada
    Então chunks são gerados em thread e publicados por fila
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | `test_world_manager_result_queue_safe_without_gl`; `test_world_manager_reports_each_pending_streaming_stage`. | O sistema deve gerar e montar chunks em thread separada, sem bloquear o laço de renderização, e publicar cada resultado por fila. |

Testes existentes: `tests/test_world_manager_result_queue_safe_without_gl.py`, `tests/test_world_manager_reports_each_pending_streaming_stage.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial de desempenho. |
| **Appropriate (Apropriado)** | [x] Sim [ ] Não | Descreve comportamento ou restrição, sem impor implementação. |
| **Unambiguous (Não ambíguo)** | [x] Sim [ ] Não | Redação única, com condição e critério de aceitação. |
| **Complete (Completo)** | [x] Sim [ ] Não | Texto, condição, verificação e rastreabilidade declarados. |
| **Singular (Singular)** | [x] Sim [ ] Não | Trata de uma única capacidade ou restrição. |
| **Feasible (Factível)** | [x] Sim [ ] Não | Implementado no baseline. |
| **Verifiable (Verificável)** | [x] Sim [ ] Não | Método: inspeção. |
| **Correct (Correto)** | [x] Sim [ ] Não | Rastreável à fonte declarada. |
| **Conforming (Conforme)** | [x] Sim [ ] Não | Segue este template e a ISO/IEC/IEEE 29148:2018. |

---

## Informações Complementares

### Restrições e Dependências

- Nenhuma restrição adicional identificada.

### Notas e Suposições

- O comportamento descrito vale para o commit de referência.

### Anexos / Referências

- Verificação: `test_world_manager_result_queue_safe_without_gl`; `test_world_manager_reports_each_pending_streaming_stage`.
- Documento de origem: `requirements.md`

---
