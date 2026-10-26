# REQ-FUNC-037 — Cor por voxel

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-037`
> **Origem:** incremento proposto
> **Arquivo-fonte:** `INCREMENTO-EDITOR-VOXEL.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-037` |
| **Nome** | Cor por voxel |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Proposto |

---

## Descrição

### Texto do Requisito

> O editor deve permitir atribuir a cada voxel uma cor escolhida de uma paleta com pelo menos 16 cores nomeadas, além de cor livre em formato hexadecimal, e recoloriar voxels existentes sem alterar sua geometria.

### Condições de Aplicação

- Ferramenta de pintura ou de atributo de cor ativa; paleta aberta; voxel existente ou novo.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Pedido de extensão de 21/10/2026 e pesquisa do Replicube (ver `INCREMENTO-EDITOR-VOXEL.md`) |
| **Requisito Pai** | FR-036 |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | Novo atributo de material por voxel; renderização e serialização. |

---

## Justificativa (Rationale)

A cor é a forma mais direta de diferenciar materiais e dar identidade ao objeto.

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
Funcionalidade: Cor por voxel
  Cenário: Exercitar Cor por voxel
    Dado a paleta aberta
    Quando o usuário escolhe #ff8800 e pinta um voxel
    Então o voxel muda de cor sem se mover e a cor fica no histórico recente
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste unitário de paleta e de atribuição (a criar); demonstração visual. | A cor escolhida aparece no voxel no mesmo quadro; trocar de cor não move o voxel; a paleta guarda as cores usadas recentemente; cor inválida é rejeitada com mensagem. |

Testes existentes: A criar (nenhum teste existe no baseline).

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial para cor por voxel. |
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

- Requisitos relacionados: FR-036, FR-038, FR-040

### Notas e Suposições

- Requisito proposto; ainda não implementado.
- O requisito é proposto e pode mudar até a implementação.

### Anexos / Referências

- Código/testes: Novo atributo de material por voxel; renderização e serialização.
- Documento de origem: `INCREMENTO-EDITOR-VOXEL.md`

---
