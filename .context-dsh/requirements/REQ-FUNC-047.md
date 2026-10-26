# REQ-FUNC-047 — Selecionar e transformar objetos

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-047`
> **Origem:** incremento proposto
> **Arquivo-fonte:** `requirements-voxel-editor.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-047` |
| **Nome** | Selecionar e transformar objetos |
| **Tipo** | Funcional |
| **Prioridade** | Desejável |
| **Status** | Proposto |

---

## Descrição

### Texto do Requisito

> O editor deve permitir selecionar um objeto colocado por clique, exibir sua caixa delimitadora e movê-lo, rotacioná-lo em 90°, duplicá-lo e excluí-lo, mantendo o resultado no mapa salvo.

### Condições de Aplicação

- Modo editor; objeto colocado no mapa.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Pedido de extensão de 21/10/2026 e pesquisa do Replicube (ver `requirements-voxel-editor.md`) |
| **Requisito Pai** | FR-012 |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | Seleção de objeto por AABB/raycast; transformação e persistência. |

---

## Justificativa (Rationale)

Construções precisam ser reposicionadas sem reconstruir tudo.

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
Funcionalidade: Selecionar e transformar objetos
  Cenário: Exercitar Selecionar e transformar objetos
    Dado uma casa colocada
    Quando o usuário a seleciona, move, rotaciona 90° e duplica
    Então a caixa delimitadora acompanha e o mapa salvo contém as transformações
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste de integração (a criar); demonstração. | O objeto selecionado é destacado; mover atualiza a posição; rotacionar gira o objeto; duplicar cria uma cópia independente; excluir remove o objeto e libera as células; todas as operações entram no histórico. |

Testes existentes: A criar (nenhum teste existe no baseline).

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito desejável para selecionar e transformar objetos. |
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

- Requisitos relacionados: FR-012, FR-042, FR-046

### Notas e Suposições

- Requisito proposto; ainda não implementado.
- O requisito é proposto e pode mudar até a implementação.

### Anexos / Referências

- Código/testes: Seleção de objeto por AABB/raycast; transformação e persistência.
- Documento de origem: `requirements-voxel-editor.md`

---
