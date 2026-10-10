# 👗 Sistema de Roupas (WrapLayer & HSR)

## 📌 Resumo

O Isometricon possui um sistema completo e autônomo de vestuário em camadas (*layered clothing*) 100% desenvolvido em Python e integrado ao OpenGL. Inspirado na tecnologia **WrapLayer** do Roblox, o sistema substitui cortes e heurísticas manuais por uma abordagem geométrica fundamentada em **cages de referência** e **deformação radial-prismática**. O pipeline garante que qualquer roupa do catálogo Roblox vista perfeitamente os avatares do jogo (feminino e masculino) sem perfuração (*clipping*), preservando dobras, caimentos e a volumetria original do artista.

---

## 🏗️ Visão Geral da Arquitetura

O vestuário de um personagem depende do pareamento volumétrico entre pares de cages:

```mermaid
flowchart TD
    A["Roupa Bruta (.rbxm / .obj)"] --> B["Extração de Cages da Peça (Inner / Outer)"]
    B --> C["Pareamento UV com Cage do Corpo"]
    C --> D["Deformação Radial + Vínculo por Prisma"]
    D --> E["Preservação de Elementos Pendurados (> 3cm)"]
    E --> F["Encaixe da Malha Deformada"]
    F --> G["HSR (Hidden Surface Removal)"]
    G --> H["Pele Oculta sob a Roupa + Margem de Segurança"]
    H --> I["Renderização Final no Motor OpenGL"]
```

### Arquivos Principais do Pipeline
- `src/clothing/wrap_layer_fit.py`: Módulo orquestrador do encaixe via WrapLayer.
- `src/clothing/radial_prism_fit.py`: Núcleo matemático de projeção radial e interpolação prismática.
- `src/clothing/hsr.py`: Removedor de superfícies ocultas com suporte a máscaras binárias e geométricas.
- `src/clothing/wear_engine.py`: Motor de conformação e cache de vestuário.
- `src/clothing/character_model.py`: Representação do personagem com pilhas de roupas.

---

## 📐 Como Funciona o Pareamento por Cages

Cada peça de roupa do Roblox traz duas malhas de controle:
1. **Inner Cage (Referência R15):** Malha fechada que descreve o corpo padrão do Roblox no qual a roupa foi desenhada.
2. **Outer Cage:** Malha que envolve a superfície exterior da peça, definindo seu volume externo.

O corpo do nosso personagem possui sua própria cage de referência (`assets/models/female_cages_apose_stage2.obj` e `assets/models/male_cages_apose.obj`).

### Passos Matemáticos do Encaixe
1. **Pareamento UV:** Como nossa cage compartilha a mesma parametrização UV da cage padrão R15, cada vértice da nossa cage tem correspondência bijetiva na inner cage da roupa.
2. **Deformação Radial + Prisma:** 
   - A distância radial do vértice da roupa em relação à inner cage é medida ao longo da normal da superfície.
   - O deslocamento é mapeado para a outer cage correspondente através de coordenadas baricêntricas prismáticas.
3. **Preservação de Franjas e Pendurados:** Vértices que se encontram a mais de 3 cm da cage (como barras de saia soltas, laços, cordões) mantêm sua direção e comprimento originais em vez de serem repuxados contra as pernas ou tronco.

---

## 🛡️ HSR (Hidden Surface Removal)

Para evitar que a geometria do corpo atravesse as dobras das roupas durante poses e movimentação, o módulo `src/clothing/hsr.py` oculta dinamicamente os polígonos da pele cobertos por tecido:

1. **HSR Nativo (0x12):** Quando a roupa contém dados binários de HSR oficiais do Roblox, as faces cobertas são desativadas diretamente.
2. **Fallback Geométrico:** Para roupas que não incluem o bloco 0x12 (ou trazem versões antigas como 0x10), um algoritmo projeta raios invertidos da roupa contra a pele.
3. **Margem de Segurança:** Uma margem de pele sob as bordas abertas (golas, mangas e tornozelos) é preservada para evitar recortes visíveis ou buracos na malha.

![HSR Geométrico - Antes e Depois](images/roupas/hsr-geometrico-antes-depois.png)
*Figura 1: À esquerda, ausência do HSR geométrico causando furos sob roupas com decote; à direita, resultado corrigido com máscara geométrica e margem de tolerância.*

---

## 👗 Saias Longas e Término de Calças

- **Saias Longas:** Vestidos de festa e saias longas possuem ancoragem contínua para evitar rasgos entre as pernas quando o personagem se move ou altera sua pose.
- **Pés e Tornozelos:** Calças com terminação na canela ou tornozelo não ocultam inadvertidamente os pés do personagem.

![Saias Longas e Ancoragem](images/roupas/saias-longas-ancoragem.png)
*Figura 2: Saias longas, vestidos de noiva e vestidos de gala encaixados sem cortes ou distorções.*

![Pés e Tornozelos](images/roupas/calcas-terminacao-pes.png)
*Figura 3: Preservação da pele dos tornozelos e pés sob diferentes modelos de calças e bermudas.*

### A pele contra o tecido que está no corpo

A máscara de cada roupa foi feita para o corpo da própria roupa. No nosso corpo o tecido fica um pouco diferente, e
onde os dois discordam aparecia defeito. Ao recortar a pele (`CharacterModel._apply_hsr_skin`), cada vértice da pele
perto da borda da máscara mede o tecido de tudo o que está vestido, ao longo da própria normal
(`hsr.cloth_distance`, e `hsr.cloth_behind` para o tecido afundado no corpo):

- **A pele que fica e encosta no tecido, ou sai dele, entra para logo abaixo dele** (`CLOTH_CLEAR`, 4 mm; no máximo
  `CLOTH_PUSH`, 2,5 cm). Era o risco fino no peito do "Dark Brown Tied Crop Top": não um rasgo na roupa, e sim a
  quina do tronco atravessando o tecido onde ele afunda (conferido com a pele pintada de verde).
- **A pele é cortada ao longo da linha da máscara** (`hsr.clip_hidden`), não por triângulos inteiros. Antes, o
  triângulo que a linha cruzava ficava inteiro: dentes de serra em cada corte, que atravessam o tecido quando o
  corpo se mexe. Um triângulo só é cortado quando o tecido cobre o canto que ele perde; senão fica inteiro, como
  sempre ficou, para o corte nunca tirar o que estava à vista.

Medido na bateria de robustez (oito peças, os dois corpos, contra o código anterior): a pele furando na pose de
vestir caiu em 14 de 16 casos e ficou praticamente igual nos outros dois, +2 e +6 cm² (camisa social masculina
169 → 125 cm², suéter off-shoulder masculino 843 → 593, vestido feminino 2023 → 1519); ao andar, nenhuma peça piorou
além do ruído, em valor absoluto (no máximo +7 cm²; a bateria mostra a diferença para a pose de vestir, que por isso
sobe quando a pose de vestir melhora: no vestido feminino o pior passo foi de 1942 para 1737 cm²); buracos iguais
(no máximo +6 cm²). O tempo de montar o personagem não mudou (2,4 → 2,7 s no suéter com jeans).

Tentado e deixado de fora, por fazer a pele furar o tecido ao andar (bateria: camisa social masculina 4 → 89 cm²,
suéter 10 → 84):

- nunca cortar pele sem tecido na frente dela (tirava buracos do vestido, mas a pele que sobra sob a manga sai
  quando o braço balança);
- manter a pele que se vê de fora por uma abertura da roupa (raios a partir dos pontos escondidos da cage);
- refinar a malha da pele ao longo da linha antes de cortar (só mostra o quanto a linha é irregular, ponto a ponto
  da cage).

### Em aberto: as pontas na cava do crop top (tampas em leque)

As pontas que aparecem dentro da cava do "Dark Brown Tied Crop Top" não são da pele: são da roupa. A peça fecha
cada cava e a gola por dentro com um leque de triângulos, cada um com a sua cópia do vértice do meio (17 cópias em
cada cava, 32 na gola, todas no mesmo ponto na malha original). O encaixe move um vértice por mais do que o lugar
dele (a normal, o triângulo), e manda cada cópia para um lado, até 28 cm umas das outras: o leque vira um estouro
de espinhos dentro da manga, atravessando a borda do braço. Vê-se tirando os braços do desenho.

Tentado em 09/10/2026 e **retirado** (commit `1b5a453`, revertido): juntar de novo as cópias do meio dos leques
depois do encaixe (8 cópias ou mais de um mesmo ponto; 38 arquivos, de 15 peças).

- No crop top feminino as pontas somem. No masculino também, mas a tampa passa por cima do alto do braço e aparece
  como um bloco escuro com um degrau no ombro: troca um defeito por outro.
- Na bateria, das 30 combinações com leques, 8 sobem numa medida e 4 descem: o braço e o pescoço atravessam a tampa
  e contam como pele furando (crop top feminino 265 → 617 cm², masculino 512 → 1042), e a tampa estica quando o
  braço balança (terno Mafioso masculino 400 → 1454, sem diferença visível).
- Juntar todas as cópias que o encaixe separa (também as duas a quatro das costuras de UV, mais de 2500 grupos no
  catálogo) é pior: 12 peças pioram e 8 melhoram no corpo feminino (Realistic White Pigeon: tecido esticado de 604
  para 16 830 cm²). As cópias seguem ossos diferentes e, juntas no encaixe, puxam mais o tecido no movimento.
- As folhas de antes e depois ficaram em `artifacts/tampas` (fora do git).

Um caminho ainda não tentado: em vez de juntar as cópias, não desenhar os triângulos desses leques (a tampa some,
e com ela os espinhos), ou pôr a tampa junto do braço. Por enquanto o pincel da seção Ajuste fino não resolve isto,
porque o defeito é da roupa e não da pele.

### Medido e descartado: cada parte da pele só na sua parte da cage (10/10/2026)

Cada vértice da pele é posto no ponto mais próximo da cage inteira. Através da axila isso cruza as partes: no corpo
feminino, 34 vértices da lateral do tronco ficam na parte de dentro do braço (por isso, para esconder à mão
triângulos do tórax, pinta-se embaixo do braço), e o alto do braço fica no tronco.

- **Tronco fora da cage dos braços:** o crop top melhora (masculino 512 → 404 cm² de pele furando), mas sob casacos a
  lateral do tronco, que a máscara da manga escondia por acaso, passa a furar o tecido. Na rodada completa, 5
  combinações pioraram (dois sobretudos, +166 e +142 cm²).
- **Braços só na cage dos braços:** na rodada completa, 6 melhoraram (Black Oversized Warmers feminino 94 → 24) e 1
  piorou (Blue Fish Suit masculino, já em falha, 1196 → 1330). Ganho pequeno, com uma piora: não entrou.

Resultados em `artifacts/robustness/2026-10-10` (as duas regras) e `2026-10-10b` (só a dos braços), fora do git.
