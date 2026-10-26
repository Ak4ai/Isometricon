# REQ-FUNC-035 — Modo editor de mapa e objetos

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-035`
> **Origem:** incremento proposto
> **Arquivo-fonte:** `requirements-voxel-editor.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-035` |
| **Nome** | Modo editor de mapa e objetos |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Proposto |

---

## Descrição

### Texto do Requisito

> O sistema deve oferecer um modo de execução dedicado ao editor de mapa e objetos, selecionável por linha de comando e por ação de interface do usuário, no qual o usuário cria, abre e salva um projeto de mapa sem iniciar a partida.

### Condições de Aplicação

- Aplicação iniciada; modo editor solicitado; projeto novo ou existente.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Pedido de extensão de 21/10/2026 e pesquisa do Replicube (ver `requirements-voxel-editor.md`) |
| **Requisito Pai** | FR-003 |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/main.py` (novo modo), novo pacote de editor, UI própria; o editor de personagem permanece separado. |

---

## Justificativa (Rationale)

O editor permite criar conteúdo próprio sem depender do gerador procedural.

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
Funcionalidade: Modo editor de mapa e objetos
  Cenário: Exercitar Modo editor de mapa e objetos
    Dado o modo editor solicitado
    Quando ele abre
    Então plataforma, painel e barra de ferramentas aparecem e os modos anteriores continuam disponíveis
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste de integração (a criar) para entrada/saída do modo; demonstração. | O modo editor abre com plataforma, painel e barra de ferramentas; ao sair, o modo anterior continua funcional; nenhum comando do editor altera o personagem. |

Testes existentes: A criar (nenhum teste existe no baseline).

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial para modo editor de mapa e objetos. |
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

- Requisitos relacionados: FR-003, FR-019, FR-021, FR-031

### Notas e Suposições

- Requisito proposto; ainda não implementado.
- O requisito é proposto e pode mudar até a implementação.

### Anexos / Referências

- Código/testes: `src/main.py` (novo modo), novo pacote de editor, UI própria; o editor de personagem permanece separado.
- Documento de origem: `requirements-voxel-editor.md`

---
