# Construções unificadas: o motor do `/schem` com os controles do Rafael

Data: 2026-11-17 · Estado: proposta, aguardando aprovação

## Por quê

Hoje o jogo tem dois jeitos de pôr uma construção no terreno, que não se falam:

- **`/schem`** (`src/interactive/schematic_tool.py` + `src/world/structure_layer.py`): lê `.schem` do Minecraft e
  sabe tudo do motor — texturas reais, formas (escada, laje…), portas que abrem, baús com tampa, escada de mão, corte
  do terreno na caixa da construção, revelação de cômodo. Mas o controle é ruim (setas, ou coordenadas pelo chat), só
  remove a última, não gira e **não salva**: tudo some ao fechar o jogo.
- **Objetos no mundo do Rafael** (`src/editor/world_objects.py`): JSON próprio feito no `--map-editor`. O controle é
  bom — clicar no chão com o mouse, girar, selecionar, remover qualquer um, dar nome, salvar por seed — e o painel
  fica sempre na tela. Mas cada voxel vira um cubo de pedra (sem porta, baú, forma, água) e o terreno não é cortado.

O usuário quer **um jeito só**, com a interação do Rafael, e o painel **escondido até rodar `/schem`**.
Escolhido o caminho A: o motor do `/schem` fica por baixo e ganha os controles e o painel do Rafael.

## Metas

1. Um único sistema de construções no `--terrain`: uma lista de construções colocadas, um desenho, uma colisão.
2. `/schem` sozinho abre o painel (o do Rafael, que hoje fica sempre visível); fechar o painel o esconde.
3. Com o painel aberto:
   - escolher a construção numa lista que mistura os `.schem` de `assets/schematics` e os objetos JSON do Rafael
     (`assets/objects`, `saves/objeto.json`), mais a vitrine `formas`;
   - **colocar com o mouse**: o holograma segue o cursor sobre o topo do terreno, verde se cabe, vermelho se não;
     clique fixa;
   - as setas e Shift+↑/↓ continuam ajustando o holograma bloco a bloco (o que existe hoje);
   - **girar** 90° (R), também a construção selecionada;
   - **selecionar** (V ou clique) e **remover qualquer uma** (Del), não só a última;
   - **nome** (N), como no Rafael.
4. **Salvar**: as construções colocadas voltam ao abrir o mundo de novo, com portas abertas/fechadas como ficaram.
5. Os objetos do Rafael ganham tudo do motor (cômodo, tampas, corte do terreno) por virarem construções.
6. Os subcomandos do chat continuam (`/schem load <nome> [x y z]`, `place`, `cancel`, `remove`, `clear`, `list`,
   `info`) como atalhos — os testes e as medições usam `--cmd "/schem load … ; /schem place"`.

## Fora do escopo

- O `--map-editor` do Rafael (onde os objetos são criados) não muda. Ele continua salvando o JSON dele.
- Inventário do baú, edição de blocos dentro da construção, desfazer/refazer no jogo.
- Miniaturas na lista (o painel continua textual, como o do Rafael).

## O que não pode acontecer (anti-metas)

- Uma porta, escada, baú ou trilho girado ficar voltado para o lado errado.
- Perder o que o `/schem` já faz bem (portas, baús, cômodos, corte do terreno, desempenho — a casa grande não pode
  voltar a custar quase 1 s por mudança de porta).
- Perder objetos que o usuário já colocou: o `saves/mundos/mundo_<seed>.json` do Rafael é lido e convertido.
- Painel aparecendo sem o `/schem`, ou roubando teclas (P, V, R, N, F3…) do jogo quando fechado.

## Como fica

### Um modelo só

`PlacedStructure` (`structure_layer.py`) passa a ser a única construção colocada. Ganha:

- `rotation` (0–3) e `source` (de onde veio: `schem:<nome>`, `object:<caminho>` ou `formas`), para salvar e recarregar;
- a grade já girada é a que vai para colisão, cômodo, portas e baús (nada abaixo precisa saber de rotação).

Um objeto JSON do Rafael vira `Schematic` pela ponte que já existe (`src/editor/room_structures.py`,
`object_structure`), mas agora **também para desenhar e colidir**, não só para o cômodo. As cores dele vão em
`schematic.tints`, que as tampas já leem; o desenho do corpo precisa ler os tints também (hoje só as tampas leem).

### Girar uma construção `.schem`

Girar a grade (como `VoxelObject.rotated_y`) e, em cada nome de bloco, girar as propriedades com direção:

- `facing` (north→east→south→west), `axis` (x↔z), `rotation` de placas/cabeças (0–15, +4 por volta);
- conexões de cerca/painel/muro (`north=true` … giram juntas);
- `shape` de trilho (`north_south`↔`east_west`, curvas e rampas giram).

`hinge`, `half`, `type=left/right` (baú duplo) são relativos ao `facing` e não mudam. Uma função pura
`rotate_block_name(name, turns)` com teste por família de bloco.

### Colocar com o mouse

O raio do mouse (`screen_to_world_ray` + `raycast_voxels`, como no Rafael) acha o topo de um bloco; o canto da
construção vai para que o centro da base fique no bloco apontado. Cabe se: não sobrepõe outra construção nem o
jogador, e não cai dentro d'água. **Terreno não impede**: como hoje no `/schem`, o terreno da caixa vira ar ao fixar.

### Painel

O `WorldObjectHud` do Rafael (canto superior direito) vira o painel das construções: modo, construção escolhida,
contagem, selecionada, cursor, nome, status e os botões Colocar / Selecionar / Construção / Girar / Remover / Sair.
"Construção" abre a lista (↑/↓ escolhe, Enter pega). Fechado, não desenha nem consome teclas ou cliques.

- `/schem` (sem nada): abre o painel em modo Colocar.
- `/schem load <nome>`: abre o painel já com essa construção no holograma.
- Esc ou "Sair": fecha o painel (cancela o holograma, mantém o que já foi fixado).

### Salvar

- Mundo aberto pelo menu: as construções vão no save do mundo (`WorldLibrary`, ao lado de `position` e `character`).
- `--terrain` direto, sem mundo: no arquivo por seed do Rafael (`saves/mundos/mundo_<seed>.json`), em formato novo.
- Cada entrada guarda `source`, `origin`, `rotation`, `name` e as portas abertas. Ao carregar, a grade vem de novo do
  arquivo de origem; se o arquivo sumiu, a construção é pulada com um aviso no chat (não quebra o mundo).
- O formato antigo do Rafael (só objetos) é lido e convertido na primeira vez.
- Salva ao fixar, remover, girar ou abrir/fechar porta (como o Rafael já faz ao colocar).

### O que sai

`WorldObjectEditor`, `WorldObjectRenderer`, `WorldObjectProvider`/`WorldTokenProvider` (a colisão "tudo é pedra") e o
`ObjectStructureCache` deixam de ser usados no jogo; o que for só do jogo é apagado, com os testes deles reescritos para
o sistema novo. O `--map-editor` continua com as peças que ele usa (`VoxelObject`, `object_mesher`, `material_atlas`).

## Caminhos considerados

| | Como | Troca |
|---|---|---|
| **A (escolhido)** | Motor do `/schem` + controles e painel do Rafael | Um sistema; tudo que o motor sabe vale para os objetos do Rafael. Girar `.schem` exige girar os estados dos blocos. |
| B | Motor do Rafael aprendendo `.schem` | Reescrever portas, baús, formas e corte do terreno dentro do formato do Rafael. |
| C | Só esconder o painel do Rafael | Rápido, mas continuam dois sistemas. |

## Decisões tomadas por mim (corrija se não for isso)

1. Girar `.schem` entra agora, com os estados dos blocos girando junto.
2. Terreno não impede colocar: o terreno da caixa é cortado, como no `/schem` hoje. (No Rafael o objeto aceitava e
   ficava enterrado no morro; o corte resolve isso.)
3. Salvar no save do mundo quando houver; senão no arquivo por seed.
4. Os subcomandos do chat continuam como atalhos.
5. Teclas do painel iguais às do Rafael (P, V, R, N, F3/lista, Del, Esc), ativas só com o painel aberto.

## Para quem construir

- Risco: os objetos do Rafael passam a ser desenhados com o atlas das construções (texturas do Minecraft), não com o
  atlas 4×4 do editor. O nome da textura de cada material (`white_concrete`, …) já é um nome do Minecraft; conferir lado
  a lado no jogo que um objeto conhecido (`assets/objects/casa_exemplo.json`) fica igual. Se uma textura do editor não
  existir no atlas, cair na cor pura do material.
- A malha das construções (`structure_mesher.py`) ainda não lê `schematic.tints`; só as tampas leem
  (`room_caps.py`). Passar a cor por vértice do mesmo jeito.

- A ordem de desenho e as passadas de profundidade de `main.py` (`draw_solids`) já tratam as construções; os objetos
  passam a entrar por ali e o desenho separado deles sai.
- Medir antes e depois com a casa grande e com vários objetos (na tomada): sem regressão de fps.
- Testes: girar nomes de bloco por família; colocar/selecionar/remover/girar sem OpenGL; salvar e recarregar (inclusive
  arquivo de origem sumido e formato antigo do Rafael); painel fechado não consome teclas.
