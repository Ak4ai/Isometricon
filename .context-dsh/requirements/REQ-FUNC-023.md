# REQ-FUNC-023 — Proporções do corpo

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-023`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `requirements.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-023` |
| **Nome** | Proporções do corpo |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O sistema deve aplicar 78 ajustes de -100 a 100 sobre altura, cabeça, pescoço, ombros, peito, cintura, pelve, quadril, glúteos, braços, mãos, pernas, pés, olhos, sobrancelhas, nariz, pele, sombra, bordas de roupa, maquiagem, orelhas, chifres, cauda e asas.

### Condições de Aplicação

- Personagem montado; ajuste alterado por comando ou editor.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/clothing/body_shape.py`; `src/clothing/skeleton.py`; `src/clothing/character_animation.py`; `tests/test_body_shape.py`. |

---

## Justificativa (Rationale)

As proporções adaptam o mesmo corpo a diferentes personagens.

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
Funcionalidade: Proporções do corpo
  Cenário: Exercitar Proporções do corpo
    Dado os 78 ajustes em zero
    Quando o usuário aplica altura, pernas_comprimento ou folga
    Então o corpo e o tecido mudam juntos e os pés permanecem no chão
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste automatizado (`tests/test_body_shape.py`, 62 casos). | Com os 78 ajustes em zero, o corpo fica como modelado; alongar pernas levanta o corpo e mantém os pés no chão; peito, cintura e glúteos movem pele e tecido juntos; folga atua apenas no tecido. |

Testes existentes: `tests/test_body_shape.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial para proporções do corpo. |
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

- Código/testes: `src/clothing/body_shape.py`; `src/clothing/skeleton.py`; `src/clothing/character_animation.py`; `tests/test_body_shape.py`.
- Documento de origem: `requirements.md`

---
