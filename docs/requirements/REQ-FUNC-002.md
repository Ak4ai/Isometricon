# REQ-FUNC-002 — Câmera isométrica ortográfica

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-002`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `SRS.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-002` |
| **Nome** | Câmera isométrica ortográfica |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O sistema deve manter uma câmera ortográfica com yaw de 45°, pitch de aproximadamente 35,264°, zoom limitado entre 0,25 e 100, pan no plano XZ e rotação do tabuleiro em passos de 90° com transição interpolada em torno do foco.

### Condições de Aplicação

- Modo terreno, personagem ou demonstração; eventos de tecla, roda e arraste.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/camera/camera.py`; `tests/test_camera.py`. |

---

## Justificativa (Rationale)

A leitura isométrica depende de projeção ortográfica e foco estável.

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
Funcionalidade: Câmera isométrica ortográfica
  Cenário: Exercitar Câmera isométrica ortográfica
    Dado a câmera isométrica com alvo definido
    Quando o usuário aplica zoom, pan ou quatro rotações de 90°
    Então o foco permanece fixo e o ângulo retorna ao inicial
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste automatizado (`tests/test_camera.py`, 38 casos). | Quatro rotações de 90° retornam ao ângulo inicial; o foco permanece fixo durante a animação; o pan desloca o alvo apenas em X/Z. |

Testes existentes: `tests/test_camera.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial para câmera isométrica ortográfica. |
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

- Código/testes: `src/camera/camera.py`; `tests/test_camera.py`.
- Documento de origem: `SRS.md`

---
