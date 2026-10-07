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
| Corpo | feminino/masculino, tom de pele, formato da cabeça | `/skin corpo`, `/skin pele`, `/skin cabeca` |
| Ajustes | altura, cabeça, ombros, peito, quadril, bunda, braços, mãos, pernas, pés | `/skin ajuste <nome> <-100 a 100>` |
| Rosto | estilo e cor dos olhos, boca, sobrancelhas; tamanho, altura e distância dos olhos, altura das sobrancelhas | `/skin olhos`, `/skin boca`, `/skin sobrancelha`, `/skin ajuste` |
| Cabelo | padrão, raspado, careca; cor; cabelos do Roblox baixados | `/skin cabelo` |
| Superior | camisetas, camisas e suéteres | `/skin top <id>` |
| Jaqueta | peça por cima da roupa | `/skin jaqueta <id>` |
| Inferior | calças e shorts | `/skin calca <id>` |
| Vestidos | vestidos e saias (o comando decide se é de cima ou de baixo) | `/skin vestir <id>` |
| Sapatos | os dois pés como um item | `/skin sapato <esquerdo,direito>` |
| Prontos | aparências prontas, voltar ao padrão, tirar roupas | `/skin preset`, `/skin reset`, `/skin tirar tudo` |

As roupas são os itens baixados em `assets/models/clothing`. A seção de cada um vem do tipo do asset do Roblox,
lido do item já encaixado em qualquer corpo; sem isso, do nome do arquivo. Um item novo baixado com
`/skin vestir <id>` aparece na próxima vez que a tela for aberta.

## 📐 Ajustes de proporção

Cada ajuste vai de -100 a 100 (0 = o corpo como foi modelado) e fica em `AvatarCustomization.body_adjust`, gravado
com o personagem. Nenhum mexe só no corpo ou só na roupa, o que desfaria o encaixe: todos agem igual sobre pele,
roupa e cabelo (`src/clothing/body_shape.py`).

- **Altura, cabeça, ombros, quadril, braços, pernas, mãos e pés** são escalas por osso, aplicadas com o esqueleto
  (`Skeleton.pose(..., scales, height)`): o que o osso carrega cresce junto e os ossos filhos acompanham sem crescer.
  Braços e pernas engrossam sem mudar de comprimento; os pés crescem sem afundar no chão.
- **Peito e bunda** não têm osso: são uma deformação do espaço na pose de vestir (`warp`). A pele e o tecido que
  está sobre o mesmo ponto se movem exatamente o mesmo tanto.
- **Olhos e sobrancelhas** agem na textura da cabeça: a camada é escalada, erguida ou afastada antes de ser colada
  (`customization.place_face_layer`). Na tela, esses só são aplicados ao soltar o controle, porque a textura é refeita.
- Com tudo em 0, nada muda em relação ao personagem sem ajustes. A bateria de robustez não mede os ajustes; os
  extremos foram conferidos por imagem com roupa justa (regata e meia-calça), parado e andando.

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
