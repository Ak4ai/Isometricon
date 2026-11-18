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
| Cenas prontas | Amanhecer, Meio-dia, Entardecer, Noite, Tempestade e Sombrio. |

Pelo chat: `/mestre hora 18:30`, `/mestre cena noite`, `/mestre padrao`, `/mestre fechar`.

Nos padrões nada muda: a hora padrão (16:30) dá exatamente o sol de sempre do terreno e o tom é branco.

Código: `src/rendering/ambience.py` (a conta da luz), `src/interactive/master_panel.py` (o painel) e `envGrade` no
fim de `assets/shaders/world_textured.frag` (tom, saturação, luz do grupo e névoa). A tela de criação do personagem
fica sem a ambientação.
