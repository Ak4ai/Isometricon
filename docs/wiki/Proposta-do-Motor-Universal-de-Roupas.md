# 👗 Motor Universal de Roupas — Paridade com Roblox LayeredClothing

> **Status:** documento histórico (a proposta de 23/09/2026 que deu origem ao encaixe por cage; estava na raiz do
> repositório como `proposta_motor_universal_roupas.md`). O que foi de fato construído está em
> [[Sistema de Roupas|Sistema-de-Roupas]] e o que foi tentado e descartado em [[Histórico de Experimentos|Historico-de-Experimentos]].  
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
- [x] Carregar as 15 cages femininas R15 diretamente via `load_r15_female_cages()`
- [x] Unificar `LeftLowerArm` + `LeftHand` em `LeftForearm` e `RightLowerArm` + `RightHand` em `RightForearm` para cobrir o antebraço contínuo do personagem

### Etapa 2 — Atribuição de vértices da roupa às partes da cage
- [x] Mapeamento anatômico robusto por membros: UpperTorso, LowerTorso, UpperArms e Forearms

### Etapa 3 — Deformação baricêntrica por parte (WrapDeformer R15)
- [x] Projeção de cada vértice na cage da parte correspondente
- [x] Preservação do volume tangencial e caimento natural do tecido
- [x] Garantia de folga normal mínima de `5mm` na pele (sem clipping) e preservação do decote onde $\hat{n}_z > 0.35$

### Etapa 4 — Blending nas zonas de transição
- [x] Articulação do Ombro: interpolação suave Hermite entre UpperTorso e UpperArm ($0.14 \le |X| \le 0.28$)
- [x] Articulação do Cotovelo: interpolação suave Hermite entre UpperArm e Forearm ($1.05 \le Z \le 1.16$)

### Etapa 5 — Exportar OBJ deformado + cache
- [x] Salvar resultado em cache por `(asset_id, genero)` com header `v3`
- [x] Normais suaves calculadas automaticamente (smooth shading)

### Etapa 6 — Validação visual e Testes
- [x] Suéter Knit (`9240757332`) — Masc e Fem (sem rasgos, sem pontas na cintura, mãos visíveis e shading suave Gouraud/Phong)
- [x] Camisa Vermelha Tucked-in (`97984232018335`) — Fem (peito e estampa SYAR intactos, gola anatômica na clavícula e braços íntegros)
- [x] Off-Shoulder (`84986992221546`) — Fem (ombro caído orgânico, alça de biquíni e braço íntegro)
- [x] Cropped com laços (`101748354579961`) — Fem (decote natural na clavícula, abdômen limpo sem artefatos flutuando)
- [x] 469/469 testes automatizados passando com 100% de sucesso (13.5s)

---

## Decisões de Arquitetura

| Decisão | Escolha | Motivo |
|---|---|---|
| Cage unificada ou por partes? | **Por partes (15 OBJs R15)** | Cobre 100% da anatomia real de cada membro com folga homogênea |
| HSR (esconder braço sob manga)? | **Não — cage elimina isso** | A cage de 15 partes garante que a roupa fica fora do corpo sem amputar membros |
| Masculino e feminino com a mesma lógica? | **Sim (feminino já migrado, masculino isolado e estável)** | Transição segura mantendo estabilidade |
| Animar? | **Não (poses estáticas)** | App é de preview — cage não precisa articular |

---

## Registro de Progresso

- **22/09/2026:** Investigação inicial. Identificados problemas com heurísticas destrutivas.
- **22/09/2026:** Removidas heurísticas (waist tapering, collar compressor, arm slice). Implementadas normais suaves. Cache v2.
- **23/09/2026:** Investigação das 15 cages. Confirmada cobertura anatômica completa de `female_cages.obj`.
- **23/09/2026:** Implementado o motor de deformação por partes R15 no feminino (`deform_top_mesh_r15`) com unificação de antebraço/mão (`Forearm`), interpolação Hermite nos ombros e cotovelos, ancoragem de ombro e preservação de decotes. 469/469 testes passando 100%.
