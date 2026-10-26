# REQ-DATA-002 — Cache de roupa e sidecars

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `DR-002`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `SRS.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `DR-002` |
| **Nome** | Cache de roupa e sidecars |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O cache de roupa deve ser um OBJ com cabeçalho `# Isometricon Universal Fitted Clothing v37` e `# asset_type N`, acompanhado de `_hsr.npz` e `_parts.npy`.

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
| **Rastreabilidade técnica** | `test_fitted_asset_type_reads_the_header`; `tests/test_hsr.py`; inspeção de `wear_engine.py`. |

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
Funcionalidade: Cache de roupa e sidecars
  Cenário: Exercitar Cache de roupa e sidecars
    Dado que existe um arquivo ou registro de dados do sistema
    Quando os dados são gravados e lidos
    Então o OBJ traz o cabeçalho v37 e os sidecars _hsr.npz e _parts.npy
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | `test_fitted_asset_type_reads_the_header`; `tests/test_hsr.py`; inspeção de `wear_engine.py`. | O cache de roupa deve ser um OBJ com cabeçalho `# Isometricon Universal Fitted Clothing v37` e `# asset_type N`, acompanhado de `_hsr.npz` e `_parts.npy`. |

Testes existentes: `tests/test_fitted_asset_type_reads_the_header.py`, `tests/test_hsr.py`.

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

- Verificação: `test_fitted_asset_type_reads_the_header`; `tests/test_hsr.py`; inspeção de `wear_engine.py`.
- Documento de origem: `SRS.md`

---
