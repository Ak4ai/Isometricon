# REQ-PERF-003 — Montagem do personagem em segundo plano

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `PR-003`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `SRS.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `PR-003` |
| **Nome** | Montagem do personagem em segundo plano |
| **Tipo** | Performance |
| **Prioridade** | Essencial |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O sistema deve montar o personagem em thread separada e trocar as malhas no laço principal, mantendo o modelo anterior enquanto a montagem ocorre.

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
| **Rastreabilidade técnica** | `test_async_model_defers_reloads_to_poll`; `test_character_model_init_without_gl`. |

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
Funcionalidade: Montagem do personagem em segundo plano
  Cenário: Exercitar Montagem do personagem em segundo plano
    Dado que o sistema opera com dados e carga compatíveis com o requisito
    Quando a condição de desempenho é exercitada
    Então o personagem é montado em thread e trocado no laço principal
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | `test_async_model_defers_reloads_to_poll`; `test_character_model_init_without_gl`. | O sistema deve montar o personagem em thread separada e trocar as malhas no laço principal, mantendo o modelo anterior enquanto a montagem ocorre. |

Testes existentes: `tests/test_async_model_defers_reloads_to_poll.py`, `tests/test_character_model_init_without_gl.py`.

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

- Verificação: `test_async_model_defers_reloads_to_poll`; `test_character_model_init_without_gl`.
- Documento de origem: `SRS.md`

---
