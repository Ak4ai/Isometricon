# REQ-PERF-006 — Limites de raycast e colisão

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `PR-006`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `SRS.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `PR-006` |
| **Nome** | Limites de raycast e colisão |
| **Tipo** | Performance |
| **Prioridade** | Essencial |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O sistema deve limitar o alcance do raycast a 256 unidades e subdividir deslocamentos de colisão para impedir atravessar blocos.

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
| **Rastreabilidade técnica** | `tests/test_raycast.py`; `tests/test_voxel_collision.py` (tunneling). |

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
Funcionalidade: Limites de raycast e colisão
  Cenário: Exercitar Limites de raycast e colisão
    Dado que o sistema opera com dados e carga compatíveis com o requisito
    Quando a condição de desempenho é exercitada
    Então o raycast para em 256 unidades e a colisão não atravessa blocos
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | `tests/test_raycast.py`; `tests/test_voxel_collision.py` (tunneling). | O sistema deve limitar o alcance do raycast a 256 unidades e subdividir deslocamentos de colisão para impedir atravessar blocos. |

Testes existentes: `tests/test_raycast.py`, `tests/test_voxel_collision.py`.

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

- Verificação: `tests/test_raycast.py`; `tests/test_voxel_collision.py` (tunneling).
- Documento de origem: `SRS.md`

---
