# Neblina de ambientação no /mestre — desenho

## Por quê
O mestre quer uma neblina de cena, de filme, separada da névoa de guerra e da névoa de distância que já existe: a
neblina baixa que se junta na beira da água e entre as árvores, e também um "dia neblinoso" mais geral, com o mestre
decidindo quanto do mapa ela cobre e até que altura sobe. O `/mestre` ficou comprido demais e passa a ter abas.

## O painel em abas
Abas no topo do pergaminho; cada uma mostra só o seu conteúdo (o pergaminho fica mais curto):
- **Luz** — hora e relógio, claridade, cor da luz, cores, luz do grupo.
- **Neblina** — a seção nova (abaixo) e, embaixo dela, a névoa de distância de hoje (renomeada "Névoa de distância").
- **Guerra** — a névoa de guerra (modo, recobrir, estilo, altura, objetos).
- **Cenas** — as cenas prontas e "Restaurar o padrão".
A aba aberta não vai para o save.

## A seção Neblina
- **Neblina** (0 a 100): o quanto ela é grossa. 0 desliga.
- **Cobertura** (0 a 100%): quanto do mapa tem neblina. Um ruído largo e lento divide o mapa em manchas; a cobertura
  escolhe o limiar, para que ~N% do chão fique dentro delas. 100% = o mundo inteiro.
- **Altura** (1 a 40 blocos): até quantos blocos acima do chão ela sobe; mais grossa rente ao chão, rareando até a
  altura. As copas altas furam a neblina baixa.
- **Onde**: *Em toda parte* ou *Água e árvores* — no segundo, a neblina só se junta perto da água e entre as árvores
  (a cobertura vale dentro dessas áreas).
- **Vento** (0 a 100): a velocidade com que os tufos derivam.
- **Tom**: fria, neutra, quente (chips) — a cor da neblina; ela também segue a luz do dia (escura à noite).
- **Presets da neblina** (chips): *Beira d'água* (água e árvores, baixa e grossa), *Manhã neblinosa* (toda parte, 70%,
  média), *Vale* (toda parte, só nos baixios), *Bruma alta* (toda parte, 100%, alta e rala).

As cenas prontas (aba Cenas) também passam a mexer na neblina: Amanhecer e Sombrio ganham neblina baixa.

## Como é desenhada (abordagem escolhida: camada no shader)
No `world_textured.frag`, como as outras névoas: integra a densidade da neblina no caminho da câmera até o ponto
desenhado. A densidade vem da altura acima do chão local (mais grossa embaixo), do ruído de tufos que deriva com o
vento, das manchas da cobertura e, no modo *Água e árvores*, de um mapa 2D em volta do jogador (como o da névoa de
guerra): 1 perto da água ou entre troncos, caindo para 0 longe. O mapa e a altura do chão por coluna saem dos chunks
carregados, numa textura recentrada quando o jogador anda longe.

Outras abordagens consideradas: folhas de névoa soltas no mundo (passariam na frente dos troncos; mais caras, ficam
para depois se faltar esse efeito) e névoa volumétrica num passe de tela (bonita, pesada demais para o notebook).

## Fica com quem implementa
Os números finos dos presets e da densidade; o raio do "perto da água/árvores"; o tamanho da textura do mapa.
Medir o fps na tomada.
