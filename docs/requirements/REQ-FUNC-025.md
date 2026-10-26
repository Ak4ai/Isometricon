# REQ-FUNC-025 — Raças

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-025`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `SRS.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-025` |
| **Nome** | Raças |
| **Tipo** | Funcional |
| **Prioridade** | Desejável |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O sistema deve aplicar 17 presets de raça sobre o corpo escolhido, alterando pele, orelhas, olhos, nariz, boca, chifres, cauda, asas e proporções.

### Condições de Aplicação

- Seção Corpo ou comando `/skin raca`; corpo feminino ou masculino.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/clothing/races.py`; `src/interactive/skin_commands.py`; `tests/test_body_shape.py`. |

---

## Justificativa (Rationale)

As raças empacotam combinações coerentes de aparência.

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
Funcionalidade: Raças
  Cenário: Exercitar Raças
    Dado um corpo feminino
    Quando o usuário aplica a raça elfo
    Então pele, orelhas, olhos, nariz e proporções mudam e maquiagem e roupas são preservadas
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste automatizado (`tests/test_body_shape.py`, casos de raça por comando e cartões). | A raça altera apenas as chaves de `RACE_ADJUSTMENTS`; maquiagem, cabelo, roupas e corpo são preservados; trocar de raça remove a boca de vampiro. |

Testes existentes: `tests/test_body_shape.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito desejável para raças. |
| **Appropriate (Apropriado)** | [x] Sim [ ] Não | Descreve comportamento ou restrição, sem impor implementação. |
| **Unambiguous (Não ambíguo)** | [x] Sim [ ] Não | Redação única, com condições e critério de aceitação. |
| **Complete (Completo)** | [x] Sim [ ] Não | Texto, condições, verificação e rastreabilidade declarados. |
| **Singular (Singular)** | [x] Sim [ ] Não | Trata de uma única capacidade ou restrição. |
| **Feasible (Factível)** | [x] Sim [ ] Não | Implementado no baseline. |
| **Verifiable (Verificável)** | [x] Sim [ ] Não | Método: Teste. |
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

- Código/testes: `src/clothing/races.py`; `src/interactive/skin_commands.py`; `tests/test_body_shape.py`.
- Documento de origem: `SRS.md`

---
