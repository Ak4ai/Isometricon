# REQ-USA-007 — Prévia de cor e textura

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `UR-007`
> **Origem:** incremento proposto
> **Arquivo-fonte:** `INCREMENTO-EDITOR-VOXEL.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `UR-007` |
| **Nome** | Prévia de cor e textura |
| **Tipo** | Usabilidade |
| **Prioridade** | Desejável |
| **Status** | Proposto |

---

## Descrição

### Texto do Requisito

> A escolha de cor e de textura deve mostrar prévia do material no voxel antes de aplicar e indicar o material ativo no painel.

### Condições de Aplicação

- um usuário opera a interface do sistema

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Pedido de extensão de 21/10/2026 e pesquisa do Replicube |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | Teste de UI (a criar); demonstração. |

---

## Justificativa (Rationale)

Torna a operação compreensível e eficiente para o usuário.

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
Funcionalidade: Prévia de cor e textura
  Cenário: Exercitar Prévia de cor e textura
    Dado que um usuário opera a interface do sistema
    Quando o usuário executa a tarefa descrita
    Então a prévia mostra cor e textura antes de aplicar e o material ativo é indicado
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste de UI (a criar); demonstração. | A escolha de cor e de textura deve mostrar prévia do material no voxel antes de aplicar e indicar o material ativo no painel. |

Testes existentes: A criar (nenhum teste existe no baseline).

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito desejável de usabilidade. |
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

- Verificação: Teste de UI (a criar); demonstração.
- Documento de origem: `INCREMENTO-EDITOR-VOXEL.md`

---
