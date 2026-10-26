# REQ-FUNC-010 — Texturização de blocos

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-010`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `SRS.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-010` |
| **Nome** | Texturização de blocos |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O sistema deve texturizar os tipos de bloco com um atlas de 12 tiles de 16×16 pixels, aplicar coordenadas UV por tipo e face e modular a cor do vértice pelo tom do material.

### Condições de Aplicação

- Renderização do mundo; atlas carregado de `assets/textures/blocks`.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/rendering/atlas.py`; `src/world/mesher.py`; `tests/test_atlas.py`. |

---

## Justificativa (Rationale)

As texturas dão identidade aos blocos e material ao tabuleiro.

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
Funcionalidade: Texturização de blocos
  Cenário: Exercitar Texturização de blocos
    Dado o atlas com 12 tiles
    Quando o mesher gera um bloco de grama
    Então topo, laterais e base usam tiles distintos com a cor de modulação correta
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste automatizado (`tests/test_atlas.py`; `tests/test_mesher.py`, casos de UV e cor). | Tipos distintos recebem tiles distintos; grama usa topo/lateral/baixo diferentes; o filtro é nearest e a borda é clampeada. |

Testes existentes: `tests/test_atlas.py`, `tests/test_mesher.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial para texturização de blocos. |
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

- Código/testes: `src/rendering/atlas.py`; `src/world/mesher.py`; `tests/test_atlas.py`.
- Documento de origem: `SRS.md`

---
