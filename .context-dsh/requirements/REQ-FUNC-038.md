# REQ-FUNC-038 — Textura individual por voxel

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-038`
> **Origem:** incremento proposto
> **Arquivo-fonte:** `requirements-voxel-editor.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-038` |
| **Nome** | Textura individual por voxel |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Proposto |

---

## Descrição

### Texto do Requisito

> O editor deve permitir atribuir a cada voxel uma textura de uma biblioteca de texturas, de modo que dois voxels da mesma cor possam exibir texturas diferentes e que a textura escolhida seja preservada ao exportar e ao colocar o objeto no mundo.

### Condições de Aplicação

- Ferramenta de textura ativa; biblioteca carregada; voxel existente ou novo.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Pedido de extensão de 21/10/2026 e pesquisa do Replicube (ver `requirements-voxel-editor.md`) |
| **Requisito Pai** | FR-010 |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | Atlas/tabela de materiais; mesher precisa emitir UV e material por voxel; textura adicional no shader. |

---

## Justificativa (Rationale)

Texturas individuais são o diferencial em relação a editores apenas de cor.

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
Funcionalidade: Textura individual por voxel
  Cenário: Exercitar Textura individual por voxel
    Dado dois voxels de mesma cor
    Quando o usuário aplica texturas diferentes a cada um
    Então eles exibem texturas distintas e a escolha sobrevive ao exportar e importar
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste unitário de atribuição e serialização (a criar); demonstração. | Texturas distintas aparecem em voxels vizinhos; a textura sobrevive ao salvar, exportar e importar; voxel sem textura usa a cor sólida; textura ausente cai em uma textura padrão visível. |

Testes existentes: A criar (nenhum teste existe no baseline).

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial para textura individual por voxel. |
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

- Requisitos relacionados: FR-010, FR-036, FR-037

### Notas e Suposições

- Requisito proposto; ainda não implementado.
- O requisito é proposto e pode mudar até a implementação.

### Anexos / Referências

- Código/testes: Atlas/tabela de materiais; mesher precisa emitir UV e material por voxel; textura adicional no shader.
- Documento de origem: `requirements-voxel-editor.md`

---
