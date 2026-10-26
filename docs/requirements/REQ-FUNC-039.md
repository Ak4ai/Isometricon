# REQ-FUNC-039 — Tamanho do volume de edição

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-039`
> **Origem:** incremento proposto
> **Arquivo-fonte:** `INCREMENTO-EDITOR-VOXEL.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-039` |
| **Nome** | Tamanho do volume de edição |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Proposto |

---

## Descrição

### Texto do Requisito

> O editor deve permitir definir as dimensões X, Y e Z do volume de edição dentro de limites declarados, exibir o volume delimitado na plataforma e preservar os voxels existentes que couberem no novo tamanho.

### Condições de Aplicação

- Projeto novo ou existente; painel de configurações do grid aberto.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Pedido de extensão de 21/10/2026 e pesquisa do Replicube (ver `INCREMENTO-EDITOR-VOXEL.md`) |
| **Requisito Pai** | FR-013 |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | Modelo de projeto com dimensões próprias; não confundir com `Chunk3D.SIZE = 16`. |

---

## Justificativa (Rationale)

O tamanho do volume define o escopo de cada construção.

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
Funcionalidade: Tamanho do volume de edição
  Cenário: Exercitar Tamanho do volume de edição
    Dado um volume 16×16×16 com voxels
    Quando o usuário muda para 32×32×32
    Então a plataforma cresce, os voxels existentes permanecem e os fora do novo volume são informados
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste unitário de redimensionamento (a criar); demonstração. | Alterar as dimensões atualiza a plataforma e os limites; voxels dentro do novo volume permanecem; voxels fora são informados e não são apagados sem confirmação; dimensão inválida é rejeitada. |

Testes existentes: A criar (nenhum teste existe no baseline).

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial para tamanho do volume de edição. |
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

- Requisitos relacionados: FR-013, FR-040, FR-045

### Notas e Suposições

- Requisito proposto; ainda não implementado.
- O requisito é proposto e pode mudar até a implementação.

### Anexos / Referências

- Código/testes: Modelo de projeto com dimensões próprias; não confundir com `Chunk3D.SIZE = 16`.
- Documento de origem: `INCREMENTO-EDITOR-VOXEL.md`

---
