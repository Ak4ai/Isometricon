# REQ-FUNC-006 — Chunks e face culling

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-006`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `requirements.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-006` |
| **Nome** | Chunks e face culling |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O sistema deve armazenar voxels em chunks de 16×16×16 com identificadores `uint8`, validar coordenadas locais e gerar malha apenas para faces expostas, consultando vizinhos de chunks adjacentes.

### Condições de Aplicação

- Construção de malha por `ChunkMesher.build`, com ou sem callback de vizinhança.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/world/chunk.py`; `src/world/mesher.py`; `tests/test_world.py`; `tests/test_mesher.py`. |

---

## Justificativa (Rationale)

O culling reduz vértices e mantém o mundo renderizável.

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
Funcionalidade: Chunks e face culling
  Cenário: Exercitar Chunks e face culling
    Dado um chunk com blocos
    Quando o mesher constrói a malha com vizinhança
    Então faces internas são omitidas e cada célula exposta gera quatro vértices
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste automatizado (`tests/test_world.py` 17 casos; `tests/test_mesher.py` 15 casos). | Um chunk vazio não gera vértices; um cubo 2×2×2 gera 24 faces; blocos adjacentes não geram faces internas; água e folhas não ocultam faces. |

Testes existentes: `tests/test_world.py`, `tests/test_mesher.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial para chunks e face culling. |
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

- Código/testes: `src/world/chunk.py`; `src/world/mesher.py`; `tests/test_world.py`; `tests/test_mesher.py`.
- Documento de origem: `requirements.md`

---
