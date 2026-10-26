# REQ-FUNC-024 — Peças procedurais

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-024`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `requirements.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-024` |
| **Nome** | Peças procedurais |
| **Tipo** | Funcional |
| **Prioridade** | Desejável |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O sistema deve gerar orelhas (17 modelos), chifres (11), caudas (11) e asas (5), com cor e ajustes próprios, compartilhando a topologia entre modelos do mesmo tipo.

### Condições de Aplicação

- Seção Rosto ou Corpo; estilo diferente de "sem"; personagem montado.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/clothing/ears.py`; `horns.py`; `tails.py`; `wings.py`; `tests/test_body_shape.py`. |

---

## Justificativa (Rationale)

Orelhas, chifres, cauda e asas completam raças e fantasias.

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
Funcionalidade: Peças procedurais
  Cenário: Exercitar Peças procedurais
    Dado o personagem sem orelhas
    Quando o usuário escolhe orelha de elfo e chifres de bode
    Então as peças aparecem com a cor e os ajustes escolhidos, compartilhando a topologia do modelo
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste automatizado (`tests/test_body_shape.py`, casos de modelos, cores e ajustes; `tests/test_character_animation.py`). | Todos os modelos de um tipo têm os mesmos triângulos; trocar de modelo só move vértices; asas e cauda saem das costas; a fada tem asa translúcida. |

Testes existentes: `tests/test_body_shape.py`, `tests/test_character_animation.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito desejável para peças procedurais. |
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

- Código/testes: `src/clothing/ears.py`; `horns.py`; `tails.py`; `wings.py`; `tests/test_body_shape.py`.
- Documento de origem: `requirements.md`

---
