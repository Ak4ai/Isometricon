# REQ-FUNC-026 — Cabelo

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-026`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `SRS.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-026` |
| **Nome** | Cabelo |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O sistema deve vestir o cabelo padrão, cabelos do catálogo Roblox encaixados na cabeça e cabelos feitos à mão, com cor, posição, escala e degradê de opacidade.

### Condições de Aplicação

- Corpo escolhido; cabelo selecionado por comando, ID ou estilo.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/clothing/hair_fit.py`; `src/clothing/character_model.py`; `tests/test_hair_fit.py`. |

---

## Justificativa (Rationale)

O cabelo completa a silhueta e usa o catálogo Roblox.

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
Funcionalidade: Cabelo
  Cenário: Exercitar Cabelo
    Dado o personagem com cabelo padrão
    Quando o usuário escolhe nudred ou um cabelo do catálogo
    Então o cabelo é vestido na cabeça do corpo e cor e posição podem ser ajustadas
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste automatizado (`tests/test_hair_fit.py`; `tests/test_character_model.py`; `tests/test_body_shape.py`, casos de cabelo). | O cabelo padrão é usado quando nenhum é escolhido; cabelos do catálogo assentam na cabeça de cada corpo; nudred e raspado são vestidos sem download; o degradê deixa a pele aparecer. |

Testes existentes: `tests/test_hair_fit.py`, `tests/test_character_model.py`, `tests/test_body_shape.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial para cabelo. |
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

- Código/testes: `src/clothing/hair_fit.py`; `src/clothing/character_model.py`; `tests/test_hair_fit.py`.
- Documento de origem: `SRS.md`

---
