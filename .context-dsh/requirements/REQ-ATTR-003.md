# REQ-ATTR-003 — Invalidação de cache v37

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `AR-003`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `requirements.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `AR-003` |
| **Nome** | Invalidação de cache v37 |
| **Tipo** | Confiabilidade |
| **Prioridade** | Essencial |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> Um cache de roupa com versão diferente de `v37` deve ser considerado inválido e refeito.

### Condições de Aplicação

- o sistema está em operação

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `test_fitted_asset_type_reads_the_header`; `is_valid_v2_obj`; inspeção. |

---

## Justificativa (Rationale)

Sustenta confiabilidade, portabilidade ou segurança do sistema.

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
Funcionalidade: Invalidação de cache v37
  Cenário: Exercitar Invalidação de cache v37
    Dado que o sistema está em operação
    Quando a condição do atributo é exercitada
    Então o cache v37 é aceito e versões antigas são refeitas
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | `test_fitted_asset_type_reads_the_header`; `is_valid_v2_obj`; inspeção. | Um cache de roupa com versão diferente de `v37` deve ser considerado inválido e refeito. |

Testes existentes: `tests/test_fitted_asset_type_reads_the_header.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial de atributo do sistema. |
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

- Verificação: `test_fitted_asset_type_reads_the_header`; `is_valid_v2_obj`; inspeção.
- Documento de origem: `requirements.md`

---
