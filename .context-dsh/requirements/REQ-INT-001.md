# REQ-INT-001 — Teclado e mouse

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `EI-001`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `requirements.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `EI-001` |
| **Nome** | Teclado e mouse |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Implementado |

---

## Descrição

### Texto do Requisito

> O sistema deve receber eventos de teclado e mouse do GLFW e manter o estado de entrada em pixels.

### Condições de Aplicação

- a aplicação está em execução e a interface está disponível

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | src/core/window.py; src/main.py |

---

## Justificativa (Rationale)

Define a fronteira de entrada e saída do sistema.

---

## Critérios de Verificação e Aceitação

### Método de Verificação

- [x] Inspeção / Revisão
- [ ] Teste
- [x] Demonstração
- [ ] Análise
- [ ] Simulação

### Critérios de Aceitação (Gherkin)

```gherkin
Funcionalidade: Teclado e mouse
  Cenário: Exercitar Teclado e mouse
    Dado que a aplicação está em execução e a interface está disponível
    Quando o sistema troca dados por essa interface
    Então a entrada Eventos GLFW (tecla, botão, roda, posição) é aceita e a saída Estado interno é produzida no formato Códigos GLFW; posição em pixels.
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Inspeção do código e demonstração. | O sistema deve receber eventos de teclado e mouse do GLFW e manter o estado de entrada em pixels. |

Testes existentes: Inspeção/demonstração.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial de interface externa. |
| **Appropriate (Apropriado)** | [x] Sim [ ] Não | Descreve comportamento ou restrição, sem impor implementação. |
| **Unambiguous (Não ambíguo)** | [x] Sim [ ] Não | Redação única, com condição e critério de aceitação. |
| **Complete (Completo)** | [x] Sim [ ] Não | Texto, condição, verificação e rastreabilidade declarados. |
| **Singular (Singular)** | [x] Sim [ ] Não | Trata de uma única capacidade ou restrição. |
| **Feasible (Factível)** | [x] Sim [ ] Não | Implementado no baseline. |
| **Verifiable (Verificável)** | [x] Sim [ ] Não | Método: Inspeção / Revisão, Demonstração. |
| **Correct (Correto)** | [x] Sim [ ] Não | Rastreável à fonte declarada. |
| **Conforming (Conforme)** | [x] Sim [ ] Não | Segue este template e a ISO/IEC/IEEE 29148:2018. |

---

## Informações Complementares

### Restrições e Dependências

- Nenhuma restrição adicional identificada.

### Notas e Suposições

- O comportamento descrito vale para o commit de referência.

### Anexos / Referências

- Verificação: Inspeção do código e demonstração.
- Documento de origem: `requirements.md`

---
