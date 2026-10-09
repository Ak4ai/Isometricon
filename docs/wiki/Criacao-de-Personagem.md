# 🧑‍🎨 Tela de Criação de Personagem

## 📌 Resumo

`/skin interface` abre a tela de criação: um painel à esquerda com as seções e as opções em grade, e o
personagem girando ao lado. Funciona no terreno (`--terrain`) e no visualizador (`--char`). Cada opção
executa o mesmo comando do chat (ver [[Comandos do Chat|Comandos-do-Chat]]), então a tela e o chat nunca
divergem.

- Abrir já na tela: `python -m src.main --terrain --editor` (ou `--editor=cabelo` para abrir numa seção).
- Fechar: **Esc** ou o botão **Concluir**. No terreno, o jogo volta de onde parou, com a câmera de antes.
- Ao fechar, o personagem é **gravado** em `saves/personagem.json` e volta na próxima vez que o jogo abrir
  (`--novo` começa do padrão; opções de personagem na linha de comando, como `--top`, também ignoram o gravado).

## 🖱️ Controles

| Gesto | O que faz |
|---|---|
| Clique numa aba | troca a seção |
| Clique numa opção | aplica (o quadro da opção em uso fica contornado) |
| Arrastar um controle deslizante | muda um ajuste de -100 a 100 (perto do meio volta a 0) |
| Clique no campo do rodapé | digita ou cola (Ctrl+V) o id ou o link de um item do Roblox; **Enter** baixa e veste |
| Roda do mouse sobre o painel | rola a grade |
| Arrastar para os lados | gira o personagem (o giro automático pausa enquanto segura) |
| Arrastar para cima ou para baixo | inclina a câmera, de um pouco abaixo do personagem até quase de cima |
| **Espaço** ou botão **Girar** | liga ou desliga o giro automático |
| Roda do mouse sobre o personagem | zoom |
| **Shift + arrastar** ou botão do meio | move a câmera |
| **Q / E** | gira a câmera 90° |

**Câmera no rosto:** nas seções Olhos, Rosto, Nariz e Maquiagem a câmera vai sozinha para o rosto: na altura da cabeça (a da
pose atual, com os ajustes de altura e pescoço), de perto, na horizontal e com o personagem parado de frente. Dá
para girar, inclinar e dar zoom a partir daí; ao trocar para outra seção volta o enquadramento de corpo inteiro
que estava antes (`CharacterEditor.focus`, tratado no laço principal).

## 🗂️ Seções

| Seção | Opções | Comando |
|---|---|---|
| Corpo | roupa de baixo (usar ou não, cor); asas (cinco modelos, cor e ajustes); cauda (onze modelos, cor e ajustes); raças (corpos prontos, em cartões); feminino/masculino, tom de pele, formato da cabeça, vitiligo (quantidade e desenho das manchas) | `/skin corpo`, `/skin intima`, `/skin asa`, `/skin cauda`, `/skin raca`, `/skin pele`, `/skin cabeca`, `/skin ajuste vitiligo` |
| Ajustes | altura, cabeça, pescoço; ombros, peito, cintura, pelve, quadril, bunda; comprimento e grossura dos braços, mãos; comprimento e grossura das pernas, pés; folga das roupas | `/skin ajuste <nome> <-100 a 100>` |
| Olhos | estilo, formato e cor dos olhos (os dois ou cada um); tamanho, altura e distância dos olhos | `/skin olhos`, `/skin olho`, `/skin ajuste` |
| Rosto | boca e sobrancelhas; tamanho, altura e distância das sobrancelhas, que não acompanham os olhos; orelhas 3D e chifres 3D, com cor e ajustes | `/skin boca`, `/skin sobrancelha`, `/skin orelha`, `/skin chifre`, `/skin ajuste` |
| Nariz | com ou sem, o formato e os ajustes de cada parte, a cor da ponta e a sombra | `/skin nariz`, `/skin ajuste` |
| Maquiagem | batom, sombra dos olhos e blush (dezesseis cores, com matiz, saturação e brilho ajustáveis; a sombra e o blush com intensidade, tamanho e esfumado), contorno, sombras do queixo e do maxilar, sardas | `/skin maquiagem`, `/skin ajuste rosto_sombra` |
| Cabelo | padrão, raspado, careca; cor; cabelos do Roblox baixados | `/skin cabelo` |
| Superior | camisetas, camisas e suéteres | `/skin top <id>` |
| Jaqueta | peça por cima da roupa | `/skin jaqueta <id>` |
| Inferior | calças e shorts | `/skin calca <id>` |
| Vestidos | vestidos e saias (o comando decide se é de cima ou de baixo) | `/skin vestir <id>` |
| Extras | qualquer peça a mais, junto com as outras (polainas com saia, cinto, adesivos); clicar veste ou tira | `/skin extra <id>` |
| Sapatos | os dois pés como um item | `/skin sapato <esquerdo,direito>` |
| Ajuste fino | a altura da barra da blusa, da cintura e da barra da calça; a pele sob a roupa: espelhar os dois lados, ou pintar com o pincel onde ela some ou aparece | `/skin hsr` |
| Prontos | aparências prontas, voltar ao padrão, tirar roupas | `/skin preset`, `/skin reset`, `/skin tirar tudo` |

As roupas são os itens baixados em `assets/models/clothing`. A seção de cada um vem do tipo do asset do Roblox,
lido do item já encaixado em qualquer corpo; sem isso, do nome do arquivo. Um item novo baixado com
`/skin vestir <id>` aparece na próxima vez que a tela for aberta.

## 👁️ Olhos, maquiagem e pele

- **Formatos de olho** (`/skin olhos <formato>`, grupo "Formato dos olhos"): padrão, arredondado, grande, feminino
  (cílios mais longos e canto levantado), fechado, sonolento, estreito, puxado, caído, suave (sem as pontas de
  cílio) e suave redondo. São gerados a partir do desenho de olho anime que já existia
  (`src/clothing/eye_shapes.py`): o globo é esticado ou achatado, a pálpebra desce, as colunas se deslocam, cílios
  são acrescentados ou tirados, em cada olho por si e sem borrar os pixels. Valem para o olho anime (não para o
  clássico) e seguem a cor de cada íris. Um formato novo é uma entrada em `EYE_SHAPES`.
- **Modelos de olho** (mesmo comando e mesmo grupo): sério, masculino, afiado, redondo, retrô, cansado e felino.
  Também saem do olho padrão (`EYE_SHAPES`), com a íris, os brilhos e o lugar dele: tira-se a asa de cílios
  (`_trim`), desce-se a pálpebra, reta ou franzida (`_lid`), inclina-se, estica-se. Modelos desenhados do zero
  foram tentados e abandonados: ficavam vesgos, sem vida e baixos perto do original. Cada olho remodelado fica
  com o globo onde estava (`_ball_middle`), não com o desenho inteiro centrado.
- **Uma cor para cada olho:** em Olhos, "Cor dos olhos" pinta os dois; "Olho direito" e "Olho esquerdo" (os do
  personagem) pintam um só (`/skin olho <direito|esquerdo> <cor>`, `customization.iris_color_other`).
- **Contorno** (`/skin maquiagem contorno <suave|marcado|sem>`): sombra esfumada sob as maçãs do rosto, nas têmporas
  e no maxilar, e uma faixa de luz sobre as maçãs, pintadas na textura do rosto nos dois lados (`CONTOUR_SHADE`,
  `CONTOUR_SHINE`, em `customization.py`).
- **Sombras do queixo e do maxilar** (controle `rosto_sombra`): as sombras de baixo do rosto vêm de duas coisas, as
  facetas da cabeça abaixo do rosto, que recebem a luz de outro ângulo, e uma faixa de pele mais escura na textura
  que elas usam. Para menos, as normais dessas facetas viram a da frente do rosto (`body_shape.face_shading`) e a
  faixa clareia até a cor da pele (`CHIN_BAND`): em -100 o rosto fica liso. Para mais, as facetas escurecem pela cor
  do vértice e a faixa escurece. A frente do rosto não muda.
  **No corpo feminino o padrão é -100** (`body_shape.DEFAULTS`, lido por `resolved_body_adjust`): vale enquanto o
  controle não for mexido, um zero escolhido fica guardado, e `/skin ajuste reset` volta ao padrão do corpo.
- **Boca de vampiro** (`/skin boca vampiro`): a boca anime com uma presa sob cada lado dela, desenhadas por cima em
  degraus de dois pixels (`FANGS_AT`, `FANG_ROWS`), depois do batom, que elas não pegam.
- **Maquiagem** (`customization.makeup`): batom, sombra dos olhos e blush, cada um com uma cor, e as sardas. Tudo é
  refeito na textura da cabeça, sem recarregar o personagem.
  - **Cor:** dezesseis cores prontas (`MAKEUP_COLORS`) ou qualquer outra pelo chat (`/skin maquiagem blush #ff8899`,
    ou `200,40,55`). Três controles por item mexem na cor escolhida: matiz (meia volta do círculo de cores em cada
    ponta), saturação e brilho (`customization.shift_colour`), então dá para chegar a qualquer tom sem sair da tela.
  - **Batom:** recolore a boca mantendo o claro e o escuro do desenho.
  - **Sombra:** uma mancha esfumada sobre cada pálpebra e um pouco além do canto de fora, por baixo do desenho do
    olho e abaixo da sobrancelha. Controles: intensidade, tamanho e esfumado.
  - **Blush:** desenhado, uma mancha esfumada em cada bochecha sob os olhos (`BLUSH_AT`, `BLUSH_RADII`). Controles:
    intensidade, tamanho, esfumado e altura. Escolher uma cor de blush tira a camada antiga de blush
    (`face_details/blush_soft.png`), que continua existindo só pelo chat (`/skin maquiagem blush sim`).
  - Os controles são ajustes como os outros (`body_shape.MAKEUP`: `blush_intensidade`, `sombra_esfumado`,
    `batom_matiz`...), de -100 a 100, e valem a partir do desenho padrão de cada item.
- **Vitiligo:** desenhado pelo shader (`world_textured.frag`, `u_Vitiligo`) sobre as partes de pele, a partir da
  posição no corpo sem pose: as manchas ficam presas à pele ao andar e são iguais dos dois lados. Só o que tem a
  cor da pele clareia, então olhos, boca e sobrancelhas da textura do rosto ficam como estão. "Quantidade" vai de
  0 a 100 (o lado negativo do controle não faz nada) e "desenho" troca o padrão das manchas.

## 🧦 Peças extras

`CharacterModel.extra_ids` é uma lista de peças vestidas junto com as outras, cada uma encaixada no corpo por si
(como os sapatos) e incluída no recorte da pele. Serve para o que não disputa espaço com as outras: polainas com
saia, cinto, adesivos, luvas. Duas peças que ocupam o mesmo lugar (duas calças inteiras) se atravessam: só a
jaqueta é encaixada por cima de outra roupa.

## 💇 Cabelos feitos à mão (nudred)

Além dos cabelos do Roblox, o jogo veste cabelos feitos no Blender. O primeiro é o **nudred**: um afro baixo com
"twists" de esponja, degradê nos lados e na nuca e a linha da testa reta (`/skin cabelo nudred`, e o botão "Nudred"
no grupo "Estilo" da seção Cabelo).

- **Formato que o jogo veste:** um OBJ no espaço do corpo (Y para cima, Z para a frente), só triângulos, com uma
  coordenada de textura por vértice, chamado `assets/models/clothing/Hair_fitted_<id>_<corpo>.obj` (um por corpo,
  porque as duas cabeças não têm o mesmo tamanho). Sem uma textura `*<id>*.png` ao lado, o cabelo é desenhado na cor
  de cabelo do personagem, como o cabelo padrão. Os cabelos feitos à mão ficam em `character_model.HANDMADE_HAIR`
  (nome -> id) e são escolhidos pelo nome, sem nada para baixar.
- **Como o nudred é feito** (`scripts/blender_nudred_hair.py`, rodado dentro do Blender com `assets/models/123.blend`
  aberto): uma calota em volta da cabeça, medida a partir da própria cabeça por raios do centro dela. Nos lados e na
  nuca ela é um **degradê**: cabelo rente (3 mm), sem twists, nos 4 cm acima da linha do cabelo (`FADE`), e só então
  enche; sobre a testa não há degradê, o volume começa na linha. No alto ficam cerca de cento e sessenta "twists"
  compridos e largos (`TWIST_LENGTH`, `TWIST_RADIUS`), tubinhos de quatro anéis que giram um pouco a cada passo, mais
  em pé do que para fora, só onde o cabelo está cheio (`TWIST_FROM`). São cerca de 10 mil triângulos (o cabelo padrão
  tem 3,9 mil). A primeira versão tinha seiscentos twists curtos pela cabeça toda, lados incluídos.
- No `.blend` o script cria a coleção "Nudred": `Cabelo_Nudred` sobre a cabeça masculina, `Cabelo_Nudred_female`
  (oculto) sobre a feminina, e cópias de referência da cabeça e do cabelo padrão. Para mexer no cabelo à mão e levar
  de volta ao jogo, edite o objeto e chame `export(objeto, caminho, título)` do mesmo script.
- Os `.obj` são ignorados pelo git (`*.obj`); os dois do nudred foram adicionados à força (`git add -f`), como os
  corpos.

## 🩲 Roupa de baixo e o personagem inicial

Um personagem novo começa **sem roupas**, só com a roupa de baixo (`parse_character_cli_args`: nenhuma peça de cima
nem de baixo). Um personagem gravado continua com o que vestia.

A roupa de baixo não é uma peça 3D: é pintada na pele (`src/clothing/underwear.py`, `world_textured.frag`). O shader
decide por onde cada ponto fica no corpo sem pose (`v_BindPos`), só na pele do tronco e das pernas:

- **Corpo masculino:** cueca, uma faixa na pelve que desce um pouco pelas coxas.
- **Corpo feminino:** calcinha, cavada dos lados, e sutiã, uma faixa no peito com duas alças, na frente e atrás.
- As medidas de cada corpo (`underwear.CUTS`) são partes da pelve e do tronco dele, lidas do arquivo do corpo
  (`underwear.regions`); o cós, as bordas das pernas e as da faixa são um pouco mais escuros.
- Fica por baixo de qualquer roupa vestida: onde a roupa esconde a pele ela some junto, e pode aparecer onde a pele
  aparece (acima do cós de uma calça baixa).
- `/skin intima <sem|sim|cor|#rrggbb>` e o grupo "Roupa de baixo" na seção Corpo: a caixa "Usar" e oito cores
  (`underwear.COLORS`). Trocar a cor ou tirá-la não reconstrói nada. Fica em `AvatarCustomization.underwear`.
- No modo de edição da pele (transparência) ela não é desenhada: ali a pele mostra a máscara.

## 🧝 Raças

Na seção Corpo, logo abaixo de feminino e masculino, há cartões com corpos prontos de raça (`/skin raca <nome>`).
Uma raça não é outro modelo: é uma escolha do que a personalização já tem (`src/clothing/races.py`), aplicada ao
corpo feminino ou masculino em uso. Depois de aplicada, tudo continua ajustável como antes.

| Raça | Pele | Orelhas | O que muda no corpo |
|---|---|---|---|
| Humano | clara | humana | nada: as proporções padrão |
| Elfo | pálida | elfo asa | alto e esguio, pescoço e pernas longos |
| Anão | corada | redonda | baixo, largo, cabeça e mãos grandes, nariz batata |
| Orc | verde-oliva | elfo, pequena | alto, ombros e braços enormes, nariz achatado |
| Goblin | verde-amarelada | elfo, grande | pequeno, cabeça grande, nariz longo |
| Demônio | vermelha | morcego | um pouco mais alto e largo, olhos dourados |
| Vampiro | cinzenta | elfo asa, pequena | um pouco mais alto e fino, olhos vermelhos |
| Tritão | verde-água | barbatana | mãos e pés grandes (o povo do mar, sereio ou tritão) |
| Marciano | verde | sem | cabeça enorme em corpo fino, olhos grandes e afastados, sem nariz |
| Fada | rosada | elfo asa | minúscula e delicada |
| Felino | clara | gato | um pouco menor, olhos grandes e dourados |
| Lupino | morena | lobo | alto, ombros e braços fortes |
| Kitsune | clara | raposa | cintura fina, olhos vermelhos |
| Coelho | clara | coelho | pequeno, pés grandes, olhos vermelhos |
| Draconato | vermelho-escura | dragão | alto e largo, nariz achatado |
| Reptiliano | verde | réptil | pescoço longo, olhos afastados, sem nariz |
| Anjo | clara | humana | um pouco mais alto, com asas de penas |

- O demônio e o draconato vêm com chifres, e o vampiro com a boca de presas (que sai ao trocar de raça). Vêm com
  cauda o demônio, o felino, o lupino, a kitsune, o coelho, o draconato e o reptiliano, e com asas a fada, o demônio,
  o draconato e o anjo.
- Cada raça dá a cor da pele, o modelo de orelha, a cor dos olhos, o formato do nariz (ou nenhum) e os ajustes de
  proporção (`Race`). Escolher outra raça tira os ajustes que uma raça decide (`RACE_ADJUSTMENTS`: as proporções do
  corpo, as orelhas, o tamanho e a posição dos olhos) e mantém o resto: maquiagem, bordas das roupas, detalhes do
  nariz, cabelo, roupas e o corpo escolhido.
- A raça escolhida fica em `AvatarCustomization.race`, só para marcar o cartão: mexer num ajuste depois não a desfaz.
- **Cartões:** as miniaturas são desenhadas por `scripts/render_catalog_thumbnails.py` (o mesmo das roupas), cada
  raça em cada corpo, como o personagem começa (sem roupas, com a roupa de baixo) e o cabelo raspado, todas com o mesmo enquadramento para os tamanhos se
  compararem (`thumbs/racas/<raça>_<corpo>.png`, fora do git). A tela pede as que faltam ao abrir; até ficarem
  prontas o cartão mostra um X. O cartão mostra a raça no corpo em uso.
- Uma raça nova é uma entrada em `RACES`.

## 👂 Orelhas

O personagem não tinha orelhas; elas são opcionais (`/skin orelha <modelo>`, grupo "Orelhas" na seção Rosto, "sem"
por padrão). São malhas 3D geradas em `src/clothing/ears.py`, uma de cada lado da cabeça, presas a ela:

| Modelo | Como é |
|---|---|
| `humana` | simples, quadradinha, rente à cabeça |
| `redonda` | humana ainda, mais redonda e um pouco maior |
| `elfo` | longa e horizontal, saindo para o lado |
| `elfo_asa` | de elfo, em diagonal para trás e para cima, como uma asa |
| `morcego` | grande, apontando para cima |
| `barbatana` | três espinhos unidos, como uma nadadeira (povo do mar, sangue de dragão) |
| `gato` | triângulo pequeno no alto da cabeça |
| `cachorro` | em pé, larga e grossa, de ponta arredondada |
| `cachorro_caido` · `cachorro_uma_caida` | grande e caída ao lado da cabeça; uma em pé e uma caída |
| `lobo` | grande e pontuda, com um tufo na borda de fora |
| `raposa` | maior ainda e larga, inclinada para fora |
| `coelho` · `coelho_uma_caida` · `coelho_caidas` | duas longas em pé; uma em pé e uma caída; as duas caídas (a de coelho é mais comprida; a de cachorro, mais larga e mais grossa) |
| `dragao` | escamosa: um leque de espinhos para trás e para cima |
| `reptil` | escamosa: um disco baixo, rente à cabeça |

- Cada modelo é um contorno de dez pontos no plano da orelha (para trás, para cima), preso à cabeça pela borda da
  frente e aberto para fora por um ângulo (`EarShape.flare`: pouco numa humana, muito numa de elfo). A placa tem
  6 mm de espessura; a frente é mais escura no meio (a concha), e a cor é a da pele (cor de vértice, textura branca).
- As de gente ficam na altura dos olhos, nos lados da cabeça em uso (`ears.styled_rows` mede a cabeça), e giram com
  ela. **As de bicho ficam no alto da cabeça** (`EarShape.mount == "top"`), a `at` do meio à borda, inclinadas para
  fora por `tilt`. São da cor do cabelo (`coat="hair"`) e rosadas por dentro (`furry`). As escamosas são da cor da
  pele, com os triângulos alternando claro e escuro (`scaly`). Um modelo pode ter a orelha do outro lado diferente
  (`other`: uma em pé, uma caída).
- **As caídas são curvas de verdade** (`bend`): a orelha é cortada em sete fatias da raiz à ponta (`STATIONS`) ao
  longo de uma linha que sai da cabeça inclinada, dobra para fora no primeiro terço (`span`) e desce reta ao lado da
  cabeça (`ears._bent`). A largura dela corre de frente para trás, e o lado de dentro fica virado para a cabeça.
- A espessura é de cada modelo (`thick`): 6 mm nas de gente, 11 mm na de coelho, 15 a 16 mm nas de cachorro.
- **Cor** (`AvatarCustomization.ear_color`, `/skin orelha cor <auto|pele|cabelo|nome|#rrggbb>`): por padrão a do
  modelo. No grupo "Cor das orelhas" há duas caixas, "Cor da pele" e "Cor do cabelo" (clicar de novo desmarca e volta
  à do modelo), oito cores prontas (`ears.EAR_COLORS`), e nos ajustes três controles que mexem na cor que ela tiver:
  matiz, saturação e brilho. Trocar a cor só repinta os vértices.
- Todos os modelos têm os mesmos triângulos (os planos deixam alguns vazios): trocar de um para outro, ou mexer num
  ajuste, só move os vértices
  (`CharacterAnimator._styled_ears`). Só pôr ou tirar as orelhas reconstrói o personagem.
- Ajustes (`body_shape.EARS`): tamanho, altura e abertura (o quanto abrem para fora; nas do alto da cabeça, o quanto
  se inclinam).
- Não há nada que as esconda sob o cabelo: num cabelo cheio a orelha humana some dentro dele, e as longas saem
  por ele. Um modelo novo é uma entrada em `EAR_STYLES` com dez pontos.

## 🦌 Chifres

Opcionais, como as orelhas (`/skin chifre <modelo>`, grupo "Chifres" na seção Rosto, "sem" por padrão), gerados em
`src/clothing/horns.py`:

| Modelo | Como é |
|---|---|
| `demonio` | curtos e grossos, curvando para cima e para dentro, escuros |
| `bode` | longos, para trás e curvando para baixo, com anéis |
| `carneiro` | grossos, enrolando ao lado da cabeça |
| `touro` | para os lados e depois para cima e para a frente |
| `boi` | mais longos e abertos, com curva suave |
| `cervo` | galhada: uma haste com três pontas de cada lado |
| `unicornio` | um só, longo e reto, na testa, com sulco em espiral |
| `um` · `dois` · `tres` | um no meio da testa; um par; o par e o do meio |
| `um_quebrado` | um par com um dos chifres quebrado |

- Cada chifre (`Horn`) é uma linha que sai da cabeça numa direção (`rise`, `out`) e muda de direção ao longo do
  comprimento (`curl`, `sweep`), com oito anéis de seis lados em volta que afinam até a ponta. Uma ponta de galhada
  nasce de outro chifre (`parent`, `at`); um quebrado termina antes (`cut`), com a borda irregular.
- Um modelo (`HornSet`) é um conjunto deles, com a cor da base e a da ponta; um par é espelhado, e `side` põe um
  chifre no meio ou só de um lado.
- Todos os modelos têm os mesmos triângulos (oito tubos, os que sobram vazios): trocar de modelo, de cor ou mexer num
  ajuste só move os vértices (`CharacterAnimator._styled_part`). Só pôr ou tirar os chifres reconstrói o personagem.
- **Cor** (`/skin chifre cor <auto|nome|#rrggbb>`, grupo "Cor dos chifres"): a do modelo, uma de oito prontas
  (`HORN_COLORS`) ou qualquer outra pelo chat. **Ajustes** (`body_shape.HORNS`): tamanho e curva.
- Ficam presos à cabeça e giram com ela; não há nada que os ajuste ao cabelo. Um modelo novo é uma entrada em
  `HORN_STYLES`.

## 🐾 Caudas

Opcionais (`/skin cauda <modelo>`, grupo "Cauda" na seção Corpo, "sem" por padrão), geradas em
`src/clothing/tails.py`:

| Modelo | Como é |
|---|---|
| `felino` | longa, fina e igual, curvando para cima |
| `diabo` | um chicote fino da cor da pele, com a seta na ponta |
| `tigre` | longa e grossa, laranja com anéis escuros (tigre, onça) |
| `leao` | fina, da cor da pele, com um tufo de cabelo na ponta |
| `lobo` | cheia, caída |
| `raposa` | muito cheia, com a ponta branca |
| `cachorro` | mais curta, enrolada para cima |
| `cavalo` | um feixe longo de cabelo, caído |
| `coelho` | uma bolinha de pelo branca |
| `reptil` | grossa na base, afinando até a ponta, em escamas |
| `dragao` | a mesma, maior, com espinhos em cima |

- A cauda (`Tail`) é uma linha que sai para trás (`rise`) e muda de direção ao longo do comprimento (`curl`), com
  quinze anéis de oito lados cujo raio segue um perfil (`profile`): é o perfil que faz o tufo do leão, a seta do
  diabo (achatada dos lados, `flat`) e o volume do lobo e da raposa. A cor vem em faixas (`bands`: a ponta branca,
  o tufo de cabelo), listras em volta (`stripes`) ou escamas (`scaly`). Os espinhos do dragão são pontas de quatro
  lados em cima dela (`spikes`).
- Sai do meio da base das costas (`CharacterModel._tail_root`: atrás da pelve, um pouco abaixo do topo dela), presa
  ao osso da pelve: acompanha o corpo, mas não balança ao andar. Ela atravessa a roupa: não há furo na calça nem
  nada que a esconda sob uma saia.
- **Cor** (`/skin cauda cor <auto|pele|cabelo|nome|#rrggbb>`): a do modelo (a do cabelo nas de pelo, a da pele nas
  outras, cores próprias no tigre e no coelho), ou as mesmas opções das orelhas. **Ajustes** (`body_shape.TAILS`):
  tamanho e curva.
- Todos os modelos têm os mesmos triângulos: trocar de modelo, de cor ou mexer num ajuste só move os vértices. Só
  pôr ou tirar a cauda reconstrói o personagem. Um modelo novo é uma entrada em `TAIL_STYLES`.

## 🪽 Asas

Opcionais (`/skin asa <modelo>`, grupo "Asas" na seção Corpo, "sem" por padrão), geradas em `src/clothing/wings.py`:

| Modelo | Como é |
|---|---|
| `morcego` | membrana escura entre dedos longos, recortada atrás (demônio, vampiro) |
| `dragao` | a mesma, maior, da cor da pele |
| `anjo` | branca, com penas ao longo da borda de baixo |
| `fada` | duas asas finas e translúcidas de cada lado |
| `borboleta` | duas asas largas de cada lado, laranja com a borda escura |

- Cada asa (`Wing`) é feita de leques e de hastes no plano da asa, que abre para os lados e para trás (`sweep`). Um
  leque (`Fan`) são triângulos de um centro até um contorno: a membrana do morcego parte do pulso, de onde saem os
  dedos, com a borda de trás recortada entre eles e um segundo leque entre o braço e o corpo; as penas do anjo vêm em
  duas fileiras, as longas embaixo e as curtas por cima. Uma haste (`Rib`) é uma tira estreita sobre a membrana, dos
  dois lados: o braço e os dedos do morcego, as hastes das penas, as nervuras das asas de fada e de borboleta. A
  membrana tem frente e verso, a 4 mm um do outro.
- **De onde saem** (`CharacterModel._wing_root`): do ponto mais atrás da metade de cima do tronco, na altura das
  omoplatas. A primeira versão olhava só os vértices daquela altura; o corpo masculino, de poucos vértices, tem ali
  só os do peito, e as asas saíam pela frente. A cauda sai do ponto mais atrás da pelve (`_tail_root`).
- **A de fada é translúcida** (`Wing.alpha`): as asas assim são desenhadas por último, com mistura
  (`CharacterModel.draw`, o uniforme `u_Alpha`), sobre o que está atrás delas.
- Ficam presas ao osso do tronco: acompanham o corpo, mas não batem. Atravessam a roupa, como a cauda.
- **Cor** (`/skin asa cor <auto|pele|cabelo|nome|#rrggbb>`) e **ajustes** (`body_shape.WINGS`): tamanho e abertura
  (mais abertas para os lados, ou recolhidas para trás).
- Todos os modelos têm os mesmos triângulos: trocar de modelo, de cor ou mexer num ajuste só move os vértices. Um
  modelo novo é uma entrada em `WING_STYLES`.

## 🖌️ Ajuste fino: a pele sob a roupa

A pele escondida sob cada roupa é uma marca por ponto da cage do corpo (ver
`src/clothing/hsr.py`). O cálculo automático erra em algumas peças: a manga curta do "Dark Brown Tied Crop Top" fica
rente ao braço, dois pontos de um braço ficam visíveis enquanto os espelhados do outro ficam escondidos (a malha da
peça não é simétrica), e a pele atravessa o tecido em dentes. A seção corrige isso de dois jeitos, separados:

- **Automático, por espelhamento** (`/skin hsr espelhar <sim|nao>`): um ponto escondido de um lado do corpo esconde
  o que o espelha do outro (`hsr.mirror_index`, pontos a até 5 mm do espelho). Só iguala os dois lados: não esconde
  o que o cálculo deixou visível nos dois. É uma escolha do personagem, desligada por padrão, e não muda o encaixe
  nem as máscaras gravadas das roupas.
- **À mão**, com duas caixas, cada uma por si (havia uma terceira, "Editar pele", que só liberava as outras e saiu):
  - **Ativar pincel:** o botão esquerdo pinta, e os pontos da cage, que são o que se pinta, aparecem sobre o
    personagem nas cores da legenda (amarelo os do traço em curso). Desmarcada, o botão esquerdo gira o personagem
    como nas outras seções. Na primeira vez que é marcada, a transparência vem junto.
  - **Transparência:** a pele aparece inteira, sem recorte, pintada pelo que a máscara diz em cada lugar
    (`hsr.edit_colours`, cores de vértice misturadas sobre a cage), sob as roupas transparentes (`EDIT_CLOTH_ALPHA`, o
    uniforme `u_Alpha` do shader). Sozinha, serve para olhar a máscara. Desmarcada, o personagem é mostrado como no
    jogo, com as roupas opacas e a pele recortada, e dá para pintar vendo o resultado de cada traço.
  - Com qualquer uma das duas ligada aparecem a legenda e as setas de desfazer, e o botão direito gira e inclina o
    personagem. Tudo isso vale só na seção: ao trocar de seção ou fechar a tela o personagem volta ao normal.
- **Braços a 90°** (outra caixa): o personagem fica com os braços abertos para os lados enquanto a tela está nesta
  seção (`CharacterAnimator.arms_out`), para ver e pintar as axilas e a lateral do tronco, que os braços cobrem em
  descanso. Os pontos acompanham a pose. Vale com ou sem o modo de edição.
- **O pincel pinta pelo que está sob ele:** além dos pontos da cage que aparecem no círculo, ele pega os pontos que
  decidem a pele sob o círculo (`CharacterModel.hsr_skin`: para cada vértice da pele, os três pontos da cage que o
  decidem e quanto cada um pesa; entra quem pesa mais de 20%, `skin_brush.SURFACE_SHARE`). Um ponto pode estar fora
  de vista (dentro da axila, numa faceta virada para o outro lado) e ainda decidir a pele da frente: sem isso ficava
  um trecho no meio dos pontos pintados que não pintava.
- **Desfazer e refazer:** Ctrl+Z e Ctrl+Shift+Z, ou as duas setas no canto de cima à direita (apagadas quando não
  há o que desfazer ou refazer). Valem para as correções da pele (pintura, espelhamento, apagar tudo), até 100
  passos, só nesta sessão (`/skin hsr desfazer`, `/skin hsr refazer`, `SkinCommandHandler.hsr_history`).
- **Legenda:** no canto de baixo à direita, o que é cada cor (`skin_brush.LEGEND`).
- **O pincel**, como no Blender: o botão esquerdo pinta os pontos sob o círculo, só os do lado de cá do corpo e na
  frente (`skin_brush.BrushView.pick`); Ctrl faz o contrário do pincel escolhido (mostra com o de esconder, e
  vice-versa); o botão direito gira e inclina o personagem. Os pincéis são Esconder pele, Mostrar pele e Apagar
  pintura (devolve o ponto ao automático), em três tamanhos, com simetria opcional (pinta também o ponto espelhado).
  Soltar o botão manda um comando só (`/skin hsr <esconder|mostrar|apagar> <pontos>`), e a pele é refeita sem
  reconstruir o personagem (`CharacterModel.refresh_skin`). "Apagar tudo" é `/skin hsr limpar`.

O que é pintado vence o automático (`hsr.adjusted_hidden`) e fica em `AvatarCustomization` (`hsr_mirror`,
`hsr_hide`, `hsr_show`), salvo com o personagem. Vale para o personagem, não para a peça: trocar de roupa mantém a
pintura, que pode não servir à roupa nova. Os pontos são mostrados posados com os ossos do personagem
(`CharacterAnimator.posed`); as deformações sem osso (peito, cintura) não entram, e com elas os pontos ficam um pouco
fora do lugar. `--pincel=<esconder|mostrar|apagar>` abre o jogo já no modo de edição, e `--mouse="x,y,press;x,y;x,y,release"` move e
clica o mouse por um roteiro, um passo por quadro, pelos mesmos caminhos do mouse de verdade (conferências).

No jogo o personagem é montado em segundo plano (`CharacterModel.poll`), e o que a montagem descobre (a máscara da
pele, as bordas das roupas, o formato da malha do nariz) é levado para o modelo em uso na troca. Sem isso o pincel
não tinha o que pintar fora do `--char` com captura de tela.

### Bordas das roupas

Três controles (`/skin ajuste blusa_barra`, `calca_cintura`, `calca_barra`, de -100 a 100) levam uma borda da roupa
para cima ou para baixo, até 8 cm (`body_shape.GARMENT_REACH`):

- A borda vai inteira e o tecido a acompanha cada vez menos até 20 cm dela (`body_shape.move_edge`), então a peça
  estica ou encolhe perto da borda sem dobrar. As mangas de uma blusa ficam nos braços: só o que está no tronco se move.
- Onde está a borda vem da peça encaixada (`CharacterModel.garment_edges`: o ponto mais baixo e o mais alto, fora as
  mangas). A mudança é feita na pose de encaixe, junto com os ajustes do corpo (`CharacterAnimator._reshape`), sem
  encaixar a roupa de novo.
- **A pele sob a peça é calculada de novo** (`hsr.recut_mask_edges`): a peça encaixada é movida como o personagem a
  mostra e raios saem da cage do corpo através dela (`ray_hidden_mask`, o mesmo cálculo das peças sem máscara do
  Roblox). Da borda para fora, e para dentro da peça até onde o tecido se moveu (20 cm), a máscara passa a ser o que
  os raios acham; o resto dela e os braços ficam como eram. Pele que estava à mostra só é escondida onde está coberta
  em toda a volta: um cordão ou uma alça passando sobre a pele também é atingido por um raio, e esconder a pele sob
  ele abria um buraco.
- **Enquanto o controle é arrastado só o tecido se move**; a pele é recortada ao soltar (cerca de meio segundo na
  primeira vez de cada valor). O recorte da pele em si ficou imediato: onde cada vértice da pele fica na cage é
  guardado à parte (`_NEAREST`) e cada recorte é só uma conta sobre isso, com o mesmo resultado de
  `hsr.cull_hidden_triangles`. Antes, cada passo do arraste refazia essa busca, cada vez mais devagar, e o controle
  parecia travado.
- Valem para a peça de cima e a de baixo (um vestido é a peça de cima, e a barra dele é a da saia); jaqueta, sapatos e
  peças extras não têm esses controles. A borda só sobe e desce: ao descer sobre uma parte mais larga do corpo o
  tecido não alarga, e a pele pode aparecer.

## 📐 Ajustes de proporção

Cada ajuste vai de -100 a 100 (0 = o corpo como foi modelado) e fica em `AvatarCustomization.body_adjust`, gravado
com o personagem. Nenhum mexe só no corpo ou só na roupa, o que desfaria o encaixe: todos agem igual sobre pele,
roupa e cabelo (`src/clothing/body_shape.py`).

- **Altura, cabeça, pescoço, ombros, pelve, quadril, braços, pernas, mãos e pés** são escalas por osso, aplicadas com
  o esqueleto (`Skeleton.pose(..., scales, height)`): o que o osso carrega muda junto e os ossos filhos acompanham
  sem mudar. Grossura e comprimento de braços e pernas são independentes (através e ao longo do osso). Com as
  pernas mais longas o corpo sobe (`ground_lift`), e os pés crescem sem afundar no chão.
  Quadril é a largura da pelve; pelve é o seu tamanho para os lados e de frente para trás.
- **Peito, bunda e cintura** não têm osso: são uma deformação do espaço na pose de vestir (`warp`). A pele e o
  tecido que está sobre o mesmo ponto se movem juntos; a cintura deixa as mãos, que ficam ao lado, onde estão.
- **Folga das roupas** é o único que age só no tecido: afasta-o ao longo da própria superfície, até 2 cm. Para
  aproximar o limite é 3 mm: mais que isso a pele atravessa a roupa justa.
- **Olhos e sobrancelhas** agem na textura da cabeça: a camada é escalada, erguida ou afastada antes de ser colada
  (`customization.place_face_layer`).
- **Nariz:** os corpos atuais não traziam o nariz (ele tinha sumido na troca dos arquivos de corpo). O nariz é
  gerado por parâmetros (`src/clothing/nose.py`, `NoseShape` e `build`), com as medidas do nariz do modelo masculino
  antigo como base: cortes ao longo do dorso, cada um com a largura no rosto, a largura do dorso e a projeção. É
  posto no rosto de cada cabeça (`styled_rows`) e preso a ela.
- **Formatos de nariz** (`/skin nariz <formato>`, grupo "Formato do nariz"): padrão, projetado, ponta larga, narinas
  largas, aquilino (ponte curva para fora), arrebitado (ponte para dentro e ponta levantada), fino, largo, botão,
  longo; os curtos e largos, com as **asas das narinas** como um bloco de cada lado da ponta (`wing_width`,
  `wing_height`, `wing_depth`): botão largo, botão arrebitado, narinas grandes, achatado, batata e aberto; e bloco
  (a malha antiga, objeto `nariz.002`, como era). Nos formatos sem asas os blocos têm tamanho zero. Os formatos gerados têm os mesmos triângulos, então
  trocar entre eles muda a malha no lugar; só o bloco reconstrói o personagem. Para um formato novo, acrescente
  uma entrada em `nose.NOSE_STYLES`.
- **Ajustes do nariz inteiro:** tamanho, largura, projeção e posição valem por cima de qualquer formato, em torno
  do ponto onde o nariz se apoia no rosto (`body_shape.nose_shape`).
- **Ajustes de cada parte** (`nose.adjusted`, mudam as medidas do formato; não valem para o bloco): largura da
  ponte, altura da ponte (quanto ela sai do rosto), largura da ponta, projeção da ponta (só ela, sem as narinas), largura da base (narinas e asas), altura da
  base (as asas ficam mais altas e o nariz começa a alargar mais acima) e posição das narinas (as asas sobem ou
  descem até 8 mm; só tem efeito nos formatos com asas).
- **Cor da ponta:** a cor dos vértices da ponta e das asas multiplica a textura (`nose.tip_colours`): positivo
  deixa mais rosada, 0 é a cor da pele, negativo escurece um pouco. A ponte fica sempre na cor da pele.
- O nariz pega a cor de um trecho da textura do rosto entre os olhos. O trecho do nariz antigo encostava na borda
  da boca e a base saía rosada; nos formatos gerados ele para antes (`nose.UV_SPAN`).
- **Sombra do nariz:** um trecho um pouco mais escuro pintado na textura do rosto, entre os olhos, como na textura
  antiga da cabeça. A malha do nariz usa esse pedaço da textura, então escurece junto. O controle vai de sem
  sombra (-100) ao dobro (+100), e a sombra acompanha o tamanho, a largura e a altura do nariz. Essa é a sombra
  **legada** (`/skin nariz sombra legado`, o padrão).
- **Sombra calculada** (`/skin nariz sombra calculada`, grupo "Sombra do nariz"): feita a partir do nariz em uso. A
  malha do formato, com todos os ajustes, é vista de frente na textura do rosto (`nose.model_rows`,
  `nose.face_pixels`, medidas em `FACE_PIXELS`): o contorno ganha uma borda de sombra, e cada ponto lança a sua para
  o lado e para baixo conforme o quanto sai do rosto (`NOSE_CAST_FALL`), então um nariz projetado tem sombra mais
  longa e um de narinas largas, mais larga. Ela esmaece nariz acima até sumir no topo da ponte (`NOSE_FADE`) e não
  cai sobre o nariz: nesse modo o nariz inteiro pega a cor de um ponto limpo da pele (`nose.PLAIN_UV`), não do
  trecho entre os olhos que a sombra legada escurece. Trocar o formato ou mexer num ajuste do nariz refaz a textura.
- **Bloco com narinas** (`/skin nariz bloco_narinas`): o nariz em bloco do modelo antigo com as asas das narinas do
  "batata" ao lado da ponta. Como o bloco, é uma malha própria: trocar para ele ou a partir dele reconstrói o nariz.
- **Ajustes nos narizes em bloco** (`nose._block`): o bloco tem dois níveis, a caixa da ponta e o topo da ponte. A
  frente da ponta segue a largura da ponta, o fundo dela (no rosto) a largura da base, o topo a largura e a altura
  da ponte, e a caixa da ponta cresce com a altura da base. No bloco com narinas, as asas acompanham a ponta e
  seguem a largura e a altura da base e a posição das narinas.
- **O rosto muda sem recarregar o personagem:** olhos (cor, tamanho, altura, distância), sobrancelhas e boca refazem
  só a textura da cabeça e a trocam no lugar (`CharacterModel.refresh_face`, ~30 ms). Só o que muda geometria
  reconstrói o personagem: pôr ou tirar o nariz, e os olhos clássicos, que o tiram.
- Com tudo em 0, nada muda em relação ao personagem sem ajustes. A bateria de robustez não mede os ajustes; os
  extremos foram conferidos por imagem no corpo feminino com roupa justa (regata e meia-calça), parado e andando.
- A pose de descanso dos braços não é recalculada com os ajustes: com quadril ou pelve muito largos as mãos podem
  encostar no quadril.

## 🖼️ Miniaturas

```
python scripts/render_catalog_thumbnails.py            # só as que faltam
python scripts/render_catalog_thumbnails.py --force    # refaz todas
python scripts/render_catalog_thumbnails.py --only <id> ...
```

Veste cada item num corpo, enquadra a peça e grava `assets/models/clothing/thumbs/<id>.png` (ignorado pelo git).
A tela roda esse script sozinha, num processo à parte, quando um item novo chega ou falta alguma miniatura.
Sem miniatura, o quadro mostra a textura crua da peça.

## 🧩 Como é feita

- `src/interactive/character_editor.py`: `catalog()` (itens por seção), `CharacterEditor` (seções, disposição,
  cliques, rolagem, arraste e o desenho do painel com PIL). A lógica não depende de OpenGL e é testada em
  `tests/test_character_editor.py`.
- `src/rendering/hud_quad.py`: uma imagem 2D desenhada sobre a cena; o painel só é reenviado à GPU quando muda.
- `src/main.py`: com a tela aberta, o mundo não é atualizado nem desenhado; só o personagem, na área à direita do
  painel, com a luz do visualizador.
- Para acrescentar uma seção ou opção, edite `CharacterEditor._make_sections`: cada `Option` tem o rótulo, o
  comando do chat e como saber se está em uso.
