# REQ-PERF-005 — Grade em uma chamada e por revisão

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `PR-005`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `requirements.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `PR-005` |
| **Nome** | Grade em uma chamada e por revisão |
| **Tipo** | Performance |
| **Prioridade** | Desejável |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O sistema deve reconstruir a malha da grade apenas quando a revisão dos chunks mudar e desenhá-la em uma única chamada de linhas.

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
| **Rastreabilidade técnica** | `test_visibility_toggle_skips_snapshot_sync_when_hidden_without_gl_context`; inspeção de `grid_overlay.py`. |

---

## Justificativa (Rationale)

Garante resposta interativa e uso previsível de recursos.

---

## Critérios de Verificação e Aceitação

### Método de Verificação

- [x] Inspeção / Revisão
- [ ] Teste
- [ ] Demonstração
- [ ] Análise
- [ ] Simulação

### Critérios de Aceitação (Gherkin)

```gherkin
Funcionalidade: Grade em uma chamada e por revisão
  Cenário: Exercitar Grade em uma chamada e por revisão
    Dado que o sistema opera com dados e carga compatíveis com o requisito
    Quando a condição de desempenho é exercitada
    Então a grade é refeita só por revisão e desenhada em uma chamada
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | `test_visibility_toggle_skips_snapshot_sync_when_hidden_without_gl_context`; inspeção de `grid_overlay.py`. | O sistema deve reconstruir a malha da grade apenas quando a revisão dos chunks mudar e desenhá-la em uma única chamada de linhas. |

Testes existentes: `tests/test_visibility_toggle_skips_snapshot_sync_when_hidden_without_gl_context.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito desejável de desempenho. |
| **Appropriate (Apropriado)** | [x] Sim [ ] Não | Descreve comportamento ou restrição, sem impor implementação. |
| **Unambiguous (Não ambíguo)** | [x] Sim [ ] Não | Redação única, com condição e critério de aceitação. |
| **Complete (Completo)** | [x] Sim [ ] Não | Texto, condição, verificação e rastreabilidade declarados. |
| **Singular (Singular)** | [x] Sim [ ] Não | Trata de uma única capacidade ou restrição. |
| **Feasible (Factível)** | [x] Sim [ ] Não | Implementado no baseline. |
| **Verifiable (Verificável)** | [x] Sim [ ] Não | Método: Inspeção / Revisão. |
| **Correct (Correto)** | [x] Sim [ ] Não | Rastreável à fonte declarada. |
| **Conforming (Conforme)** | [x] Sim [ ] Não | Segue este template e a ISO/IEC/IEEE 29148:2018. |

---

## Informações Complementares

### Restrições e Dependências

- Nenhuma restrição adicional identificada.

### Notas e Suposições

- O comportamento descrito vale para o commit de referência.

### Anexos / Referências

- Verificação: `test_visibility_toggle_skips_snapshot_sync_when_hidden_without_gl_context`; inspeção de `grid_overlay.py`.
- Documento de origem: `requirements.md`

---
