# Árvores altas da taiga (pinheiros grandes e sequoias) — desenho

## Por quê
Os pinheiros da taiga (tronco 1x1, 6 a 10 blocos, cone de raio 3) parecem árvores de Natal pequenas. O pedido: árvores
com cara de sequoia, bem maiores, pinheiros mais altos e mais bonitos.

## O que muda
- **Dois tipos misturados.** A maioria são **pinheiros altos** (14 a 20 blocos, tronco 1x1, ou 2x2 nos mais altos); mais
  raro, uma **sequoia gigante** (26 a 36 blocos, tronco 2x2 ou 3x3, com a base alargada em raízes de 1 bloco).
- **Tronco nu na metade de baixo**, copa só no alto, em **andares irregulares**: galhos curtos saindo do tronco em
  direções sorteadas pela seed, mais largos embaixo, afinando até a ponta. Nada de cone perfeito.
- **Casca avermelhada nas sequoias**: bloco novo `SEQUOIA_LOG` (textura de tronco de mangue/acácia, ou a do pinheiro
  tingida), opaco como os outros troncos.
- **Células maiores** (11x11) para as copas não se embolarem; a margem de busca segue o maior raio de copa, e um chunk
  gerado sozinho continua igual ao gerado junto dos vizinhos.

## Restrição encontrada
O mundo só gerava a camada de chunks y=0 (blocos 0–15, chão perto de 8): as pontas já eram cortadas. **Na taiga, cada
coluna passa a gerar as camadas 0, 1 e 2** (até y=47). O `WorldManager` já descarrega por coluna; ele só passa a pedir
as camadas que o gerador diz que a coluna tem (`column_layers`). Os outros biomas continuam com uma camada.

## Visão do personagem
As folhas já somem no círculo (`leafHole`). O tronco é sólido e já conta para o corredor da câmera (`sight_cover`): se
um tronco tapar o personagem, o corredor abre. Nada novo aqui (decisão minha, no lugar de pôr o tronco no círculo).

## Abordagens consideradas
- **Gerar mais camadas por coluna na taiga (escolhida):** árvores no tamanho pedido; custo de mais chunks (quase todos
  ar) para malhar e desenhar — medir o fps na tomada.
- Baixar o chão da taiga e ficar numa camada: no máximo ~13 blocos de árvore. Não é sequoia.
- Desenhar as árvores como modelos fora da grade de voxels: perde sombra, colisão e o corte da câmera que já existem.

## Fica com quem implementa
Números finos (densidade, raio de cada andar, chance de sequoia), a textura exata da casca.
