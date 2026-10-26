# REQ-FUNC-033 — Diagnóstico de versão e sincronização

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-033`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `requirements.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-033` |
| **Nome** | Diagnóstico de versão e sincronização |
| **Tipo** | Funcional |
| **Prioridade** | Opcional |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O sistema deve exibir a versão base, o commit, a branch e o estado de alterações locais, e comparar o commit local com o remoto em segundo plano, mostrando o resultado no console e no título da janela.

### Condições de Aplicação

- Repositório Git presente; rede disponível para comparar com o remoto.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/core/version.py`; `src/main.py`; `tests/test_version.py`. |

---

## Justificativa (Rationale)

O diagnóstico liga a execução ao commit e ao estado do repositório.

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
Funcionalidade: Diagnóstico de versão e sincronização
  Cenário: Exercitar Diagnóstico de versão e sincronização
    Dado um repositório Git e rede disponível
    Quando o jogo inicia
    Então o título mostra versão, status de sincronização e FPS
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste automatizado (`tests/test_version.py`, 2 casos); inspeção de `src/core/version.py`. | O título mostra versão, status e FPS; sem rede, o status é `offline`; com alterações locais, o status é `modified`; commit igual ao remoto é `synced`. |

Testes existentes: `tests/test_version.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito opcional para diagnóstico de versão e sincronização. |
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

- Código/testes: `src/core/version.py`; `src/main.py`; `tests/test_version.py`.
- Documento de origem: `requirements.md`

---
