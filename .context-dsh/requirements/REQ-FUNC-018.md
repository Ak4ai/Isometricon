# REQ-FUNC-018 — Overlay de coordenadas

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-018`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `requirements.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-018` |
| **Nome** | Overlay de coordenadas |
| **Tipo** | Funcional |
| **Prioridade** | Opcional |
| **Status** | Implementado |

---

## Descrição

### Texto do Requisito

> O sistema deve exibir em pixels as coordenadas X, Y e Z da posição do token em sobreposição à cena 3D.

### Condições de Aplicação

- Modo terreno; token existente.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/interactive/coordinate_overlay.py`; `assets/shaders/coordinate_overlay.*`; `src/main.py`. |

---

## Justificativa (Rationale)

As coordenadas apoiam depuração e conferência de posição.

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
Funcionalidade: Overlay de coordenadas
  Cenário: Exercitar Overlay de coordenadas
    Dado o token no mundo
    Quando o overlay é desenhado
    Então as coordenadas X, Y e Z aparecem em pixels sobre a cena
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Inspeção de `src/interactive/coordinate_overlay.py`; demonstração. | O texto acompanha a posição do token e usa apenas dígitos, sinais e separador decimal. |

Testes existentes: Inspeção/demonstração.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito opcional para overlay de coordenadas. |
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

- Código/testes: `src/interactive/coordinate_overlay.py`; `assets/shaders/coordinate_overlay.*`; `src/main.py`.
- Documento de origem: `requirements.md`

---
