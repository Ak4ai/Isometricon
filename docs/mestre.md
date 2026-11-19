# Mestre: ambientação (`/mestre`)

`/mestre` abre (ou fecha) um painel de pergaminho à esquerda da tela, no estilo das telas de entrada e de combate,
para o mestre ambientar a cena. Tudo muda na hora, enquanto se arrasta, e fica salvo no mundo (`world["ambiente"]`).
Esc ou o X fecha; o chat passa para a direita do painel enquanto ele está aberto.

| Opção | O que faz |
| --- | --- |
| Hora do dia | Move o sol, e com ele as sombras: neutro de dia, dourado perto do horizonte, azul e escuro à noite (a luz vem da lua). A trilha mostra o céu do dia. |
| Relógio | Parado, 1×, 10× ou 60× (minutos de jogo por segundo): a hora anda sozinha. |
| Claridade | 0 a 200% da luz. |
| Cor da luz | Fria a quente. |
| Névoa | Engole o que está longe do jogador, na cor da hora. |
| Cores | A saturação, de cinza a 200%. |
| Luz do grupo | Uma luz quente em volta do personagem (uma tocha), que não escurece com a noite. |
| Névoa de guerra | Sem; Revela (andando, a névoa se abre em volta do personagem e o explorado fica limpo, guardado no mundo); Em volta (limpo só perto dele: fecha atrás). Recobrir cobre de novo o explorado. |
| Cenas prontas | Amanhecer, Meio-dia, Entardecer, Noite, Tempestade, Sombrio, Névoa densa (cinza claro, vê-se só perto) e Pesadelo (névoa escura à noite, com a luz do grupo). |

Pelo chat: `/mestre hora 18:30`, `/mestre cena noite`, `/mestre guerra revela|volta|sem`, `/mestre recobrir`, `/mestre padrao`, `/mestre fechar`.

A névoa é densa e viva: rente ao chão (os vales enchem primeiro), com tufos que derivam com o tempo e grão de filme quando é muita; as linhas do contorno do relevo somem nela. Na superfície, a névoa de guerra é uma manta de nuvens de blocos, como as do Minecraft (`src/rendering/cloud_fog.py`): caixas brancas de 2 x 2 blocos, de topo chato e lados sombreados, deitadas rente ao relevo; na luz da hora (douradas no entardecer, escuras à noite). Elas são translúcidas, com um gradiente de opacidade: ralas na beira do que já foi visto (dá para ver o relevo e quem está debaixo) e densas a algumas células para dentro, pelo campo de distância até o aberto, uma textura pequena refeita só quando a manta muda. O shader dá volume: os lados escurecem para baixo e o topo tem tufos claros e escuros que derivam devagar. Para não ficar em degraus, a manta desenha primeiro só a profundidade e depois a cor, misturada uma vez só na face da frente, por último na cena. Onde o grupo olha, as células se desfazem em tufos (menos de um segundo); no modo Em volta, voltam a se formar atrás dele. Logo abaixo dos modos, "Blocos" / "Plana" / "Fofas" (`/mestre estilo nuvens|nevoa|fofas`) escolhe o jeito da névoa de guerra: as nuvens de blocos, a névoa plana de antes, a do shader (a mesma das cavernas), que cobre o chão com a borda de tufos, ou as nuvens fofas: cada célula vira uma caixa quadrada de quinas e vértices redondos, como blocos de nuvem soltos (o shader acha a superfície redonda andando o raio da câmera dentro da caixa da malha), emendadas nas vizinhas da mesma altura numa nuvem só, ralas perto do aberto e opacas para dentro (o mesmo gradiente das de blocos), com uma luz lisa: o topo claro, o lado de baixo azulado como o céu, o sol que dá a volta e uma sombra no vão entre as caixas. Ao se desfazer, cada célula se parte em quatro tufos que, cada um no seu tempo, incham, encolhem e sobem girando e sumindo; ao voltar, os tufos descem do alto e assentam com um quique. A "Altura da névoa" (0 a 16 blocos acima do relevo; padrão 2, ou `/mestre altura <n>`) diz até onde as nuvens sobem, e "Cobrir objetos" / "Mostrar acima" (`/mestre objetos cobrir|mostrar`) diz se elas sobem também por cima das construções (pela caixa de cada uma) ou se o que é mais alto que a névoa aparece por cima dela. Mais alta que a padrão, a névoa desce como uma pia: na beira do que já foi visto fica na altura padrão (de perto não atrapalha a vista) e sobe em degraus para longe, até a altura escolhida a umas 6 células da beira. Numa caverna, a manta sai e fica a névoa do shader, com a mesma borda de tufos (`src/rendering/fog_of_war.py`). Numa janela baixa, o painel encolhe para caber.

Nos padrões nada muda: a hora padrão (16:30) dá exatamente o sol de sempre do terreno e o tom é branco.

Código: `src/rendering/ambience.py` (a conta da luz), `src/interactive/master_panel.py` (o painel) e `envGrade` no
fim de `assets/shaders/world_textured.frag` (tom, saturação, luz do grupo e névoa). A tela de criação do personagem
fica sem a ambientação.
