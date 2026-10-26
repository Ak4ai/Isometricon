# REQ-FUNC-014 — Destaque de bloco

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-014`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `requirements.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-014` |
| **Nome** | Destaque de bloco |
| **Tipo** | Funcional |
| **Prioridade** | Desejável |
| **Status** | Implementado |

---

## Descrição

### Texto do Requisito

> O sistema deve destacar o bloco sob o cursor e o bloco sob o token com cor distinta e intensidade pulsante, usando mistura aditiva e sem escrever no buffer de profundidade.

### Condições de Aplicação

- Modo terreno; hover com interseção ou token apoiado.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/interactive/highlight.py`; `assets/shaders/highlight.*`; `src/main.py`. |

---

## Justificativa (Rationale)

O destaque dá retorno imediato sobre o alvo do cursor e do token.

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
Funcionalidade: Destaque de bloco
  Cenário: Exercitar Destaque de bloco
    Dado o token apoiado e o cursor sobre um bloco
    Quando a cena é desenhada
    Então o bloco sob o token recebe destaque branco e o do cursor, amarelo
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Inspeção de `src/interactive/highlight.py` e do shader; demonstração. | O bloco sob o token recebe destaque branco; o bloco sob o cursor recebe destaque amarelo; o destaque desaparece quando não há interseção. |

Testes existentes: Inspeção/demonstração.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito desejável para destaque de bloco. |
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

- Código/testes: `src/interactive/highlight.py`; `assets/shaders/highlight.*`; `src/main.py`.
- Documento de origem: `requirements.md`

---
