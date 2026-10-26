# REQ-FUNC-020 — Comandos de customização e roupas

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-020`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `SRS.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-020` |
| **Nome** | Comandos de customização e roupas |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Implementado |

---

## Descrição

### Texto do Requisito

> O sistema deve interpretar 32 comandos sob `/skin` e 3 comandos raiz, aceitando nomes em português e inglês, e executar troca de corpo, aparência, roupas, raças, peças 3D, ajustes, editor e persistência.

### Condições de Aplicação

- Console aberto; modelo de personagem pode estar ausente para comandos de aparência.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/interactive/skin_commands.py`; `tests/test_chat_console.py`; `tests/test_body_shape.py`; `tests/test_character_save.py`. |

---

## Justificativa (Rationale)

Os comandos tornam a customização e as roupas operáveis por texto.

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
Funcionalidade: Comandos de customização e roupas
  Cenário: Exercitar Comandos de customização e roupas
    Dado o personagem montado
    Quando o usuário executa /skin olhos verde ou um comando de roupa
    Então o efeito correspondente é aplicado e o feedback aparece no chat
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste automatizado da tabela, dos apelidos e de comandos representativos (`tests/test_chat_console.py`, `tests/test_body_shape.py`, `tests/test_character_save.py`, `tests/test_skin_brush.py`); os demais comandos por inspeção. | Cada comando tem uso e nome único; apelidos em inglês executam o mesmo efeito; `/ajuda` lista grupos e detalha um comando; comando inválido retorna erro colorido. |

Testes existentes: `tests/test_chat_console.py`, `tests/test_body_shape.py`, `tests/test_character_save.py`, `tests/test_skin_brush.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial para comandos de customização e roupas. |
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

- Código/testes: `src/interactive/skin_commands.py`; `tests/test_chat_console.py`; `tests/test_body_shape.py`; `tests/test_character_save.py`.
- Documento de origem: `SRS.md`

---
