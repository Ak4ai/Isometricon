# REQ-FUNC-015 — Movimento do token

> **Norma de referência:** ISO/IEC/IEEE 29148:2018 (Seções 5.2.5 e 5.2.8)
> **ID original:** `FR-015`
> **Origem:** baseline implementado
> **Arquivo-fonte:** `SRS.md`

---

## Identificação

| Campo | Valor |
|-------|-------|
| **ID** | `FR-015` |
| **Nome** | Movimento do token |
| **Tipo** | Funcional |
| **Prioridade** | Essencial |
| **Status** | Verificado |

---

## Descrição

### Texto do Requisito

> O sistema deve mover o token no plano horizontal com as teclas WASD, orientar o token na direção do deslocamento e animar caminhada enquanto houver movimento e repouso quando parar.

### Condições de Aplicação

- Modo terreno; teclas WASD pressionadas; token com ou sem avatar.

---

## Rastreabilidade

| Campo | Valor |
|-------|-------|
| **Fonte (Source)** | Código e testes do commit `0b5c1fe` |
| **Requisito Pai** | — |
| **Requisitos Filhos** | — |
| **Casos de Uso / Histórias Relacionadas** | — |
| **Rastreabilidade técnica** | `src/interactive/token_system.py`; `tests/test_interactive.py`; `tests/test_token_avatar.py`. |

---

## Justificativa (Rationale)

O token é a representação do jogador no tabuleiro.

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
Funcionalidade: Movimento do token
  Cenário: Exercitar Movimento do token
    Dado o modo terreno com teclas WASD
    Quando o usuário move o token
    Então ele se desloca no plano, gira para a direção e anima caminhada; ao parar, repousa
```

### Casos de Teste Associados

| ID do Teste | Descrição | Resultado Esperado |
|-------------|-----------|--------------------|
| TEST-001 | Teste automatizado (`tests/test_interactive.py`, casos de inicialização, movimento, yaw e caminhada; `tests/test_token_avatar.py`). | O movimento diagonal é normalizado; o yaw aponta para a direção do movimento; o avatar caminha enquanto o token se move e repousa ao parar; sem avatar, o token modular é exibido. |

Testes existentes: `tests/test_interactive.py`, `tests/test_token_avatar.py`.

---

## Análise de Conformidade com a Norma

| Característica | Atende? | Observações |
|----------------|---------|-------------|
| **Necessary (Necessário)** | [x] Sim [ ] Não | Requisito essencial para movimento do token. |
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

- Código/testes: `src/interactive/token_system.py`; `tests/test_interactive.py`; `tests/test_token_avatar.py`.
- Documento de origem: `SRS.md`

---
