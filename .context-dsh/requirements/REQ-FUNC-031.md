# REQ-FUNC-031 — Salvar e carregar personagem

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-031`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `requirements.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-031` |
| **Nome** | Salvar e carregar personagem |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O sistema deve gravar o personagem em `saves/personagem.json` com aparência, peças vestidas e posicionamento do cabelo, e restaurá-lo na abertura quando não houver flag de personagem.

### Condições de Aplicação

- Fechamento do editor, `/skin salvar`, `/skin carregar` ou abertura do jogo.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/clothing/character_save.py`; `src/main.py`; `src/interactive/skin_commands.py`; `tests/test_character_save.py`. |

---

## Justificativa (Rationale)

Sem persistência o trabalho de criação se perde.

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
Funcionalidade: Salvar e carregar personagem
  Cenário: Exercitar Salvar e carregar personagem
    Dado um personagem salvo
    Quando o jogo é aberto sem flags de personagem
    Então o mesmo corpo, roupas e cabelo são restaurados
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste automatizado (`tests/test_character_save.py`, 5 casos). | O save é escrito de forma atômica; um save ausente ou corrompido não impede a abertura; o personagem restaurado é igual ao salvo; `--novo` ignora o save. |

Testes existentes: `tests/test_character_save.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial para salvar e carregar personagem. |
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

- Código/testes: `src/clothing/character_save.py`; `src/main.py`; `src/interactive/skin_commands.py`; `tests/test_character_save.py`.
- Documento de origem: `requirements.md`

---
