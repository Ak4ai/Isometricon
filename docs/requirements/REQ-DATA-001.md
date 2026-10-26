# REQ-DATA-001 — Save do personagem em JSON

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `DR-001`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `SRS.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `DR-001` |
| **Nome** | Save do personagem em JSON |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O save do personagem deve ser um JSON com `versao`, `aparencia` (39 campos), `veste` (7 slots) e `cabelo` (6 valores), gravado de forma atômica.

### Condições de Aplicação

- existe um arquivo ou registro de dados do sistema

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `tests/test_character_save.py`; inspeção de `character_save.py`. |

---

## Justificativa (Rationale)

Garante persistência e interoperabilidade dos dados.

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
Funcionalidade: Save do personagem em JSON
  Cenário: Exercitar Save do personagem em JSON
    Dado que existe um arquivo ou registro de dados do sistema
    Quando os dados são gravados e lidos
    Então o JSON contém versao, aparencia (39), veste (7) e cabelo (6), gravado atomicamente
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | `tests/test_character_save.py`; inspeção de `character_save.py`. | O save do personagem deve ser um JSON com `versao`, `aparencia` (39 campos), `veste` (7 slots) e `cabelo` (6 valores), gravado de forma atômica. |

Testes existentes: `tests/test_character_save.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial de dados. |
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

- Verificação: `tests/test_character_save.py`; inspeção de `character_save.py`.
- Documento de origem: `SRS.md`

---
