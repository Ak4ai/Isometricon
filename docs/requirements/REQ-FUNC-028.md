# REQ-FUNC-028 — Ocultação de pele sob a roupa (HSR)

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-028`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `SRS.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-028` |
| **Nome** | Ocultação de pele sob a roupa (HSR) |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O sistema deve ocultar a pele coberta pelas roupas usando a máscara HSR do Roblox, com alternativa geométrica quando a máscara não existe, e permitir correção manual por espelhamento e pintura de pontos.

### Condições de Aplicação

- Roupas com sidecar de HSR ou malha encaixada disponível; seção Ajuste fino para edição.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/clothing/hsr.py`; `src/clothing/character_model.py`; `src/interactive/skin_brush.py`; `tests/test_hsr.py`; `tests/test_skin_brush.py`. |

---

## Justificativa (Rationale)

O HSR evita pele atravessando o tecido sem cortar a roupa.

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
Funcionalidade: Ocultação de pele sob a roupa (HSR)
  Cenário: Exercitar Ocultação de pele sob a roupa (HSR)
    Dado uma roupa com máscara HSR
    Quando o personagem é montado
    Então a pele coberta não é desenhada e a pele sob aberturas permanece visível
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste automatizado (`tests/test_hsr.py`, 12 casos; `tests/test_skin_brush.py`, 19 casos). | A pele sob a roupa não é desenhada; a pele sob aberturas permanece visível; pintar um ponto esconde ou mostra apenas o que ele decide; desfazer/refazer restaura o estado anterior. |

Testes existentes: `tests/test_hsr.py`, `tests/test_skin_brush.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial para ocultação de pele sob a roupa (hsr). |
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

- Código/testes: `src/clothing/hsr.py`; `src/clothing/character_model.py`; `src/interactive/skin_brush.py`; `tests/test_hsr.py`; `tests/test_skin_brush.py`.
- Documento de origem: `SRS.md`

---
