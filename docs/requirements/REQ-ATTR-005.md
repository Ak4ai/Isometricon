# REQ-ATTR-005 — Falha de montagem mantém modelo

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `AR-005`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `SRS.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `AR-005` |
| **Nome** | Falha de montagem mantém modelo |
| **Tipo** | Confiabilidade |
| **Prioridade** | Essencial |
| **Status** | Implementado |

---

## Descrição

### Texto do Requisito

> Uma falha durante a montagem em background deve manter o modelo anterior em uso e registrar a mensagem, sem encerrar a aplicação.

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
| **Rastreabilidade técnica** | Inspeção de `CharacterModel.poll`; demonstração. |

---

## Justificativa (Rationale)

Sustenta confiabilidade, portabilidade ou segurança do sistema.

---

## Critérios de Verificação e Aceitação

### Método de Verificação

- [x] Inspeção / Revisão
- [ ] Teste
- [x] Demonstração
- [ ] Análise
- [ ] Simulação

### Critérios de Aceitação (Gherkin)

```gherkin
Funcionalidade: Falha de montagem mantém modelo
  Cenário: Exercitar Falha de montagem mantém modelo
    Dado que o sistema está em operação
    Quando a condição do atributo é exercitada
    Então o modelo anterior permanece e a mensagem é registrada
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Inspeção de `CharacterModel.poll`; demonstração. | Uma falha durante a montagem em background deve manter o modelo anterior em uso e registrar a mensagem, sem encerrar a aplicação. |

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
| **Verifiable (Verificável)** | [x] Sim [ ] Não | Método: Inspeção / Revisão, Demonstração. |
| **Correct (Correto)** | [x] Sim [ ] Não | Rastreável à fonte declarada. |
| **Conforming (Conforme)** | [x] Sim [ ] Não | Segue este template e a ISO/IEC/IEEE 29148:2018. |

---

## Informações Complementares

### Restrições e Dependências

- Nenhuma restrição adicional identificada.

### Notas e Suposições

- O comportamento descrito vale para o commit de referência.

### Anexos / Referências

- Verificação: Inspeção de `CharacterModel.poll`; demonstração.
- Documento de origem: `SRS.md`

---
