# REQ-CONS-011 — Formatos abertos e versionados

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `CR-011`
> **Origem:** incremento proposto
> **Arquivo-fonte:** `requirements-voxel-editor.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `CR-011` |
| **Nome** | Formatos abertos e versionados |
| **Tipo** | Restrição de Design |
| **Prioridade** | Essencial |
| **Status** | Proposto |

---

## Descrição

### Texto do Requisito

> Os formatos de objeto e de mapa devem ser abertos, documentados e versionados, sem depender de serviço ou formato proprietário para o funcionamento básico.

### Condições de Aplicação

- o código-fonte e o ambiente de execução estão disponíveis

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Pedido de extensão de 21/10/2026 e pesquisa do Replicube |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | Inspeção da documentação e dos arquivos. |

---

## Justificativa (Rationale)

Preserva o escopo e a arquitetura definidos para o projeto.

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
Funcionalidade: Formatos abertos e versionados
  Cenário: Exercitar Formatos abertos e versionados
    Dado que o código-fonte e o ambiente de execução estão disponíveis
    Quando a restrição é verificada
    Então os formatos são abertos, documentados e versionados
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Inspeção da documentação e dos arquivos. | Os formatos de objeto e de mapa devem ser abertos, documentados e versionados, sem depender de serviço ou formato proprietário para o funcionamento básico. |

Testes existentes: A criar (nenhum teste existe no baseline).

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial de restrição de design. |
| **Appropriate (Apropriado)** | [x] Sim [ ] Não | Descreve comportamento ou restrição, sem impor implementação. |
| **Unambiguous (Não ambíguo)** | [x] Sim [ ] Não | Redação única, com condição e critério de aceitação. |
| **Complete (Completo)** | [x] Sim [ ] Não | Texto, condição, verificação e rastreabilidade declarados. |
| **Singular (Singular)** | [x] Sim [ ] Não | Trata de uma única capacidade ou restrição. |
| **Feasible (Factível)** | [x] Sim [ ] Não | Previsto no incremento proposto. |
| **Verifiable (Verificável)** | [x] Sim [ ] Não | Método: Inspeção / Revisão. |
| **Correct (Correto)** | [x] Sim [ ] Não | Rastreável à fonte declarada. |
| **Conforming (Conforme)** | [x] Sim [ ] Não | Segue este template e a ISO/IEC/IEEE 29148:2018. |

---

## Informações Complementares

### Restrições e Dependências

- Nenhuma restrição adicional identificada.

### Notas e Suposições

- Requisito proposto; ainda não implementado.

### Anexos / Referências

- Verificação: Inspeção da documentação e dos arquivos.
- Documento de origem: `requirements-voxel-editor.md`

---
