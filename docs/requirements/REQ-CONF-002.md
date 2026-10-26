# REQ-CONF-002 — Estrutura ISO/IEC/IEEE 29148

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `SR-002`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `SRS.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `SR-002` |
| **Nome** | Estrutura ISO/IEC/IEEE 29148 |
| **Tipo** | Conformidade |
| **Prioridade** | Desejável |
| **Status** | Implementado |

---

## Descrição

### Texto do Requisito

> A documentação de requisitos deve seguir a estrutura da ISO/IEC/IEEE 29148:2018, seções 1 a 5.

### Condições de Aplicação

- o artefato sujeito à conformidade está disponível

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | Este documento; template em `.context-dsh/templates/TEMPLATE_SRS.md`. |

---

## Justificativa (Rationale)

Atende ao padrão ou à norma aplicável.

---

## Critérios de Verificação e Aceitação

### Método de Verificação

- [ ] Inspeção / Revisão
- [ ] Teste
- [ ] Demonstração
- [ ] Análise
- [ ] Simulação

### Critérios de Aceitação (Gherkin)

```gherkin
Funcionalidade: Estrutura ISO/IEC/IEEE 29148
  Cenário: Exercitar Estrutura ISO/IEC/IEEE 29148
    Dado que o artefato sujeito à conformidade está disponível
    Quando a conformidade é verificada
    Então o documento segue a estrutura 1 a 5 da ISO 29148
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Este documento; template em `.context-dsh/templates/TEMPLATE_SRS.md`. | A documentação de requisitos deve seguir a estrutura da ISO/IEC/IEEE 29148:2018, seções 1 a 5. |

Testes existentes: Inspeção/demonstração.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito desejável de conformidade. |
| **Appropriate (Apropriado)** | [x] Sim [ ] Não | Descreve comportamento ou restrição, sem impor implementação. |
| **Unambiguous (Não ambíguo)** | [x] Sim [ ] Não | Redação única, com condição e critério de aceitação. |
| **Complete (Completo)** | [x] Sim [ ] Não | Texto, condição, verificação e rastreabilidade declarados. |
| **Singular (Singular)** | [x] Sim [ ] Não | Trata de uma única capacidade ou restrição. |
| **Feasible (Factível)** | [x] Sim [ ] Não | Implementado no baseline. |
| **Verifiable (Verificável)** | [x] Sim [ ] Não | Método: inspeção. |
| **Correct (Correto)** | [x] Sim [ ] Não | Rastreável à fonte declarada. |
| **Conforming (Conforme)** | [x] Sim [ ] Não | Segue este template e a ISO/IEC/IEEE 29148:2018. |

---

## Informações Complementares

### Restrições e Dependências

- Nenhuma restrição adicional identificada.

### Notas e Suposições

- O comportamento descrito vale para o commit de referência.

### Anexos / Referências

- Verificação: Este documento; template em `.context-dsh/templates/TEMPLATE_SRS.md`.
- Documento de origem: `SRS.md`

---
