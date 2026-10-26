# REQ-FUNC-011 — Iluminação e modo subterrâneo

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-011`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `requirements.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-011` |
| **Nome** | Iluminação e modo subterrâneo |
| **Tipo** | Funcional |
| **Prioridade** | Desejável |
| **Status** | Implementado |

---

## Descrição

### Texto do Requisito

> O sistema deve aplicar iluminação ambiente e direcional às superfícies e, quando o jogador está abaixo da superfície, desenhar o terreno acima dele em um segundo passe translúcido com atenuação por altura.

### Condições de Aplicação

- Renderização do terreno; `get_top_solid_block` disponível no provedor.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `assets/shaders/world_textured.frag`; `src/main.py`; `src/integration/voxel_grid.py`. |

---

## Justificativa (Rationale)

A iluminação e o cutaway tornam o subsolo legível.

---

## Critérios de Verificação e Aceitação

### Método de Verificação

- [x] Inspeção / Revisão
- [ ] Teste
- [x] Demonstração
- [ ] Análise
- [ ] Simulação

### Critérios de Aceitação (Gherkin)

```gherkin
Funcionalidade: Iluminação e modo subterrâneo
  Cenário: Exercitar Iluminação e modo subterrâneo
    Dado o token abaixo da superfície
    Quando o terreno é renderizado
    Então o terreno acima dele aparece translúcido e o token não herda o cutaway
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Inspeção de `assets/shaders/world_textured.frag` e de `src/main.py`; demonstração em `--terrain` cavando até o subsolo. | O terreno acima do jogador fica translúcido no subsolo e opaco na superfície; a miniatura do personagem não herda o cutaway. |

Testes existentes: Inspeção/demonstração.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito desejável para iluminação e modo subterrâneo. |
| **Appropriate (Apropriado)** | [x] Sim [ ] Não | Descreve comportamento ou restrição, sem impor implementação. |
| **Unambiguous (Não ambíguo)** | [x] Sim [ ] Não | Redação única, com condições e critério de aceitação. |
| **Complete (Completo)** | [x] Sim [ ] Não | Texto, condições, verificação e rastreabilidade declarados. |
| **Singular (Singular)** | [x] Sim [ ] Não | Trata de uma única capacidade ou restrição. |
| **Feasible (Factível)** | [x] Sim [ ] Não | Implementado no baseline. |
| **Verifiable (Verificável)** | [x] Sim [ ] Não | Método: Inspeção / Revisão, Demonstração. |
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

- Código/testes: `assets/shaders/world_textured.frag`; `src/main.py`; `src/integration/voxel_grid.py`.
- Documento de origem: `requirements.md`

---
