# REQ-ATTR-009 — Lógica testável sem OpenGL

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `AR-009`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `SRS.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `AR-009` |
| **Nome** | Lógica testável sem OpenGL |
| **Tipo** | Manutenibilidade |
| **Prioridade** | Essencial |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> A lógica de mundo, matemática, raycast e colisão deve ser importável e testável sem contexto OpenGL.

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
| **Rastreabilidade técnica** | `test_cpu_meshing_imports_without_opengl_or_glfw`; `test_voxel_provider_chunks_are_usable_without_graphics_context`; `tests/test_math.py`. |

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
Funcionalidade: Lógica testável sem OpenGL
  Cenário: Exercitar Lógica testável sem OpenGL
    Dado que o sistema está em operação
    Quando a condição do atributo é exercitada
    Então os módulos importam e são testados sem OpenGL
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | `test_cpu_meshing_imports_without_opengl_or_glfw`; `test_voxel_provider_chunks_are_usable_without_graphics_context`; `tests/test_math.py`. | A lógica de mundo, matemática, raycast e colisão deve ser importável e testável sem contexto OpenGL. |

Testes existentes: `tests/test_cpu_meshing_imports_without_opengl_or_glfw.py`, `tests/test_voxel_provider_chunks_are_usable_without_graphics_context.py`, `tests/test_math.py`.

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

- Verificação: `test_cpu_meshing_imports_without_opengl_or_glfw`; `test_voxel_provider_chunks_are_usable_without_graphics_context`; `tests/test_math.py`.
- Documento de origem: `SRS.md`

---
