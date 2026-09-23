# 👗 Motor Universal de Roupas — Paridade com Roblox LayeredClothing

> **Status:** Em implementação  
> **Última atualização:** 23/09/2026  
> **Objetivo:** Vestir qualquer roupa do catálogo Roblox em qualquer avatar (masculino ou feminino) sem clipping, sem heurísticas, usando deformação por cage como o Roblox faz.

---

## O Problema Central

O Roblox usa um sistema chamado **LayeredClothing** onde cada roupa é deformada por pares de cages (inner/outer). A roupa sempre fica **fora do corpo** porque a cage garante isso matematicamente — sem `if`s, sem cortes, sem truques.

Nosso motor atual usava heurísticas manuais (cortar braços, comprimir golas, encolher cintura) que quebravam para roupas novas. Precisamos replicar o sistema correto.

---

## Como o Roblox Faz (o que queremos replicar)

```
Para cada parte do corpo R15 (UpperTorso, LeftUpperArm, etc.):
  1. A roupa tem vértices próximos a essa parte
  2. O motor projeta esses vértices sobre a inner cage daquela parte
  3. Calcula coordenadas baricentricas (u, v, w) dentro do triângulo mais próximo
  4. Reconstrói a posição usando a outer cage na mesma posição (u, v, w)
  5. A roupa fica sempre FORA do corpo, preservando o shape original do artista
```

Resultado: zero clipping, zero cortes, qualquer roupa funciona automaticamente.

---

## Nossa Arquitetura (usando o que já temos)

### Assets disponíveis
| Arquivo | O que é | Status |
|---|---|---|
| `female_cages.obj` | 15 cages R15 femininas feitas no Roblox Studio | ✅ Pronto |
| `assets/models/clothing/cages/*.obj` | 15 cages R15 masculinas originais do Roblox | ✅ Pronto |
| `character_female_clean.obj` | Body mesh feminino | ✅ Pronto |
| `character_clean.obj` | Body mesh masculino | ✅ Pronto |
| Roupas `.obj` do catálogo | Geometria original do Roblox com inner/outer cage embutida | ✅ Baixados |

### Mapeamento Cage → Membro do Corpo

Cada vértice da roupa é deformado pela cage da parte mais próxima:

| Cage | Cobre no nosso personagem |
|---|---|
| `UpperTorso` | `Export_torso` + `Export_pecoco` |
| `LowerTorso` | `Export_pelve` |
| `LeftUpperArm` | `Export_braco_superior_esquerdo` |
| `RightUpperArm` | `Export_braco_superior_direito` |
| `LeftLowerArm` + `LeftHand` | `Export_antebraco_esquerdo` (antebraço+mão juntos) |
| `RightLowerArm` + `RightHand` | `Export_antebraco_direito` |
| `LeftUpperLeg` | `Export_coxa_esquerda` |
| `RightUpperLeg` | `Export_coxa_direita` |
| `LeftLowerLeg` | `Export_canela_esquerda` |
| `RightLowerLeg` | `Export_canela_direita` |
| `LeftFoot` | `Export_pe_esquerdo` |
| `RightFoot` | `Export_pe_direito` |
| `Head` | `Export_cabeca` |

### Transições entre partes (blending)
Na região de junção entre duas cages (ex: ombro entre `UpperTorso` e `UpperArm`), o vértice é influenciado por ambas com peso interpolado suavemente (smoothstep). Isso evita costuras ou rachaduras visíveis na roupa.

---

## Etapas de Implementação

### Etapa 1 — Carregar as cages por parte no motor
- [ ] Criar função `load_male_cages()` que lê os 15 OBJs de `assets/models/clothing/cages/` e aplica a `matrix_world` de cada parte (posição no world space)
- [ ] Verificar que `load_r15_female_cages()` já existente cobre o feminino
- [ ] Mapear cada parte da cage ao grupo de body mesh correspondente

### Etapa 2 — Atribuição de vértices da roupa às partes da cage
- [ ] Para cada vértice da roupa, determinar qual parte da cage é a responsável (baseado em proximidade + região anatômica)
- [ ] Vértices na zona de transição (ombro, quadril) recebem peso de duas cages

### Etapa 3 — Deformação baricêntrica por parte
- [ ] Para cada vértice da roupa e sua cage responsável:
  - Projetar no triângulo mais próximo da cage → obter `(u, v, w)` baricentricas
  - Calcular o offset normal/tangencial em relação à cage
  - Reconstruir posição final: `P = u*A + v*B + w*C + offset_normal * n`
- [ ] Garantir offset normal mínimo de `5mm` (roupa nunca penetra o corpo)

### Etapa 4 — Blending nas zonas de transição
- [ ] Vértices no ombro (transição Torso→Braço): interpolar resultado das duas cages com peso Hermite
- [ ] Vértices no quadril (transição UpperTorso→LowerTorso): mesma lógica

### Etapa 5 — Exportar OBJ deformado + cache
- [ ] Salvar resultado em cache por `(asset_id, genero)` com header `v3`
- [ ] Normais suaves calculadas automaticamente (smooth shading)

### Etapa 6 — Validação visual
- [ ] Suéter Knit (`9240757332`) — Masc e Fem
- [ ] Camisa Vermelha Tucked-in (`97984232018335`) — Fem
- [ ] Off-Shoulder (`84986992221546`) — Fem
- [ ] Cropped com laços (`101748354579961`) — Fem
- [ ] 469/469 testes passando

---

## Decisões de Arquitetura

| Decisão | Escolha | Motivo |
|---|---|---|
| Cage unificada ou por partes? | **Por partes (15 OBJs)** | Cage unificada não contém o body mesh corretamente; body sai 9cm na frente no torso |
| HSR (esconder braço sob manga)? | **Não — cage elimina isso** | Se a cage envolve o corpo e a roupa fica fora da cage, o corpo nunca fura a roupa |
| Masculino e feminino com a mesma lógica? | **Sim** | Mesmo pipeline, cages diferentes |
| Animar? | **Não (poses estáticas)** | App é de preview — cage não precisa articular |

---

## Registro de Progresso

- **22/09/2026:** Investigação inicial. Identificados problemas com heurísticas destrutivas.
- **22/09/2026:** Removidas heurísticas (waist tapering, collar compressor, arm slice). Implementadas normais suaves. Cache v2.
- **23/09/2026:** Descoberto que a cage NPZ usada pelo motor não é a cage do usuário — body mesh sai 9cm fora da cage no torso. Decisão: usar as 15 partes separadas diretamente.
