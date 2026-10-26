# REQ-FUNC-042 — Colocar objeto no mundo isométrico

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-042`
> **Origem:** incremento proposto
> **Arquivo-fonte:** `INCREMENTO-EDITOR-VOXEL.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-042` |
| **Nome** | Colocar objeto no mundo isométrico |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Proposto |

---

## Descrição

### Texto do Requisito

> O sistema deve permitir escolher um objeto voxel e colocá-lo no mundo isométrico em uma posição da grade, com prévia visual, encaixe na superfície, rotação em passos de 90° e confirmação ou cancelamento antes de efetivar.

### Condições de Aplicação

- Mundo carregado; objeto disponível na biblioteca ou recém-criado; ferramenta de colocação ativa.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Pedido de extensão de 21/10/2026 e pesquisa do Replicube (ver `INCREMENTO-EDITOR-VOXEL.md`) |
| **Requisito Pai** | FR-007 |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | Objetos podem ocupar vários chunks; é preciso remalhar os chunks afetados e atualizar colisão/grid. |

---

## Justificativa (Rationale)

É o elo entre o objeto criado e o mundo isométrico jogável.

---

## Critérios de Verificação e Aceitação

### Método de Verificação

- [ ] Inspeção / Revisão
- [x] Teste
- [x] Demonstração
- [ ] Análise
- [ ] Simulação

### Critérios de Aceitação (Gherkin)

```gherkin
Funcionalidade: Colocar objeto no mundo isométrico
  Cenário: Exercitar Colocar objeto no mundo isométrico
    Dado uma casa na biblioteca
    Quando o usuário posiciona a prévia sobre o terreno e confirma
    Então a casa é gravada no mapa, os chunks afetados são remalhados e o token colide com ela
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste de integração (a criar): colocar uma casa, confirmar, salvar e reabrir; demonstração. | A prévia acompanha o cursor e indica posição válida ou inválida; confirmar grava o objeto no mapa; cancelar não altera o mapa; a rotação muda o objeto em 90°; a colocação atualiza todos os chunks afetados; o token passa a colidir com os voxels colocados. |

Testes existentes: A criar (nenhum teste existe no baseline).

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial para colocar objeto no mundo isométrico. |
| **Appropriate (Apropriado)** | [x] Sim [ ] Não | Descreve comportamento ou restrição, sem impor implementação. |
| **Unambiguous (Não ambíguo)** | [x] Sim [ ] Não | Redação única, com condições e critério de aceitação. |
| **Complete (Completo)** | [x] Sim [ ] Não | Texto, condições, verificação e rastreabilidade declarados. |
| **Singular (Singular)** | [x] Sim [ ] Não | Trata de uma única capacidade ou restrição. |
| **Feasible (Factível)** | [x] Sim [ ] Não | Previsto no incremento proposto. |
| **Verifiable (Verificável)** | [x] Sim [ ] Não | Método: Teste, Demonstração. |
| **Correct (Correto)** | [x] Sim [ ] Não | Rastreável à fonte declarada. |
| **Conforming (Conforme)** | [x] Sim [ ] Não | Segue este template e a ISO/IEC/IEEE 29148:2018. |

---

## Informações Complementares

### Restrições e Dependências

- Requisitos relacionados: FR-007, FR-012, FR-013, FR-016, FR-041

### Notas e Suposições

- Requisito proposto; ainda não implementado.
- O requisito é proposto e pode mudar até a implementação.

### Anexos / Referências

- Código/testes: Objetos podem ocupar vários chunks; é preciso remalhar os chunks afetados e atualizar colisão/grid.
- Documento de origem: `INCREMENTO-EDITOR-VOXEL.md`

---
