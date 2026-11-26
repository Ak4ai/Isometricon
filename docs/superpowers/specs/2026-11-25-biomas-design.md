# Biomas: deserto e taiga — desenho

## Intenção

Hoje o gerador só faz planície (grama, capim, flores, água). Na apresentação da disciplina, quase todo slide mostra
a mesma planície. Queremos mais dois tipos de mundo, para variar os slides e para o jogo:

- **Deserto** no estilo do Minecraft;
- **Taiga** no estilo da floresta de pinheiros norte-americana, **sem neve**.

## Objetivos

- Na tela "Uma nova aventura", escolher o bioma do mundo: **Planície · Deserto · Taiga**.
- Cada bioma é reproduzível pela seed, como o terreno de hoje.
- A apresentação pode pôr um slide em outro bioma.

## Não-objetivos

- Vários biomas no mesmo mundo, com bordas entre eles (a opção A da conversa; ficou para depois).
- Neve, taiga nevada, aldeias, templos, poços do deserto.

## Anti-objetivos (falharia mesmo funcionando)

- Mundos já salvos mudarem de cara: sem a opção, o mundo é a planície de hoje, idêntica bloco a bloco.
- A apresentação travar visivelmente ao trocar de bioma (mais que uma pausa curta de carregamento).
- Commitar texturas da Mojang (`assets/textures/blocks/*`): elas já estão na pasta local e continuam fora do git.

## Abordagens consideradas

| | Como | Troca |
|---|---|---|
| A. Regiões num mundo | um segundo ruído largo divide o mapa em biomas, com transição | anda-se de um a outro; a apresentação não recarrega; borda entre biomas dá trabalho |
| **B. Um bioma por mundo** (escolhida) | opção na criação do mundo; o mundo inteiro é daquele tipo | simples e sem bordas; a apresentação recarrega o terreno ao trocar de bioma |

Escolhida pelo usuário: **B**.

## O que cada bioma tem (decidido na conversa)

### Planície
O de hoje, sem mudança.

### Deserto
- Topo de **areia**, 3 a 4 blocos de areia embaixo, depois **arenito**, depois pedra.
- Dunas: o mesmo ruído, com relevo um pouco mais alto e suave que a planície.
- **Cactos** de 1 a 3 blocos, raros; um cacto nunca encosta em outro (as 4 vizinhas na horizontal livres).
- **Arbustos secos** espalhados; sem capim nem flores.
- Pouca água: o padrão da barra "Água" no deserto fica perto de 5% (oásis raro); a barra continua valendo.

### Taiga (sem neve)
- Grama no topo com tom mais frio e escuro que a da planície; manchas de **podzol**.
- **Pinheiros**: tronco de pinheiro de 6 a 10 blocos e copa em cone de folhas de pinheiro. É o primeiro gerador de
  árvores do jogo; a mesma árvore sai sempre no mesmo lugar pela seed, inclusive quando a copa cruza a borda de um
  chunk.
- No chão: **samambaia**, **samambaia grande** e **arbusto de frutinhas**.

As opções de sempre (cavernas, planície, água, vegetação, tamanho do relevo) valem nos três biomas; "Vegetação"
escala também cactos, arbustos secos, pinheiros e samambaias.

### Na apresentação
- Cada slide pode dizer em que bioma passa (campo novo na cena do slide; vazio = planície).
- Proposta inicial: **Mundo: modelagem** no deserto, **Iluminação e sombras** na taiga, o resto na planície.
- Ao entrar num slide de outro bioma, o terreno é refeito com a mesma seed e o outro bioma (o mesmo caminho do `R`,
  nova seed, que já existe). Pausa curta enquanto os chunks carregam. Os lugares de teste (sala, caverna, vitrine)
  são postos depois do terreno carregado e somem ao trocar de bioma, como somem com o Esc.

## Restrições encontradas no código

- O gerador (`src/world/terrain.py`) é um campo de altura só, com camadas grama/terra/pedra/água e vegetação sorteada
  por coluna (`_plant_roll`). Não há árvores: `WOOD` e `LEAVES` existem mas nada as põe.
- Os blocos são um `IntEnum` de 17 tipos guardado em `uint8`. Blocos novos entram como tipos novos: areia, arenito,
  cacto, arbusto seco, tronco e folha de pinheiro, podzol, samambaia, samambaia grande, arbusto de frutinhas (e a
  grama da taiga, se o tom frio não sair de outro jeito).
- Os enfeites (`SHAPED_BLOCK_NAMES`) apontam para o nome do Minecraft e a forma sai de `block_shapes`; hoje todo
  bloco com forma é atravessável. **O cacto precisa ser sólido** mesmo tendo forma.
- Opacidade, sólido e "conta como teto" ficam em listas espalhadas (`block.py`, `mesher.py`, `room_reveal.py`):
  cada bloco novo precisa entrar nelas.
- A textura de cada tipo sai de `src/rendering/atlas.py` (com tinta para grama e folhas).
- As opções da criação (`src/world/terrain_options.py`) são porcentagens 0–100; o bioma é uma escolha, não uma
  porcentagem. Mundos sem a chave continuam planície.
- A prévia da tela de criação (`src/interactive/world_preview.py`) deve mostrar o bioma escolhido.

## Decisões tomadas por mim (para conferir)

- O bioma é salvo junto das opções do mundo, como `world["terrain"]["bioma"]` = `"planicie"`, `"deserto"` ou
  `"taiga"`; sem a chave, planície.
- Ao escolher Deserto na tela de criação, a barra "Água" vai para 5%. Ao voltar para Planície ou Taiga, volta para 20%,
  o padrão. Quem mexer na barra depois manda.
- O cacto não machuca nem quebra: é só um bloco sólido com forma.
- `--apresentacao` continua com a seed fixa; o bioma de cada slide vem do slide, não da linha de comando.

## O que fica com quem constrói

- O tom exato da grama da taiga e das folhas de pinheiro (tinta no atlas ou tipo próprio).
- As densidades exatas (cactos, arbustos, pinheiros, samambaias) dentro do que está acima.
- A forma exata da copa do pinheiro, desde que leia como cone em vista isométrica.
- Quanto mais alto e suave é o relevo das dunas.
- Como a tela de criação mostra a escolha (três botões, como os de "Névoa de guerra" do /mestre, é um bom padrão).
