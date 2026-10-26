# REQ-FUNC-043 — Biblioteca de objetos

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-043`
> **Origem:** incremento proposto
> **Arquivo-fonte:** `INCREMENTO-EDITOR-VOXEL.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-043` |
| **Nome** | Biblioteca de objetos |
| **Tipo** | Funcional |
| **Prioridade** | Desejável |
| **Status** | Proposto |

---

## Descrição

### Texto do Requisito

> O editor deve listar os objetos disponíveis com nome, miniatura e categoria, permitir importar um objeto de arquivo, duplicar e excluir objetos, e manter a lista atualizada após salvar um objeto novo.

### Condições de Aplicação

- Modo editor; diretório de objetos acessível.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Pedido de extensão de 21/10/2026 e pesquisa do Replicube (ver `INCREMENTO-EDITOR-VOXEL.md`) |
| **Requisito Pai** | FR-034 |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | Reaproveita o padrão de catálogo/miniaturas do editor de personagem; novo diretório de objetos. |

---

## Justificativa (Rationale)

Reaproveitar objetos acelera a criação de mapas.

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
Funcionalidade: Biblioteca de objetos
  Cenário: Exercitar Biblioteca de objetos
    Dado um objeto salvo
    Quando o editor recarrega a biblioteca
    Então o objeto aparece com nome e miniatura e pode ser importado, duplicado ou excluído
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste unitário do catálogo (a criar); demonstração. | Objeto novo aparece na lista sem reiniciar; miniatura ausente é gerada ou substituída por marcador; importar arquivo válido adiciona o objeto; excluir pede confirmação. |

Testes existentes: A criar (nenhum teste existe no baseline).

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito desejável para biblioteca de objetos. |
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

- Requisitos relacionados: FR-034, FR-041

### Notas e Suposições

- Requisito proposto; ainda não implementado.
- O requisito é proposto e pode mudar até a implementação.

### Anexos / Referências

- Código/testes: Reaproveita o padrão de catálogo/miniaturas do editor de personagem; novo diretório de objetos.
- Documento de origem: `INCREMENTO-EDITOR-VOXEL.md`

---
