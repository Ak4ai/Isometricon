# REQ-FUNC-034 — Catálogo e miniaturas do editor

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-034`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `requirements.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-034` |
| **Nome** | Catálogo e miniaturas do editor |
| **Tipo** | Funcional |
| **Prioridade** | Desejável |
| **Status** | Implementado |

---

## Descrição

### Texto do Requisito

> O sistema deve listar os itens do catálogo por seção, emparelhar sapatos esquerdo e direito em um item, marcar peças com defeito conhecido e gerar miniaturas ausentes em processo separado.

### Condições de Aplicação

- Editor aberto; itens em `assets/models/clothing`; texturas ou miniaturas disponíveis.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/interactive/character_editor.py`; `scripts/render_catalog_thumbnails.py`; `src/clothing/known_defects.py`; `tests/test_character_editor.py`. |

---

## Justificativa (Rationale)

O catálogo precisa ser navegável para escolher peças e raças.

---

## Critérios de Verificação e Aceitação

### Método de Verificação

- [x] Inspeção / Revisão
- [x] Teste
- [ ] Demonstração
- [ ] Análise
- [ ] Simulação

### Critérios de Aceitação (Gherkin)

```gherkin
Funcionalidade: Catálogo e miniaturas do editor
  Cenário: Exercitar Catálogo e miniaturas do editor
    Dado itens no catálogo
    Quando o editor abre
    Então os itens aparecem por seção, com sapatos emparelhados e defeitos marcados
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste automatizado (`tests/test_character_editor.py`, catálogo e seleção; `tests/test_body_shape.py`, cartões de raça); inspeção de `scripts/render_catalog_thumbnails.py`. | O item em uso aparece contornado; sapatos só aparecem quando as duas metades existem; peça defeituosa mostra aviso; sem miniatura, o cartão mostra a textura ou um X. |

Testes existentes: `tests/test_character_editor.py`, `tests/test_body_shape.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito desejável para catálogo e miniaturas do editor. |
| **Appropriate (Apropriado)** | [x] Sim [ ] Não | Descreve comportamento ou restrição, sem impor implementação. |
| **Unambiguous (Não ambíguo)** | [x] Sim [ ] Não | Redação única, com condições e critério de aceitação. |
| **Complete (Completo)** | [x] Sim [ ] Não | Texto, condições, verificação e rastreabilidade declarados. |
| **Singular (Singular)** | [x] Sim [ ] Não | Trata de uma única capacidade ou restrição. |
| **Feasible (Factível)** | [x] Sim [ ] Não | Implementado no baseline. |
| **Verifiable (Verificável)** | [x] Sim [ ] Não | Método: Inspeção / Revisão, Teste. |
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

- Código/testes: `src/interactive/character_editor.py`; `scripts/render_catalog_thumbnails.py`; `src/clothing/known_defects.py`; `tests/test_character_editor.py`.
- Documento de origem: `requirements.md`

---
