# REQ-FUNC-041 — Formato e exportação de objeto voxel

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-041`
> **Origem:** incremento proposto
> **Arquivo-fonte:** `INCREMENTO-EDITOR-VOXEL.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-041` |
| **Nome** | Formato e exportação de objeto voxel |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Proposto |

---

## Descrição

### Texto do Requisito

> O sistema deve salvar e exportar um objeto voxel em um formato aberto e documentado que preserve dimensões, voxels vazios, cor, textura e metadados do objeto, com gravação atômica e recusa de arquivos inválidos.

### Condições de Aplicação

- Objeto em edição; comando de salvar ou exportar; caminho de destino.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Pedido de extensão de 21/10/2026 e pesquisa do Replicube (ver `INCREMENTO-EDITOR-VOXEL.md`) |
| **Requisito Pai** | FR-036 |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | Novo módulo de serialização de objeto; formato JSON (legível) e, se necessário, carga binária opcional. |

---

## Justificativa (Rationale)

Sem formato persistente o objeto não sai do editor.

---

## Critérios de Verificação e Aceitação

### Método de Verificação

- [x] Inspeção / Revisão
- [x] Teste
- [ ] Demonstração
- [ ] Análise
- [ ] Simulação

### Critérios de Aceitação (Gherkin)

```gherkin
Funcionalidade: Formato e exportação de objeto voxel
  Cenário: Exercitar Formato e exportação de objeto voxel
    Dado um objeto voxel com cor e textura
    Quando o usuário salva e reabre o objeto
    Então dimensões, voxels, cores e texturas são idênticos
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste de round-trip (a criar); teste de arquivo corrompido; inspeção do formato documentado. | Salvar e reabrir reproduz o mesmo objeto; exportar e importar reproduz dimensões, cores e texturas; arquivo inválido é rejeitado sem apagar o objeto em memória; o formato tem identificador e versão. |

Testes existentes: A criar (nenhum teste existe no baseline).

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial para formato e exportação de objeto voxel. |
| **Appropriate (Apropriado)** | [x] Sim [ ] Não | Descreve comportamento ou restrição, sem impor implementação. |
| **Unambiguous (Não ambíguo)** | [x] Sim [ ] Não | Redação única, com condições e critério de aceitação. |
| **Complete (Completo)** | [x] Sim [ ] Não | Texto, condições, verificação e rastreabilidade declarados. |
| **Singular (Singular)** | [x] Sim [ ] Não | Trata de uma única capacidade ou restrição. |
| **Feasible (Factível)** | [x] Sim [ ] Não | Previsto no incremento proposto. |
| **Verifiable (Verificável)** | [x] Sim [ ] Não | Método: Inspeção / Revisão, Teste. |
| **Correct (Correto)** | [x] Sim [ ] Não | Rastreável à fonte declarada. |
| **Conforming (Conforme)** | [x] Sim [ ] Não | Segue este template e a ISO/IEC/IEEE 29148:2018. |

---

## Informações Complementares

### Restrições e Dependências

- Requisitos relacionados: FR-036, FR-037, FR-038, DR-006

### Notas e Suposições

- Requisito proposto; ainda não implementado.
- O requisito é proposto e pode mudar até a implementação.

### Anexos / Referências

- Código/testes: Novo módulo de serialização de objeto; formato JSON (legível) e, se necessário, carga binária opcional.
- Documento de origem: `INCREMENTO-EDITOR-VOXEL.md`

---
