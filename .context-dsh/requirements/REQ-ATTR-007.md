# REQ-ATTR-007 — Sem telemetria e rede limitada

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `AR-007`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `requirements.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `AR-007` |
| **Nome** | Sem telemetria e rede limitada |
| **Tipo** | Segurança |
| **Prioridade** | Essencial |
| **Status** | Implementado |

---

## Descrição

### Texto do Requisito

> A aplicação não deve coletar telemetria nem enviar dados do usuário; as únicas requisições de rede são a checagem de commit no GitHub e o download de assets do Roblox.

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
| **Rastreabilidade técnica** | Inspeção de `src/core/version.py`, `scripts/import_roblox_clothing.py`; busca por `urllib`. |

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
Funcionalidade: Sem telemetria e rede limitada
  Cenário: Exercitar Sem telemetria e rede limitada
    Dado que o sistema está em operação
    Quando a condição do atributo é exercitada
    Então não há telemetria; só GitHub e Roblox são acessados
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Inspeção de `src/core/version.py`, `scripts/import_roblox_clothing.py`; busca por `urllib`. | A aplicação não deve coletar telemetria nem enviar dados do usuário; as únicas requisições de rede são a checagem de commit no GitHub e o download de assets do Roblox. |

Testes existentes: Inspeção/demonstração.

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

- Verificação: Inspeção de `src/core/version.py`, `scripts/import_roblox_clothing.py`; busca por `urllib`.
- Documento de origem: `requirements.md`

---
