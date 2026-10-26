# REQ-FUNC-036 — Edição de voxels

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-036`
> **Origem:** incremento proposto
> **Arquivo-fonte:** `INCREMENTO-EDITOR-VOXEL.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-036` |
| **Nome** | Edição de voxels |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Proposto |

---

## Descrição

### Texto do Requisito

> O editor deve permitir colocar, remover e pintar voxels em um volume de edição, com ferramenta ativa, tamanho de pincel de 1 a 8 voxels e indicação visual da célula sob o cursor.

### Condições de Aplicação

- Modo editor; plataforma visível; ferramenta de construção, remoção ou pintura selecionada.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Pedido de extensão de 21/10/2026 e pesquisa do Replicube (ver `INCREMENTO-EDITOR-VOXEL.md`) |
| **Requisito Pai** | FR-006 |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | Novo modelo de edição; raycast atual para a célula; malha do objeto atualizada por edição. |

---

## Justificativa (Rationale)

Colocar, remover e pintar são as operações básicas de um editor voxel.

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
Funcionalidade: Edição de voxels
  Cenário: Exercitar Edição de voxels
    Dado a ferramenta de colocação com pincel 2
    Quando o usuário clica e arrasta na plataforma
    Então os voxels do bloco ao redor do cursor são criados e a malha é atualizada
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste unitário do modelo de edição (a criar); teste de integração de colocação/remoção; demonstração. | Colocar cria um voxel na célula indicada; remover esvazia a célula; pintar altera apenas a célula atingida; o pincel maior afeta o bloco de células ao redor do centro; arrastar aplica a ferramenta de forma contínua. |

Testes existentes: A criar (nenhum teste existe no baseline).

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial para edição de voxels. |
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

- Requisitos relacionados: FR-006, FR-012, FR-040

### Notas e Suposições

- Requisito proposto; ainda não implementado.
- O requisito é proposto e pode mudar até a implementação.

### Anexos / Referências

- Código/testes: Novo modelo de edição; raycast atual para a célula; malha do objeto atualizada por edição.
- Documento de origem: `INCREMENTO-EDITOR-VOXEL.md`

---
