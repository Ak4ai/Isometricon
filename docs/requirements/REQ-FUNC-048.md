# REQ-FUNC-048 — Feedback visual do editor

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-048`
> **Origem:** incremento proposto
> **Arquivo-fonte:** `INCREMENTO-EDITOR-VOXEL.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-048` |
| **Nome** | Feedback visual do editor |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Proposto |

---

## Descrição

### Texto do Requisito

> O editor deve exibir, durante a edição, a célula sob o cursor, a posição em coordenadas, a ferramenta ativa, o material ativo, os limites do volume e a validade da colocação de um objeto, com distinção visual entre prévia válida e inválida.

### Condições de Aplicação

- Modo editor; cursor sobre a plataforma ou sobre um objeto.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Pedido de extensão de 21/10/2026 e pesquisa do Replicube (ver `INCREMENTO-EDITOR-VOXEL.md`) |
| **Requisito Pai** | FR-014 |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | Reaproveita highlight/HUD; nova camada de prévia. |

---

## Justificativa (Rationale)

Sem feedback o usuário não sabe onde está editando nem o que é válido.

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
Funcionalidade: Feedback visual do editor
  Cenário: Exercitar Feedback visual do editor
    Dado o editor com uma ferramenta ativa
    Quando o cursor percorre a plataforma
    Então célula, coordenadas, ferramenta, material e validade da prévia são exibidos
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Demonstração; teste de estado da prévia (a criar). | O cursor mostra a célula e as coordenadas; a ferramenta e o material ativos são visíveis no painel; a prévia válida e a inválida têm cores distintas; a colocação fora dos limites é recusada com indicação. |

Testes existentes: A criar (nenhum teste existe no baseline).

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial para feedback visual do editor. |
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

- Requisitos relacionados: FR-014, FR-040, UR-006

### Notas e Suposições

- Requisito proposto; ainda não implementado.
- O requisito é proposto e pode mudar até a implementação.

### Anexos / Referências

- Código/testes: Reaproveita highlight/HUD; nova camada de prévia.
- Documento de origem: `INCREMENTO-EDITOR-VOXEL.md`

---
