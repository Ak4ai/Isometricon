# REQ-FUNC-005 — Cavernas tridimensionais

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-005`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `SRS.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-005` |
| **Nome** | Cavernas tridimensionais |
| **Tipo** | Funcional |
| **Prioridade** | Desejável |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O sistema deve escavar cavernas determinísticas em formato de túneis e salões, criar entradas de superfície quando sorteado e preservar blocos de água durante a escavação.

### Condições de Aplicação

- `TerrainGenerator(enable_caves=True)`; colunas geradas.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/world/caves.py`; `src/world/terrain.py`; `tests/test_caves.py`. |

---

## Justificativa (Rationale)

As cavernas dão profundidade e exploração ao subterrâneo.

---

## Critérios de Verificação e Aceitação

### Método de Verificação

- [ ] Inspeção / Revisão
- [x] Teste
- [ ] Demonstração
- [ ] Análise
- [ ] Simulação

### Critérios de Aceitação (Gherkin)

```gherkin
Funcionalidade: Cavernas tridimensionais
  Cenário: Exercitar Cavernas tridimensionais
    Dado um terreno com enable_caves e uma seed
    Quando as cavernas são geradas
    Então túneis e salões são determinísticos e nenhum bloco de água é removido
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste automatizado (`tests/test_caves.py`, 11 casos). | Duas gerações com a mesma seed produzem as mesmas cavernas; nenhum bloco de água é removido; cavernas profundas podem criar chunks em Y negativo. |

Testes existentes: `tests/test_caves.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito desejável para cavernas tridimensionais. |
| **Appropriate (Apropriado)** | [x] Sim [ ] Não | Descreve comportamento ou restrição, sem impor implementação. |
| **Unambiguous (Não ambíguo)** | [x] Sim [ ] Não | Redação única, com condições e critério de aceitação. |
| **Complete (Completo)** | [x] Sim [ ] Não | Texto, condições, verificação e rastreabilidade declarados. |
| **Singular (Singular)** | [x] Sim [ ] Não | Trata de uma única capacidade ou restrição. |
| **Feasible (Factível)** | [x] Sim [ ] Não | Implementado no baseline. |
| **Verifiable (Verificável)** | [x] Sim [ ] Não | Método: Teste. |
| **Correct (Correto)** | [x] Sim [ ] Não | Rastreável à fonte declarada. |
| **Conforming (Conforme)** | [x] Sim [ ] Não | Segue este template e a ISO/IEC/IEEE 29148:2018. |

---

## Informações Complementares

### Restrições e Dependências

- Requisitos relacionados: —

### Notas e Suposições

- Nenhuma observação adicional.
- O comportamento descrito vale para o commit de referência.

### Anexos / Referências

- Código/testes: `src/world/caves.py`; `src/world/terrain.py`; `tests/test_caves.py`.
- Documento de origem: `SRS.md`

---
