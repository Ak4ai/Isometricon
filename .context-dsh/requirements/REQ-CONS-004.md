# REQ-CONS-004 — Um token por execução

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `CR-004`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `requirements.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `CR-004` |
| **Nome** | Um token por execução |
| **Tipo** | Restrição de Design |
| **Prioridade** | Essencial |
| **Status** | Implementado |

---

## Descrição

### Texto do Requisito

> Deve existir um único token de jogador por execução.

### Condições de Aplicação

- o código-fonte e o ambiente de execução estão disponíveis

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/main.py`; `src/interactive/token_system.py`; inspeção. |

---

## Justificativa (Rationale)

Preserva o escopo e a arquitetura definidos para o projeto.

---

## Critérios de Verificação e Aceitação

### Método de Verificação

- [x] Inspeção / Revisão
- [ ] Teste
- [ ] Demonstração
- [ ] Análise
- [ ] Simulação

### Critérios de Aceitação (Gherkin)

```gherkin
Funcionalidade: Um token por execução
  Cenário: Exercitar Um token por execução
    Dado que o código-fonte e o ambiente de execução estão disponíveis
    Quando a restrição é verificada
    Então há um único token por execução
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | `src/main.py`; `src/interactive/token_system.py`; inspeção. | Deve existir um único token de jogador por execução. |

Testes existentes: Inspeção/demonstração.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial de restrição de design. |
| **Appropriate (Apropriado)** | [x] Sim [ ] Não | Descreve comportamento ou restrição, sem impor implementação. |
| **Unambiguous (Não ambíguo)** | [x] Sim [ ] Não | Redação única, com condição e critério de aceitação. |
| **Complete (Completo)** | [x] Sim [ ] Não | Texto, condição, verificação e rastreabilidade declarados. |
| **Singular (Singular)** | [x] Sim [ ] Não | Trata de uma única capacidade ou restrição. |
| **Feasible (Factível)** | [x] Sim [ ] Não | Implementado no baseline. |
| **Verifiable (Verificável)** | [x] Sim [ ] Não | Método: Inspeção / Revisão. |
| **Correct (Correto)** | [x] Sim [ ] Não | Rastreável à fonte declarada. |
| **Conforming (Conforme)** | [x] Sim [ ] Não | Segue este template e a ISO/IEC/IEEE 29148:2018. |

---

## Informações Complementares

### Restrições e Dependências

- Nenhuma restrição adicional identificada.

### Notas e Suposições

- O comportamento descrito vale para o commit de referência.

### Anexos / Referências

- Verificação: `src/main.py`; `src/interactive/token_system.py`; inspeção.
- Documento de origem: `requirements.md`

---
