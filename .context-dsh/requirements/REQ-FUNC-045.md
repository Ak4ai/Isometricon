# REQ-FUNC-045 — Salvar e carregar mapa

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-045`
> **Origem:** incremento proposto
> **Arquivo-fonte:** `requirements-voxel-editor.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-045` |
| **Nome** | Salvar e carregar mapa |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Proposto |

---

## Descrição

### Texto do Requisito

> O editor deve salvar e carregar um mapa em arquivo próprio, com versão, dimensões, terreno base e lista de objetos com posição e rotação, usando gravação atômica e validação na leitura.

### Condições de Aplicação

- Projeto de mapa aberto; comando de salvar/carregar; caminho de arquivo.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Pedido de extensão de 21/10/2026 e pesquisa do Replicube (ver `requirements-voxel-editor.md`) |
| **Requisito Pai** | FR-031 (padrão atômico) |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | Novo formato de mapa; possível reutilização do `WorldManager` para carregar chunks prontos. |

---

## Justificativa (Rationale)

Um mapa sem persistência não é um projeto reutilizável.

---

## Critérios de Verificação e Aceitação

### Método de Verificação

- [ ] Inspeção / Revisão
- [x] Teste
- [x] Demonstração
- [ ] Análise
- [ ] Simulação

### Critérios de Aceitação (Gherkin)

```gherkin
Funcionalidade: Salvar e carregar mapa
  Cenário: Exercitar Salvar e carregar mapa
    Dado um mapa com uma casa
    Quando o usuário salva, fecha e reabre
    Então a casa está na mesma posição e rotação e o mapa pode ser jogado
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste de round-trip (a criar); teste de arquivo corrompido; demonstração. | Salvar e reabrir reproduz o mapa; o mapa carregado pode ser jogado no modo terreno; arquivo de versão desconhecida é recusado com mensagem; interrupção da gravação não deixa arquivo parcial. |

Testes existentes: A criar (nenhum teste existe no baseline).

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial para salvar e carregar mapa. |
| **Appropriate (Apropriado)** | [x] Sim [ ] Não | Descreve comportamento ou restrição, sem impor implementação. |
| **Unambiguous (Não ambíguo)** | [x] Sim [ ] Não | Redação única, com condições e critério de aceitação. |
| **Complete (Completo)** | [x] Sim [ ] Não | Texto, condições, verificação e rastreabilidade declarados. |
| **Singular (Singular)** | [x] Sim [ ] Não | Trata de uma única capacidade ou restrição. |
| **Feasible (Factível)** | [x] Sim [ ] Não | Previsto no incremento proposto. |
| **Verifiable (Verificável)** | [x] Sim [ ] Não | Método: Teste, Demonstração. |
| **Correct (Correto)** | [x] Sim [ ] Não | Rastreável à fonte declarada. |
| **Conforming (Conforme)** | [x] Sim [ ] Não | Segue este template e a ISO/IEC/IEEE 29148:2018. |

---

## Informações Complementares

### Restrições e Dependências

- Requisitos relacionados: FR-031 (padrão atômico), FR-044, DR-007

### Notas e Suposições

- Requisito proposto; ainda não implementado.
- O requisito é proposto e pode mudar até a implementação.

### Anexos / Referências

- Código/testes: Novo formato de mapa; possível reutilização do `WorldManager` para carregar chunks prontos.
- Documento de origem: `requirements-voxel-editor.md`

---
