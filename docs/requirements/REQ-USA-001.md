# REQ-USA-001 — Controles de teclado e mouse

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `UR-001`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `SRS.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `UR-001` |
| **Nome** | Controles de teclado e mouse |
| **Tipo** | Usabilidade |
| **Prioridade** | Essencial |
| **Status** | Implementado |

---

## Descrição

### Texto do Requisito

> O sistema deve oferecer controles de teclado e mouse documentados para câmera, pan, zoom, rotação, grade, chat, movimento e editor, sem exigir configuração prévia.

### Condições de Aplicação

- um usuário opera a interface do sistema

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | Inspeção de `README.md` e `src/main.py`; demonstração. |

---

## Justificativa (Rationale)

Torna a operação compreensível e eficiente para o usuário.

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
Funcionalidade: Controles de teclado e mouse
  Cenário: Exercitar Controles de teclado e mouse
    Dado que um usuário opera a interface do sistema
    Quando o usuário executa a tarefa descrita
    Então os controles documentados respondem sem configuração prévia
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Inspeção de `README.md` e `src/main.py`; demonstração. | O sistema deve oferecer controles de teclado e mouse documentados para câmera, pan, zoom, rotação, grade, chat, movimento e editor, sem exigir configuração prévia. |

Testes existentes: Inspeção/demonstração.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial de usabilidade. |
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

- Verificação: Inspeção de `README.md` e `src/main.py`; demonstração.
- Documento de origem: `SRS.md`

---
