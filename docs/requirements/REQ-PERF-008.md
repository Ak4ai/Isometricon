# REQ-PERF-008 — Resposta de edição no quadro seguinte

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `PR-008`
> **Origem:** incremento proposto
> **Arquivo-fonte:** `INCREMENTO-EDITOR-VOXEL.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `PR-008` |
| **Nome** | Resposta de edição no quadro seguinte |
| **Tipo** | Performance |
| **Prioridade** | Essencial |
| **Status** | Proposto |

---

## Descrição

### Texto do Requisito

> Uma operação de colocação, remoção ou pintura em um objeto de até 32³ voxels deve aparecer na tela no quadro seguinte à ação.

### Condições de Aplicação

- o sistema opera com dados e carga compatíveis com o requisito

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Pedido de extensão de 21/10/2026 e pesquisa do Replicube |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | Teste de tempo (a criar); demonstração. |

---

## Justificativa (Rationale)

Garante resposta interativa e uso previsível de recursos.

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
Funcionalidade: Resposta de edição no quadro seguinte
  Cenário: Exercitar Resposta de edição no quadro seguinte
    Dado que o sistema opera com dados e carga compatíveis com o requisito
    Quando a condição de desempenho é exercitada
    Então a edição em objeto 32³ aparece no quadro seguinte
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste de tempo (a criar); demonstração. | Uma operação de colocação, remoção ou pintura em um objeto de até 32³ voxels deve aparecer na tela no quadro seguinte à ação. |

Testes existentes: A criar (nenhum teste existe no baseline).

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial de desempenho. |
| **Appropriate (Apropriado)** | [x] Sim [ ] Não | Descreve comportamento ou restrição, sem impor implementação. |
| **Unambiguous (Não ambíguo)** | [x] Sim [ ] Não | Redação única, com condição e critério de aceitação. |
| **Complete (Completo)** | [x] Sim [ ] Não | Texto, condição, verificação e rastreabilidade declarados. |
| **Singular (Singular)** | [x] Sim [ ] Não | Trata de uma única capacidade ou restrição. |
| **Feasible (Factível)** | [x] Sim [ ] Não | Previsto no incremento proposto. |
| **Verifiable (Verificável)** | [x] Sim [ ] Não | Método: Teste, Demonstração. |
| **Correct (Correto)** | [x] Sim [ ] Não | Rastreável à fonte declarada. |
| **Conforming (Conforme)** | [x] Sim [ ] Não | Segue este template e a ISO/IEC/IEEE 29148:2018. |

---

## Informações Complementares

### Restrições e Dependências

- Nenhuma restrição adicional identificada.

### Notas e Suposições

- Requisito proposto; ainda não implementado.

### Anexos / Referências

- Verificação: Teste de tempo (a criar); demonstração.
- Documento de origem: `INCREMENTO-EDITOR-VOXEL.md`

---
