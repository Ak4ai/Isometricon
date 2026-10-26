# REQ-FUNC-032 — Automação por linha de comando

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-032`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `requirements.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-032` |
| **Nome** | Automação por linha de comando |
| **Tipo** | Funcional |
| **Prioridade** | Desejável |
| **Status** | Implementado |

---

## Descrição

### Texto do Requisito

> O sistema deve aceitar comandos iniciais, limite de quadros, captura de framebuffer em PNG, roteiro de mouse e flags de seed, editor e pincel para execuções automatizadas.

### Condições de Aplicação

- Flags `--cmd`, `--frames`, `--screenshot`, `--mouse`, `--seed`, `--editor`, `--pincel`, entre outras.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/main.py`; `src/core/version.py`; `README.md`. |

---

## Justificativa (Rationale)

A automação permite capturas e conferências reproduzíveis.

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
Funcionalidade: Automação por linha de comando
  Cenário: Exercitar Automação por linha de comando
    Dado a flag --frames 10 --screenshot
    Quando a execução termina
    Então o PNG do framebuffer é gravado e o autosave não é acionado
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Inspeção de `src/main.py`; demonstração com `--frames 10 --screenshot`. | O comando inicial é executado antes do laço; a captura é gravada ao atingir o limite de quadros; o roteiro de mouse produz os mesmos eventos do mouse real; `--frames` desliga o autosave. |

Testes existentes: Inspeção/demonstração.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito desejável para automação por linha de comando. |
| **Appropriate (Apropriado)** | [x] Sim [ ] Não | Descreve comportamento ou restrição, sem impor implementação. |
| **Unambiguous (Não ambíguo)** | [x] Sim [ ] Não | Redação única, com condições e critério de aceitação. |
| **Complete (Completo)** | [x] Sim [ ] Não | Texto, condições, verificação e rastreabilidade declarados. |
| **Singular (Singular)** | [x] Sim [ ] Não | Trata de uma única capacidade ou restrição. |
| **Feasible (Factível)** | [x] Sim [ ] Não | Implementado no baseline. |
| **Verifiable (Verificável)** | [x] Sim [ ] Não | Método: Inspeção / Revisão, Demonstração. |
| **Correct (Correto)** | [x] Sim [ ] Não | Rastreável à fonte declarada. |
| **Conforming (Conforme)** | [x] Sim [ ] Não | Segue este template e a ISO/IEC/IEEE 29148:2018. |

---

## Informações Complementares

### Restrições e Dependências

- Requisitos relacionados: —

### Notas e Suposições

- Nenhuma observação adicional.
- O comportamento descrito vale para o commit de referência.

### Anexos / Referências

- Código/testes: `src/main.py`; `src/core/version.py`; `README.md`.
- Documento de origem: `requirements.md`

---
