# REQ-FUNC-008 — Frustum culling

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-008`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `requirements.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-008` |
| **Nome** | Frustum culling |
| **Tipo** | Funcional |
| **Prioridade** | Desejável |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O sistema deve deixar de desenhar chunks cujos oito cantos ficam fora de um mesmo plano do frustum, mantendo visível o chunk que contém o foco da câmera.

### Condições de Aplicação

- Renderização do mundo com matriz de projeção e visão válidas.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/world/manager.py` (`render`); `tests/test_interactive.py`. |

---

## Justificativa (Rationale)

Chunks fora da visão não devem custar desenho.

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
Funcionalidade: Frustum culling
  Cenário: Exercitar Frustum culling
    Dado um chunk fora do frustum e outro no foco
    Quando o mundo é renderizado
    Então o chunk fora é descartado e o do foco é desenhado
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste automatizado (`tests/test_interactive.py`, casos de frustum culling). | Um chunk distante do foco é descartado quando fora do frustum; o chunk do foco permanece desenhado. |

Testes existentes: `tests/test_interactive.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito desejável para frustum culling. |
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

- Código/testes: `src/world/manager.py` (`render`); `tests/test_interactive.py`.
- Documento de origem: `requirements.md`

---
