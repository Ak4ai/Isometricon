# Combate por turnos

Portado do mod RPG (Fabric, Minecraft 1.20.1) e aprimorado. A regra fica em `src/combat/` (pura, sem OpenGL, testada em
`tests/test_combat_*.py`); o jogo liga a regra ao mundo em `src/interactive/combat_controller.py`, desenha a tela em
`combat_hud.py` e as miniaturas em `enemy_tokens.py`.

## Como jogar

| | |
|---|---|
| `/inimigo <tipo> [n]` | põe `n` criaturas (1 a 8) a 5 blocos do personagem: zumbi, esqueleto, aranha, slime, bandido, ogro |
| `/inimigo lista` / `limpar` | lista os tipos / tira todos |
| `/ficha` | atributos, vida, CA, arma, armadura e itens |
| `/atributo for 16`, `arma espada`, `armadura ferro`, `nivel 3` | muda a ficha (fora do combate) |
| clicar num inimigo | a até 6 blocos começa a luta **de surpresa** (vale o Ataque Furtivo); na luta, mira; clicar no alvo ataca |
| chegar perto | um inimigo que te vê a até 6 blocos começa a luta |
| WASD | anda só o movimento da vez (anel azul); o anel vermelho é o alcance da arma |
| 1 a 6 | Atacar, Habilidades, Itens, Defender, Disparada, Fugir (0 volta do submenu) |
| Tab / Enter | troca o alvo / encerra a vez |

A ficha do personagem (atributos, nível, arma, armadura, itens e vida) é salva com o mundo. Fora do combate a vida
volta 1 ponto a cada 3 segundos.

## Regras

- **Iniciativa:** d20 + DES. Empata quem tem mais DES, depois o personagem. Quem chega perto no meio da luta (até 15
  blocos) entra no começo de uma rodada, na sua iniciativa.
- **A vez:** uma ação e o movimento (8 blocos; aranha 10, zumbi 6...), em qualquer ordem. Acaba quando os dois
  acabam, ou com Enter. No começo da vez a postura defensiva cai, os efeitos agem e perdem uma rodada, e as recargas
  andam.
- **Acerto:** d20 + atributo (FOR; DES com arco, ou adaga quando a DES é maior) + proficiência (+2) contra a CA. 1
  natural sempre erra; 20 natural sempre acerta e dobra os **dados** de dano (não o bônus).
- **Dano:** dados da arma + atributo + Força/Fraqueza, no mínimo 1; a armadura do alvo reduz (curva armadura/dureza,
  até 82%) e a vida temporária é gasta antes da vida.
- **CA:** sem armadura 10 + DES; leve 11 + DES + armadura/2; média 11 + min(1, DES) + armadura/2; pesada
  10 + armadura/3 + dureza/10. A DES na CA tem teto de +6; conjunto misto: -1 CA e -5% de redução. Defender: +5 CA até
  a próxima vez.
- **Habilidades:** Golpe Pesado (-2 no acerto, dados da arma x2); Ataque Furtivo (só de surpresa ou com o alvo
  atordoado: vantagem e +2d6); Escudo Divino (5 + SAB de vida temporária que não soma, e +5 CA; recarga de 3 rodadas);
  Foco Espiritual (1d10 + nível de vida, uma vez por combate).
- **Itens** (até o inventário existir, um kit fixo): Poção de cura 2d4+2; Poção de regeneração (2 por rodada, 4
  rodadas).
- **Efeitos:** regeneração, veneno (não derruba: deixa com 1), força, fraqueza, atordoado (perde a vez), abençoado.
- **Disparada:** a ação vira mais um movimento inteiro.
- **Fugir:** sem inimigo corpo a corpo por perto sai na hora; senão d20 + DES contra CD 10 + 3 por inimigo que te
  alcança. Terminar a vez a mais de 16 blocos de todos os inimigos também é fugir.
- **Fim:** vitória quando não sobra inimigo de pé (os que fogem saem do combate); derrota quando a vida chega a 0 — o
  personagem acorda com 1 de vida e os inimigos vão embora; fugindo, eles ficam, mas não perseguem por 8 segundos.

## Inimigos (IA)

A IA pesa a situação em vez de sortear: escolhe o alvo mais perto e mais fraco; corpo a corpo anda até o alvo e ataca,
e se não chega nesta vez dispara; o arqueiro recua quando o alvo encosta (a menos de 3 blocos) e chega só até poder
atirar; ferido e ameaçado, o `agressivo` tende a defender e o `covarde` (aranha, bandido) foge e sai do combate; o
Golpe Pesado entra quando o acerto é fácil. A aranha envenena; o ogro é um chefe.

## O que mudou em relação ao mod

- Lutar, Golpe Pesado e Ataque Furtivo usam uma só resolução de golpe (no mod eram três cópias; o Golpe Pesado
  ignorava o arco).
- O movimento é contado pela regra (no mod só o cliente contava).
- O Ataque Furtivo depende de surpresa de verdade (no mod, de estar agachado na hora da ação).
- Escudo Divino não empilha e tem recarga (no mod dava +5 de vida temporária e +5 CA a cada vez, sem limite).
- Fugir depende da DES e de quantos inimigos te alcançam (no mod era 50% fixo); afastar-se também foge.
- Os inimigos têm ficha própria (no mod o acerto era metade do dano do mob) e IA por situação (no mod, 70/30).
- Os dados aceitam semente: o mesmo combate se repete igual (testes e replays).
- O registro explica cada rolagem (a dica que o mod mostrava ao passar o mouse vira a linha de baixo do registro).

## Para depois

Inventário de verdade (armas, armaduras e consumíveis como itens), tela de ficha do personagem, inimigos que aparecem
sozinhos no mundo, experiência e níveis por vitória, e caminhos que contornam paredes (hoje o inimigo anda em linha
reta e para onde não dá para subir).
