# 👗 Proposta de Reestruturação do Motor de Roupas: Paridade Universal com Roblox WrapDeformer

> **Status do Documento:** Proposta Inicial em Revisão Contínua  
> **Data de Criação:** 22/09/2026  
> **Última Atualização:** 22/09/2026  
> **Objetivo:** Estabelecer uma arquitetura 100% universal e contínua para vestir qualquer roupa do Roblox (camisas, suéteres, vestidos, croppeds, regatas, jaquetas e calças) em avatares masculinos e femininos em tempo real (Python puro + NumPy), com 0 Blender em runtime e fidelidade idêntica ao Roblox Studio.

---

## 1. Contexto e Diagnóstico dos Problemas Atuais

Ao longo dos testes visuais com peças variadas do catálogo, identificamos anomalias recorrentes:
1. **Pontas e dentes de serra na cintura:** O suéter de tricô (`9240757332`) e a camisa vermelha *tucked-in* (`97984232018335`) apresentavam triângulos pontudos se projetando para fora ou para trás da cintura.
2. **Ombros amputados e buracos no corpo:** Em peças de ombro caído (*off-shoulder* como a `84986992221546`) e peças cropped com braçadeiras (`101748354579961`), o braço superior do avatar era cortado fora, deixando um buraco vazio de pele.
3. **Peito oco e gola quadrada tipo lápide:** Em decotes profundos ou camisas assimétricas, o motor descartava toda a pele do peito, deixando um vazio escuro e o pescoço flutuando como um bloco quadrado solto.
4. **Golas achatadas e comprimidas:** Decotes em V, laços frontais e mangas caídas eram amassados contra a clavícula por caixas de altura fixa.

---

## 2. Investigação Técnica dos Dados Brutos

Investigamos minuciosamente as Cages oficiais, os modelos de avatar e os arquivos baixados do Roblox (`.obj`, `.png`, `.rbxm`):

### 2.1 Coordenadas e Dimensões

| Modelo / Cage | Vértices | Largura X | Altura Y (Motor Z) | Profundidade Z (Motor Y) | Observação |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `character_clean.obj` (Masc) | 326 | $[-0.397, 0.397]\text{m}$ | $[-0.025, 1.820]\text{m}$ | $[-0.154, 0.165]\text{m}$ | Base masculina |
| `character_female_clean.obj` (Fem) | 257 | $[-0.439, 0.439]\text{m}$ | $[-0.025, 1.795]\text{m}$ | $[-0.141, 0.207]\text{m}$ | Base feminina (Busto chega a $Z=+0.207\text{m}$) |
| `inner_cage_universal.obj` | 1711 | $[-0.405, 0.406]\text{m}$ | $[-0.008, 1.846]\text{m}$ | $[-0.175, 0.174]\text{m}$ | Cage unificada A-pose neutra/masculina |
| `female_cages.obj` (Oficial R15) | 1513 | $[-0.448, 0.448]\text{m}$ | $[-0.035, 1.803]\text{m}$ | $[-0.159, 0.218]\text{m}$ | 15 Cages R15 femininas (`UpperTorso` chega a $Z=+0.218\text{m}$) |
| `roblox_female_cage_data.npz` | 1711 | $[-0.433, 0.437]\text{m}$ | $[-0.008, 1.803]\text{m}$ | $[-0.202, 0.150]\text{m}$ | Cage conformativa gerada via nearest (Busto ficou em $0.168\text{m}$) |
| `inner_cage.obj` (Oficial Roblox) | 5410 | $[-1.616, 1.616]$ studs | $[-2.750, 2.750]$ studs | $[-0.384, 0.384]$ studs | Manequim Roblox clássico (5.5 studs) |

### 2.2 Descobertas Cruciais
1. Com a transformação linear canônica ($X = -V_x \times 0.54$, $Y = V_z \times 0.54 + 0.007$, $Z = V_y \times 0.54 + 1.185$), **todas as roupas do Roblox já estão no espaço exato da Cage**.
2. **Por que o peito furou na camisa vermelha (`97984232018335`):**
   * A cage feminina em `roblox_female_cage_data.npz` tinha o busto em $Z=0.168\text{m}$, enquanto o corpo feminino do avatar (`character_female_clean.obj`) alcança $Z=0.207\text{m}$.
   * O clamp de damping em `deform_point` limitava a folga normal a no máximo $+0.0166\text{m}$, fazendo com que a camisa ficasse em $Z=0.183\text{m}$, ou seja, **2.4 cm atrás da pele do peito**!
   * No Roblox, a verdadeira cage feminina R15 (`female_cages.obj` -> `UpperTorso`) já avança até **$Z=+0.218\text{m}$**, ficando naturalmente 1.1 cm à frente da pele sem precisar de nenhum ajuste manual.
   * Além disso, a heurística `_collar_v < 120 and _upper_v < 1500` classificou incorretamente a camisa fechada como top aberto, mantendo a pele por baixo.
3. **Por que a camisa parecia "amassada" (tipo papel/origami):**
   * **Flat Facet Shading:** Os arquivos `.obj` do Roblox não trazem normais de vértice (`vn`). Nosso parser `parse_obj_as_mesh` atribuía uma normal plana por triângulo (`n0 = n1 = n2 = fn`). Sob luz direcional, cada polígono refletia luz em um ângulo brusco diferente.
   * **Escultura Original com Dobras Orgânicas:** A peça `oversized_tucked-in_red_syaa_shirt` já possui pregas modeladas pelo artista. Quando iluminadas com flat shading e somadas ao amortecimento tangencial não-linear que comprimia cumes em 70%, o tecido parecia amassado e quebrado.

---

## 3. Onde o Nosso Pipeline Atual Falhava vs Como o Roblox Faz

| Aspecto | No Roblox Engine (`WrapDeformer`) | No Nosso Pipeline Atual (Heurístico) | Causa do Erro |
| :--- | :--- | :--- | :--- |
| **Cintura & Barra** | **Não há fórmulas manuais.** A roupa mantém seu caimento orgânico; a Cage contém a peça. | Multiplica $X$ e $Z$ por $0.58$ em um subconjunto arbitrário de vértices (`torso_list`). | Vértices vizinhos não encolhem, rasgando a barra em dentes de serra pontudos. |
| **Volume do Busto Feminino** | O `WrapTarget` feminino oficial já tem o formato do busto ($Z \ge 0.218\text{m}$). Sem `if`. | Usava cage achatada ($Z=0.168\text{m}$) + clamp de normal em $0.026\text{m}$. | A roupa afunda para dentro dos seios do avatar por 2.4 cm. |
| **Shading do Tecido** | Normais de vértice suaves (Smooth Shading / Gouraud) médias por vértice. | Flat shading por triângulo quando o OBJ não tem `vn`. | Tecido com dobras fica parecendo papel amassado / celofane quebrado. |
| **Braços e Ombros** | **Nunca corta membros do avatar.** O braço superior fica 100% íntegro sob a roupa. | Aplica `slice_mesh_below_z(1.200m)` em qualquer manga curta. | Em roupas de ombro caído (*off-shoulder*), amputa o ombro e deltoide do boneco. |
| **Pele do Tronco** | A pele do corpo permanece sob roupas abertas; roupas fechadas cobrem a pele. | Heurísticas de contagem de vértices (`_collar_v < 120 and _upper_v < 1500`). | Classifica camisa de manga curta como biquíni e causa furos. |
| **Gola & Decote** | Preserva a modelagem do artista (decotes V, ombro caído, golas volumosas). | Compressor de 30 caixas puxa à força qualquer ponto acima de $Y=0.35$ para $1.485\text{m}$. | Achata e amassa o decote concebido pelo criador. |

---

## 4. Pilares da Nova Arquitetura Universal

Para garantir que **qualquer roupa funcione universalmente sem precisar de ajustes caso a caso**, a nova arquitetura se apoiará em 5 pilares:

### Pilar 1: Eliminação das Heurísticas Destrutivas
* **Aposentar o Tapering Artificial de Cintura:** Remover a multiplicação forçada de $sx, sz$ em `torso_list`. A roupa deve se conformar puramente pela superfície da Cage.
* **Aposentar o Compressor de Gola de 30 Bins:** Preservar a curvatura natural e altura original do decote ou gola modelada pelo artista.
* **Aposentar o Corte Plano nos Braços (`slice_mesh_below_z`):** O braço superior do avatar deve permanecer 100% modelado e íntegro para mangas curtas, regatas e camisas de ombro caído.

### Pilar 2: Continuous Joint Blending nas Articulações (Ombros e Joelhos)
* Na zona de transição do ombro ($|X| \in [0.18, 0.28]\text{m}$), qualquer ponto interpola suavemente entre a rotação da cage do Torso e a cage do Braço via função Hermite:
  $$w_{arm} = \text{smoothstep}(0.18, 0.28, |X|)$$
  $$P_{final} = (1.0 - w_{arm}) \cdot P_{torso} + w_{arm} \cdot P_{arm}$$
* Garante continuidade matemática $C^1$, eliminando fendas na dorsal e costuras sem precisar de costuras rígidas (*hard snapping*).

### Pilar 3: Cage Alvo Anatômica e Thickness Positiva Universal (Zero Penetração, Zero Ifs)
* A deformação de qualquer top feminino passa a usar a Cage Alvo com o volume real do busto ($Z \ge 0.218\text{m}$, extraída diretamente de `female_cages.obj` `UpperTorso`).
* Toda roupa é projetada a partir da Cage Alvo e empurrada para fora ao longo da normal da Cage com folga positiva garantida:
  $$P_{deformed} = P_{cage}(u, v, w) + o_t \hat{t} + o_b \hat{b} + \max(o_n, 0.005\text{m}) \hat{n}$$
* O offset tangencial original é transferido rigidamente sem compressão distorcida de 70%, preservando as dobras naturais da peça.
* Como $P_{cage}$ já está fora do corpo e $o_n \ge +0.005\text{m}$, a penetração do peito ou pele é impossível por definição matemática.

### Pilar 4: Sombreamento Suave Universal (Smooth Vertex Normals)
* O carregador `parse_obj_as_mesh` e o exportador de roupas calculam normais suaves por vértice via média ponderada dos triângulos adjacentes.
* Acaba de vez com o visual facetado de "papel amassado" em todas as roupas do catálogo.

### Pilar 5: Zero Dependência Externa em Runtime
* Todo o pipeline roda em Python puro + NumPy em milissegundos (< 2s no primeiro uso, instantâneo via cache).
* Zero chamadas ao Blender em tempo de execução.

---

## 5. Advertências, Riscos e Casos de Borda Mapeados

Durante a investigação, mapeamos as seguintes advertências cruciais que devem ser respeitadas durante a reestruturação:

1. **Roupas Assimétricas (ex: `84986992221546`):**
   - *Advertência:* Um ombro é coberto e o outro é totalmente nu. O código nunca pode aplicar heurísticas simétricas globais de ombro; a decisão de visibilidade do braço deve ser local ou o braço deve permanecer sempre inteiro.
2. **Camadas Múltiplas e Ilhas Desconexas (ex: `9240757332` com 55 componentes):**
   - *Advertência:* Botões, canelados e detalhes em relevo não podem ser filtrados por tamanho de componente (`len(c) < 20`). Toda a geometria precisa ser projetada continuamente na Cage.
3. **Sobreposição Calça vs Camisa (Layering):**
   - *Advertência:* Camisas que caem sobre a calça precisam de uma folga mínima na normal ($+0.005\text{m}$) na altura do cós ($Z \approx 0.95 - 1.05\text{m}$) para evitar z-fighting visual com a cintura da calça.
4. **Diferenças Anatômicas Masculino vs Feminino:**
   - *Advertência:* O corpo feminino possui maior inclinação pélvica e deltoides mais estreitos. No masculino, o ombro é largo. O amortecimento de ombro deve respeitar a largura do deltoide de cada sexo sem criar ombreiras infladas de futebol americano.
5. **Manutenção da Suíte de Testes:**
   - *Advertência:* Todos os 469 testes do projeto (`pytest tests/`) devem continuar passando com 100% de sucesso.

---

## 6. Checklist de Implementação (Passo a Passo)

- [ ] **Etapa 1: Limpeza das Heurísticas Destrutivas em `wear_engine.py`**
  - [ ] Remover o loop de encolhimento manual da cintura ($sx, sz$) em `fit_top_clothing`.
  - [ ] Desativar o compressor forçado de golas de 30 caixas em `fit_top_clothing`.
  - [ ] Eliminar o corte plano de braço `slice_mesh_below_z(1.200m)` em `apply_arm_hsr`.
- [ ] **Etapa 2: Atualização da Cage Feminina e Cálculo de Normais Suaves**
  - [ ] Atualizar a Cage Alvo Feminina para utilizar a curvatura real de `female_cages.obj` (`UpperTorso` com $Z \ge 0.218\text{m}$).
  - [ ] Implementar cálculo automático de normais de vértice suaves em `parse_obj_as_mesh` e exportação do wear engine.
  - [ ] Assegurar folga de espessura positiva universal ($\max(o_n, 0.005\text{m})$) sem esmagamento não-linear.
- [ ] **Etapa 3: Atualização do `CharacterModel` em `character_model.py`**
  - [ ] Preservar o braço superior íntegro para roupas curtas, regatas e ombro caído.
  - [ ] Substituir heurística de contagem de vértices de gola por detecção de cobertura real.
- [ ] **Etapa 4: Validação Visual no Catálogo Canônico**
  - [ ] Validar Camisa Tucked-in Vermelha (`97984232018335`) — Feminino (tecido suave, sem peito furando, sem pontas).
  - [ ] Validar Suéter de Tricô (`9240757332`) — Masculino e Feminino (sem pontas na cintura).
  - [ ] Validar Camisa Off-Shoulder (`84986992221546`) — Feminino (ombros e braços íntegros).
  - [ ] Validar Cropped com Laços (`101748354579961`) — Feminino (braçadeiras sólidas e gola natural).
  - [ ] Validar Boxy Shirt (`89475537632859`) — Masculino e Feminino (ombros naturais, sem asas).
  - [ ] Validar Cross Shirt (`94197227825305`) e Vestido Plaid (`114590471167431`).
- [ ] **Etapa 5: Verificação dos Testes Automatizados**
  - [ ] Rodar `pytest tests/` e certificar 469/469 aprovados.

---

## 7. Registro de Discussões e Atualizações da Proposta

*(Este espaço será atualizado continuamente com as decisões, sugestões e novos tópicos definidos nas nossas conversas.)*

* **22/09/2026 - Versão Inicial:** Documento gerado após investigação técnica comprovando que as roupas do Roblox já estão no espaço canônico correto e que os problemas visuais (pontas, rasgos e ombros amputados) provinham de 4 rotinas heurísticas destrutivas no código atual.
* **22/09/2026 - Diagnóstico da Camisa Vermelha Tucked-in (`97984232018335`):**
  - Descoberto por que o peito furou: A cage feminina usada no `.npz` estava achatada no busto ($Z=0.168\text{m}$) enquanto o corpo feminino vai até $Z=0.207\text{m}$. A verdadeira cage R15 oficial (`female_cages.obj`) tem $Z=0.218\text{m}$. Aliado a um clamp de amortecimento que limitava a folga normal a $+0.0166\text{m}$, a camisa deformada parava 2.4 cm atrás da pele.
  - Descoberto por que parecia amassada: O carregador `parse_obj_as_mesh` aplicava Flat Shading em arquivos sem normais de vértice (`vn`), transformando dobras orgânicas em facetas duras de origami; além de um damping tangencial que distorcia pregas em 70%.
  - Definição da solução universal estilo Roblox: Uso da Cage Alvo anatômica real (que já possui a geometria do busto), preservação linear do offset tangencial, folga normal mínima garantida ($\ge 5\text{mm}$) e cálculo automático de normais de vértice suaves (smooth shading). Zero `if`s no pipeline.
