# REQ-FUNC-012 — Seleção de bloco por cursor

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-012`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `SRS.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-012` |
| **Nome** | Seleção de bloco por cursor |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O sistema deve converter a posição do cursor em um raio no espaço do mundo, percorrer os voxels até 256 unidades e identificar o primeiro bloco diferente de ar, informando bloco, tipo, face e distância.

### Condições de Aplicação

- Modo terreno; cursor dentro da janela; fora de gesto de pan.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/interaction/raycast.py`; `src/main.py`; `tests/test_raycast.py`. |

---

## Justificativa (Rationale)

A seleção por cursor é a base de toda interação com o tabuleiro.

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
Funcionalidade: Seleção de bloco por cursor
  Cenário: Exercitar Seleção de bloco por cursor
    Dado o cursor sobre um bloco carregado
    Quando o quadro calcula o hover e o clique
    Então o primeiro bloco não-ar é identificado com face e distância e o clique o registra no terminal
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste automatizado (`tests/test_raycast.py`, 28 casos). | O centro da tela aponta para o alvo da câmera; coordenadas negativas usam `floor`; água e folhas são atingíveis; o clique registra o resultado no terminal. |

Testes existentes: `tests/test_raycast.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial para seleção de bloco por cursor. |
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

- Código/testes: `src/interaction/raycast.py`; `src/main.py`; `tests/test_raycast.py`.
- Documento de origem: `SRS.md`

---
