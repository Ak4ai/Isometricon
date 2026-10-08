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

## 🗂️ Seções

| Seção | Opções | Comando |
|---|---|---|
| Corpo | feminino/masculino, tom de pele, formato da cabeça, vitiligo (quantidade e desenho das manchas) | `/skin corpo`, `/skin pele`, `/skin cabeca`, `/skin ajuste vitiligo` |
| Ajustes | altura, cabeça, pescoço; ombros, peito, cintura, pelve, quadril, bunda; comprimento e grossura dos braços, mãos; comprimento e grossura das pernas, pés; folga das roupas | `/skin ajuste <nome> <-100 a 100>` |
| Rosto | estilo e cor dos olhos, boca, sobrancelhas; tamanho, altura e distância dos olhos, altura das sobrancelhas; nariz (com ou sem), seu tamanho, largura, projeção, altura e sombra | `/skin olhos`, `/skin boca`, `/skin sobrancelha`, `/skin nariz`, `/skin ajuste` |
| Maquiagem | batom e sombra dos olhos (dez cores cada), blush, sardas | `/skin maquiagem` |
| Cabelo | padrão, raspado, careca; cor; cabelos do Roblox baixados | `/skin cabelo` |
| Superior | camisetas, camisas e suéteres | `/skin top <id>` |
| Jaqueta | peça por cima da roupa | `/skin jaqueta <id>` |
| Inferior | calças e shorts | `/skin calca <id>` |
| Vestidos | vestidos e saias (o comando decide se é de cima ou de baixo) | `/skin vestir <id>` |
| Extras | qualquer peça a mais, junto com as outras (polainas com saia, cinto, adesivos); clicar veste ou tira | `/skin extra <id>` |
| Sapatos | os dois pés como um item | `/skin sapato <esquerdo,direito>` |
| Prontos | aparências prontas, voltar ao padrão, tirar roupas | `/skin preset`, `/skin reset`, `/skin tirar tudo` |

As roupas são os itens baixados em `assets/models/clothing`. A seção de cada um vem do tipo do asset do Roblox,
lido do item já encaixado em qualquer corpo; sem isso, do nome do arquivo. Um item novo baixado com
`/skin vestir <id>` aparece na próxima vez que a tela for aberta.

## 👁️ Olhos, maquiagem e pele

- **Uma cor para cada olho:** em Rosto, "Cor dos olhos" pinta os dois; "Olho direito" e "Olho esquerdo" (os do
  personagem) pintam um só (`/skin olho <direito|esquerdo> <cor>`, `customization.iris_color_other`).
- **Maquiagem** (`customization.makeup`): o batom recolore a boca mantendo o claro e o escuro do desenho; a sombra
  é uma mancha suave de cor sobre cada pálpebra, por baixo do desenho do olho. Blush e sardas são as camadas de
  detalhe do rosto que já existiam. Tudo é refeito na textura da cabeça, sem recarregar o personagem.
- **Vitiligo:** desenhado pelo shader (`world_textured.frag`, `u_Vitiligo`) sobre as partes de pele, a partir da
  posição no corpo sem pose: as manchas ficam presas à pele ao andar e são iguais dos dois lados. Só o que tem a
  cor da pele clareia, então olhos, boca e sobrancelhas da textura do rosto ficam como estão. "Quantidade" vai de
  0 a 100 (o lado negativo do controle não faz nada) e "desenho" troca o padrão das manchas.

## 🧦 Peças extras

`CharacterModel.extra_ids` é uma lista de peças vestidas junto com as outras, cada uma encaixada no corpo por si
(como os sapatos) e incluída no recorte da pele. Serve para o que não disputa espaço com as outras: polainas com
saia, cinto, adesivos, luvas. Duas peças que ocupam o mesmo lugar (duas calças inteiras) se atravessam: só a
jaqueta é encaixada por cima de outra roupa.

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
  ponte, altura da ponte (quanto ela sai do rosto), largura da ponta, largura da base (narinas e asas), altura da
  base (as asas ficam mais altas e o nariz começa a alargar mais acima) e posição das narinas (as asas sobem ou
  descem até 8 mm; só tem efeito nos formatos com asas).
- **Cor da ponta:** a cor dos vértices da ponta e das asas multiplica a textura (`nose.tip_colours`): positivo
  deixa mais rosada, 0 é a cor da pele, negativo escurece um pouco. A ponte fica sempre na cor da pele.
- O nariz pega a cor de um trecho da textura do rosto entre os olhos. O trecho do nariz antigo encostava na borda
  da boca e a base saía rosada; nos formatos gerados ele para antes (`nose.UV_SPAN`).
- **Sombra do nariz:** um trecho um pouco mais escuro pintado na textura do rosto, entre os olhos, como na textura
  antiga da cabeça. A malha do nariz usa esse pedaço da textura, então escurece junto. O controle vai de sem
  sombra (-100) ao dobro (+100), e a sombra acompanha o tamanho, a largura e a altura do nariz.
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
