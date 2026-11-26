# Modo apresentação (`--apresentacao`) — desenho

## Intenção

Apresentar o Isometricon na disciplina de Computação Gráfica (CEFET-MG Divinópolis, 2026) com o próprio jogo
rodando ao fundo: os textos do slide em LaTeX/Beamer viram cartões desenhados por cima da cena, avançando com o
teclado, e a cena muda para ilustrar cada slide (wireframe no face culling, zoom na câmera ortográfica etc.).

## Metas

- `python src/main.py --terrain --apresentacao` abre o terreno com o slide 1 por cima.
- Avança/volta slide a slide; a cena de fundo de cada slide é real (o mundo carregado, a câmera e o GL de verdade).
- Contagens mostradas (faces, chunks) vêm do mundo carregado, não são números fixos.
- Texto dos 13 slides mantido, com os acentos revisados e as fórmulas preservadas.

## Fora do escopo

- Exportar para PDF/PPTX, notas do apresentador, segunda tela.
- Mudar o comportamento do jogo fora do modo apresentação.

## O que faria isto falhar mesmo funcionando

- Quebrar o jogo normal (sem a flag nada muda; a suíte de ~1500 testes continua verde).
- Texto ilegível sobre o terreno, ou fórmulas com quadradinhos no lugar de Σ, ⊙, λ.
- Afirmações nos slides que o código atual desmente.

## Abordagens consideradas

- **A. Modo dentro do jogo (escolhida).** Cartões com `HudQuad` sobre a cena; lógica num módulo puro testável.
  Troca: mexe no `main.py` (grande) e as fórmulas não têm a cara do LaTeX.
- B. HTML (reveal.js) com vídeos gravados do jogo: fórmulas bonitas, mas o jogo não roda de verdade.
- C. Janela transparente sobreposta ao jogo: frágil no Windows; descartada.

## Como fica

### Peças

- `src/interactive/presentation_slides.py` — dados puros: lista de `Slide(titulo, blocos, cena)`. Blocos são
  parágrafos, tópicos, fórmulas, diagrama de pipeline (caixas com setas), prompts de IA. `cena` é um
  `SceneCue` imutável: giro (graus/s), zoom (alvo e oscilação de `ortho_size`), perspectiva, wireframe,
  modo de visualização do shader (normal / só textura / só luz), contorno de chunk, contadores a mostrar,
  passos internos (o pipeline acende uma caixa por toque).
- `src/interactive/presentation.py` — `Presentation`: índice, passo interno, `next/prev/first/last`, `toggle_card`,
  `key(key, action) -> bool` (consome a tecla), `update(dt)` com o relógio da cena do slide e
  `camera_targets(t)` que devolve yaw/ortho_size/perspectiva desejados (função pura do tempo). Sem GL.
- `src/interactive/presentation_card.py` — monta a imagem PIL do cartão no estilo pergaminho de `menu_style`:
  títulos com a fonte do Minecraft (`mc_font`), corpo e fórmulas numa TTF com Unicode (Cambria/Segoe UI do
  Windows, com queda para a fonte padrão do Pillow). Também o mapa de altura do slide 6, gerado pelo
  `TerrainGenerator.heights` com 1, 2 e 3 oitavas. Cache da imagem por (slide, passo, tamanho da janela).
  Testável sem GL (gera `Image`).
- `src/main.py` — lê a flag; cria a apresentação; registra as teclas antes das do jogo (as consumidas não chegam
  ao jogo); a cada quadro aplica `camera_targets` com suavização, `glPolygonMode(GL_LINE)` no wireframe, o
  uniform do modo de visualização e desenha o cartão + rodapé ("7/13", contadores) com `HudQuad` depois da cena.
  O HUD normal do jogo (FPS, coordenadas, barra) fica escondido no modo.
- `world_textured.frag` — um `uniform int u_DebugView` (0 normal, 1 só textura, 2 só iluminação), padrão 0.
- `WorldManager` — expor contagem de chunks desenhados no último quadro e soma de faces das malhas carregadas
  (`ChunkMeshData.face_count`) e de voxels sólidos, se ainda não houver.

### Teclas

→ / espaço / PageDown: próximo (ou próximo passo interno). ← / PageUp: anterior. Home / End: primeiro / último.
H: esconde/mostra o cartão. Esc: sai do modo (o jogo segue normal).

### Slides e cenas

| # | Slide | Cena de fundo |
|---|-------|---------------|
| 1 | Capa: "Isometricon: do voxel à imagem na tela" / "Modelagem 3D, câmera virtual e pipeline gráfico", autores, CEFET-MG Divinópolis 2026 | giro lento, cartão central |
| 2 | O que vamos demonstrar (+ pergunta central, recorte) | zoom out devagar |
| 3 | Ferramentas | câmera girando devagar |
| 4 | Pipeline CPU → GPU | caixas acendem uma por toque |
| 5 | Voxel e chunk (16×16×16, uint8, 4096 B; tipos) | contorno do chunk sob o foco |
| 6 | Geração procedural (Value Noise, fade quíntica, fórmula N) | mapa de altura 1/2/3 oitavas no cartão |
| 7 | Face culling na CPU | wireframe + "faces desenhadas: X de 6 × N voxels" |
| 8 | Da malha aos shaders (11 floats = 44 B; fórmula de luz) | alterna só textura / só luz / normal a cada ~3 s |
| 9 | Câmera (P·V·M, TRS, look-at, yaw 45°, pitch 35,264°) | yaw em passos de 45°, `ortho_size` oscilando, ortográfica ↔ perspectiva |
| 10 | Outras otimizações | zoom out + "chunks desenhados: X de Y" |
| 11 | IA como apoio (dois prompts) | giro lento |
| 12 | Conclusão | giro lento |
| 13 | Fontes (links Ak4ai/Isometricon) + "Obrigado!" | zoom out final |

### Ajustes de conteúdo pelo código atual

- Slide 5: os 7 tipos do texto original continuam; uma linha a mais: "hoje são 18, com plantas, tocha, escadas e
  fogo, que têm forma própria".
- Slide 7: "só DIRT, GRASS, STONE e WOOD ocultam; água, folhas e blocos com forma não".
- Slide 8: Half-Lambert ao quadrado; linha a mais citando sombras do sol por raio e oclusão de ambiente por vértice.
- Slide 9: menção ao modo perspectiva opcional.

## Verificação

- Testes (pytest) de `presentation.py` (navegação, passos, limites, teclas consumidas, alvos de câmera),
  `presentation_slides.py` (13 slides, textos com acento, fórmulas presentes) e `presentation_card.py`
  (imagem com o tamanho certo, sem erro com e sem as TTF do Windows, mapa de altura).
- Rodar o jogo com a flag, percorrer os 13 slides e capturar telas (o `--screenshot`/`--frames` já existentes ou
  `glReadPixels`) para conferir.

## Deixado para quem constrói

Cores e medidas do cartão, posição por slide (central na capa, à direita nos demais), suavização da câmera,
velocidade dos giros, como desenhar o contorno do chunk (linhas com o shader de highlight ou equivalente).
