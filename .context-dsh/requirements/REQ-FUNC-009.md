# REQ-FUNC-009 — Água

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-009`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `requirements.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-009` |
| **Nome** | Água |
| **Tipo** | Funcional |
| **Prioridade** | Desejável |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O sistema deve propagar água entre células de ar dentro dos chunks carregados, reduzindo o nível a cada avanço, e refletir a altura parcial da água na malha renderizada.

### Condições de Aplicação

- Chunks carregados com água e células de ar vizinhas; modo terreno.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/world/manager.py` (`_simulate_water`); `src/world/mesher.py` (`water_levels`); `tests/test_interactive.py`. |

---

## Justificativa (Rationale)

A água faz parte do terreno e precisa de comportamento visual coerente.

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
Funcionalidade: Água
  Cenário: Exercitar Água
    Dado água cercada por ar em chunks carregados
    Quando a simulação avança
    Então a água desce, depois espalha, e a malha usa a altura parcial
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste automatizado (`tests/test_interactive.py`, três casos de água e o teste de altura reduzida). | A água desce antes de espalhar; o volume permanece finito no teste; a superfície renderizada fica abaixo do topo do voxel quando o nível é menor que 1. |

Testes existentes: `tests/test_interactive.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito desejável para água. |
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

- Código/testes: `src/world/manager.py` (`_simulate_water`); `src/world/mesher.py` (`water_levels`); `tests/test_interactive.py`.
- Documento de origem: `requirements.md`

---
