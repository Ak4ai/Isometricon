# REQ-DATA-003 — Assets de roupa por ID

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `DR-003`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `SRS.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `DR-003` |
| **Nome** | Assets de roupa por ID |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> Os assets de roupa devem ser localizados por ID no nome do arquivo, em `assets/models/clothing`, com malha, textura e `.rbxm`.

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
| **Rastreabilidade técnica** | `test_find_clothing_texture`; `tests/test_character_editor.py` (catálogo). |

---

## Justificativa (Rationale)

Garante persistência e interoperabilidade dos dados.

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
Funcionalidade: Assets de roupa por ID
  Cenário: Exercitar Assets de roupa por ID
    Dado que existe um arquivo ou registro de dados do sistema
    Quando os dados são gravados e lidos
    Então a roupa é encontrada por ID em assets/models/clothing
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | `test_find_clothing_texture`; `tests/test_character_editor.py` (catálogo). | Os assets de roupa devem ser localizados por ID no nome do arquivo, em `assets/models/clothing`, com malha, textura e `.rbxm`. |

Testes existentes: `tests/test_find_clothing_texture.py`, `tests/test_character_editor.py`.

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

- Verificação: `test_find_clothing_texture`; `tests/test_character_editor.py` (catálogo).
- Documento de origem: `SRS.md`

---
