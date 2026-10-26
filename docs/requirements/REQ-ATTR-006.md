# REQ-ATTR-006 — Portabilidade Windows/Linux/WSL

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `AR-006`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `SRS.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `AR-006` |
| **Nome** | Portabilidade Windows/Linux/WSL |
| **Tipo** | Portabilidade |
| **Prioridade** | Essencial |
| **Status** | Implementado |

---

## Descrição

### Texto do Requisito

> A aplicação deve operar em Windows e Linux, incluindo WSL com backend GLX.

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
| **Rastreabilidade técnica** | `src/_platform.py`; `tests/test_platform.py`; CI em `ubuntu-latest` e build em `windows-latest`. |

---

## Justificativa (Rationale)

Sustenta confiabilidade, portabilidade ou segurança do sistema.

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
Funcionalidade: Portabilidade Windows/Linux/WSL
  Cenário: Exercitar Portabilidade Windows/Linux/WSL
    Dado que o sistema está em operação
    Quando a condição do atributo é exercitada
    Então a aplicação opera em Windows, Linux e WSL/GLX
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | `src/_platform.py`; `tests/test_platform.py`; CI em `ubuntu-latest` e build em `windows-latest`. | A aplicação deve operar em Windows e Linux, incluindo WSL com backend GLX. |

Testes existentes: `tests/test_platform.py`.

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

- Verificação: `src/_platform.py`; `tests/test_platform.py`; CI em `ubuntu-latest` e build em `windows-latest`.
- Documento de origem: `SRS.md`

---
