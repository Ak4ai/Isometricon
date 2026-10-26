# Ficha de Requisito

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `REQ-XXX-NNN` |
| **Nome** | `[Nome curto e objetivo do requisito]` |
| **Tipo** | `Funcional / Performance / Usabilidade / Segurança / Confiabilidade / Portabilidade / Manutenibilidade / Restrição de Design / Conformidade` |
| **Prioridade** | `Essencial / Desejável / Opcional` |
| **Status** | `Proposto / Aprovado / Em revisão / Implementado / Verificado` |
| **Versão** | `1.0` |

---

## Descrição

### Texto do Requisito
> *Redija o requisito de forma única, completa, não ambígua e verificável. Diga **O QUE** é necessário, não **COMO** fazer. Evite termos vagos ("user friendly", "sempre", "todos", "se possível", "etc.").*

`[Insira aqui a redação final do requisito]`

### Condições de Aplicação
> *Liste condições ou estados sob os quais o requisito deve ser atendido. Um requisito singular pode ter múltiplas condições.*

- Condição 1: `[descreva]`
- Condição 2: `[descreva]`

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | `[Stakeholder / Documento / Norma / Sistema pai]` |
| **Requisito Pai** | `[ID do requisito de nível superior, se houver]` |
| **Requisitos Filhos** | `[IDs dos requisitos derivados, se houver]` |
| **Casos de Uso / Histórias Relacionadas** | `[UC-XXX / US-XXX]` |

---

## Justificativa (Rationale)

> *Explique o porquê deste requisito existir. Qual necessidade do negócio ou do stakeholder ele atende?*

`[Descreva a justificativa]`

---

## Critérios de Verificação e Aceitação

> *O requisito deve ser verificável (de preferência mensurável). Descreva como se comprovará que ele foi atendido.*

### Método de Verificação
- [ ] Inspeção / Revisão
- [ ] Teste
- [ ] Demonstração
- [ ] Análise
- [ ] Simulação

### Critérios de Aceitação (Gherkin / BDD recomendado)
```gherkin
Funcionalidade: [nome resumido]
  Cenário: [título do cenário]
    Dado [contexto inicial]
    Quando [ação / estímulo]
    Então [resultado esperado mensurável]
```

### Casos de Teste Associados
| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | | |

---

## Análise de Conformidade com a Norma

Verifique se o requisito atende às características da seção 5.2.5 da ISO/IEC/IEEE 29148:2018.

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [ ] Sim [ ] Não | Capacidade essencial? Se omitido, haverá deficiência? |
| **Appropriate (Apropriado)** | [ ] Sim [ ] Não | Nível de abstração adequado? Evita impor design desnecessário? |
| **Unambiguous (Não ambíguo)** | [ ] Sim [ ] Não | Só existe uma interpretação possível? |
| **Complete (Completo)** | [ ] Sim [ ] Não | Descreve suficientemente sem depender de informações externas? |
| **Singular (Singular)** | [ ] Sim [ ] Não | Trata de uma única capacidade/característica/restrição? |
| **Feasible (Factível)** | [ ] Sim [ ] Não | Realizável dentro das restrições de custo, cronograma e técnica? |
| **Verifiable (Verificável)** | [ ] Sim [ ] Não | É possível comprovar objetivamente sua implementação? |
| **Correct (Correto)** | [ ] Sim [ ] Não | Representa com precisão a necessidade do stakeholder? |
| **Conforming (Conforme)** | [ ] Sim [ ] Não | Segue o template e padrão de escrita aprovado? |

---

## Informações Complementares

### Restrições e Dependências
> *Liste restrições técnicas, de negócio ou dependências externas que impactam este requisito.*

- `[Restrição/dependência 1]`
- `[Restrição/dependência 2]`

### Notas e Suposições
> *Documente todas as suposições feitas em relação a este requisito. Se a suposição for incorreta, o requisito pode precisar ser alterado.*

- `[Suposição 1]`
- `[Suposição 2]`

### Anexos / Referências
- `[Link ou referência para protótipo, diagrama, norma, etc.]`

---

## Histórico de Alterações

| Versão | Data | Autor | Alteração |
|--------|------|-------|-----------|
| 1.0 | DD/MM/AAAA | `[Nome]` | Criação inicial |
