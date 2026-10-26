# REQ-CONS-010 — Modo editor aditivo

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `CR-010`
> **Origem:** incremento proposto
> **Arquivo-fonte:** `requirements-voxel-editor.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `CR-010` |
| **Nome** | Modo editor aditivo |
| **Tipo** | Restrição de Design |
| **Prioridade** | Essencial |
| **Status** | Proposto |

---

## Descrição

### Texto do Requisito

> O modo editor deve ser aditivo: os modos atuais (`--terrain`, `--char` e demonstração), os requisitos FR-001 a FR-034 e o editor de personagem devem continuar funcionando sem alteração de comportamento.

### Condições de Aplicação

- o código-fonte e o ambiente de execução estão disponíveis

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Pedido de extensão de 21/10/2026 e pesquisa do Replicube |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | Execução da suíte atual; teste de regressão (a criar). |

---

## Justificativa (Rationale)

Preserva o escopo e a arquitetura definidos para o projeto.

---

## Critérios de Verificação e Aceitação

### Método de Verificação

- [ ] Inspeção / Revisão
- [x] Teste
- [ ] Demonstração
- [ ] Análise
- [ ] Simulação

### Critérios de Aceitação (Gherkin)

```gherkin
Funcionalidade: Modo editor aditivo
  Cenário: Exercitar Modo editor aditivo
    Dado que o código-fonte e o ambiente de execução estão disponíveis
    Quando a restrição é verificada
    Então os modos atuais e FR-001 a FR-034 continuam funcionando
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Execução da suíte atual; teste de regressão (a criar). | O modo editor deve ser aditivo: os modos atuais (`--terrain`, `--char` e demonstração), os requisitos FR-001 a FR-034 e o editor de personagem devem continuar funcionando sem alteração de comportamento. |

Testes existentes: A criar (nenhum teste existe no baseline).

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial de restrição de design. |
| **Appropriate (Apropriado)** | [x] Sim [ ] Não | Descreve comportamento ou restrição, sem impor implementação. |
| **Unambiguous (Não ambíguo)** | [x] Sim [ ] Não | Redação única, com condição e critério de aceitação. |
| **Complete (Completo)** | [x] Sim [ ] Não | Texto, condição, verificação e rastreabilidade declarados. |
| **Singular (Singular)** | [x] Sim [ ] Não | Trata de uma única capacidade ou restrição. |
| **Feasible (Factível)** | [x] Sim [ ] Não | Previsto no incremento proposto. |
| **Verifiable (Verificável)** | [x] Sim [ ] Não | Método: Teste. |
| **Correct (Correto)** | [x] Sim [ ] Não | Rastreável à fonte declarada. |
| **Conforming (Conforme)** | [x] Sim [ ] Não | Segue este template e a ISO/IEC/IEEE 29148:2018. |

---

## Informações Complementares

### Restrições e Dependências

- Nenhuma restrição adicional identificada.

### Notas e Suposições

- Requisito proposto; ainda não implementado.

### Anexos / Referências

- Verificação: Execução da suíte atual; teste de regressão (a criar).
- Documento de origem: `requirements-voxel-editor.md`

---
