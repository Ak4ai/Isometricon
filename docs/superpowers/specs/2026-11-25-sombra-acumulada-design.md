# Sombra acumulada entre quadros

## Por quê
Na taiga, com as copas altas, quase todo pixel fica na penumbra e traça os 18 raios do sol a cada quadro (~230 milhões
de passos). A RTX 3050 passa 24 ms nisso e rende igual à Intel: o trabalho é ler textura e esperar, raio a raio.
O mundo e o sol quase não mudam de um quadro para o outro, então a sombra de um ponto do mundo pode ser somada ao
longo do tempo em vez de refeita do zero.

## Objetivo
- O mesmo visual de hoje (a mesma penumbra borrada e a borda nítida em pixel), ou mais liso.
- Custo perto de 3 a 4 raios por pixel por quadro em vez de até 18.
- Opção nas Configurações (Sombra acumulada), ligada ou não; desligada, tudo como antes.

## Fora do escopo
- RT cores (não existem em OpenGL).
- A sombra dos personagens (mapa de sombra à parte, não muda).

## Como
1. **Passada da sombra**, logo depois da pré-passada de profundidade: o mundo é desenhado de novo num framebuffer
   sem MSAA do tamanho da cena, com a profundidade copiada da pré-passada (só o fragmento da frente roda, com o
   teste antecipado). O shader do mundo, na variante `SHADOW_ACCUM_PASS`, para logo depois de achar o ponto do
   mundo e grava dois alvos: (borrada, nítida, raios da borrada, raios da nítida) e (posição no mundo, válido).
2. **Histórico**: o ponto é reprojetado na tela do quadro anterior (matriz mundo → recorte dele). Se o pixel de lá é
   o mesmo ponto (mesmo plano da face e a menos de ~1,5 pixel no mundo), as somas dele continuam; senão começam de
   zero. Dois pares de texturas alternam a cada quadro.
3. **Raios novos por quadro**: sem histórico, o cone inteiro (12 + 6 na Alta), para não aparecer ruído; com histórico,
   3 borrados e 1 nítido, com o giro do cone avançando pelo ângulo de ouro a cada quadro (cobre o disco todo com o
   tempo). As somas param em 48 raios: daí em diante é média móvel (~16 quadros), e o sol mudando ou um bloco
   posto aparecem em ~1/4 de segundo.
4. **Passada de cor**: onde hoje chama `sunVisibility`, lê o resultado do mesmo pixel; se a posição gravada não é a
   do fragmento (a borda de um bloco com MSAA), calcula como antes.

## Decisões
- Só no caminho do cone (Média e Alta); água, cômodo escurecido e qualidade Baixa seguem com o raio único.
- Sem cena num framebuffer próprio (editor de personagem) a opção não vale.
- Com a Sombra em meia resolução ligada junto, vale a acumulada.
