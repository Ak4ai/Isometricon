# Jeans com botas: o que a cage radial e o prisma corrigem

Reprodução, sobre os mesmos dados do rastreamento do runtime:

```powershell
python scripts/trace_female_jeans_runtime.py
python scripts/audit_jeans_radial_witnesses.py
python -m pytest tests/test_multi_influence_shell.py tests/test_experimental_canonical_radial.py tests/test_wrap_layer_fit.py -q -p no:cacheprovider
```

O resultado está em `RADIAL_PRISM_WITNESSES.json` e na imagem
`radial_prism_witness_comparison.png`. As quatro variantes usam os mesmos
vértices da roupa, corpo, vistas, escala e métrica. Nenhum parâmetro foi
escolhido pelo nome da roupa: a experiência radial usa `radius_factor=1`.

## Garantia de comparabilidade

- A malha de produção do fixture é exatamente a gerada pela chamada fresca
  `wear()` auditada anteriormente: erro máximo zero.
- O fingerprint do vínculo em prismas arquivado bate com as cages e com o
  código atual de `closest_prism_binding`.
- A cage radial, recalculada pelo código atual de
  `transfer_outer_cage_radial`, bate com a arquivada; a avaliação final dos
  prismas também bate com o resultado arquivado. Erros exatos em
  `RADIAL_PRISM_WITNESSES.json`.
- “Só cage radial” conserva os vínculos por face externa do runtime.
  “Só prisma” conserva a cage externa do runtime. A quarta combinação usa
  ambos. Assim separam-se os efeitos das duas mudanças.

## Resultados

| Cage externa / vínculo visível | Aresta 2396–2397 após normalizar escala | Z do vértice 1464 da bota | Arestas >3× | Faces com <10% da área esperada | Amostras dentro do corpo |
| --- | ---: | ---: | ---: | ---: | ---: |
| Produção / face externa | 23,67× | −0,156 m | 584 | 69 | 7,65% |
| Radial / face externa | 1,56× | +0,118 m | 104 | 47 | 4,60% |
| Produção / prisma | 1,39× | +0,020 m | 399 | 99 | 6,59% |
| Radial / prisma | **1,17×** | **+0,021 m** | **76** | **50** | **2,15%** |

“Amostras” são vértices e centros de faces contra componentes corporais
fechados; não é percentual de superfície. Razões de aresta e área usam o mesmo
fator RMS do relatório de seis controles. As contagens antigas de 33 arestas
usavam razão sem esta normalização e não podem ser comparadas diretamente.

## Dois defeitos rastreados

### Pelve–coxa, aresta 2396–2397

Na produção, o vértice 2396 segue LowerTorso e 2397 segue RightUpperLeg.
Suas previsões para o mesmo ponto de origem diferem 0,164 m e a aresta final
mede 0,163 m. No prisma, os dois passam à **mesma face 1559 da RightUpperLeg**,
com profundidades 0,5205 e 0,5627. A aresta final mede 0,00805 m na
combinação radial/prisma. O resíduo de cada vértice é inferior a 0,005
unidade de origem. A continuidade local foi restaurada nesse ponto.

Ambas as substituições isoladas também reduzem muito essa aresta. Logo,
o defeito não é explicável por uma única operação: a forma da outer alvo
e a escolha independente de face contribuem. A combinação é a melhor
das quatro nesses mesmos pontos.

### Ponta da bota, vértice 1464

Na produção, o apoio está em Z=+0,00477 m, mas o resíduo transportado
tem Z=−0,16086 m e leva o vértice a −0,15610 m. Com prisma, o vértice
passa para a face 2360, na região RightLowerLeg, profundidade 0,0535.
Seu resíduo de origem é ~2,1×10⁻⁹ e o ponto fica em Z=+0,02126 m com
cage radial. Assim, **a ponta específica de 1464 desaparece** porque o
vínculo volumétrico não extrapola seu grande resíduo original. A mudança
apenas da cage radial também move 1464 para cima, mas até +0,118 m;
isso não demonstra que a forma da bota esteja correta.

## O que ainda falha

- Na combinação radial/prisma restam **76 arestas >3×**, **50 faces muito
  comprimidas** e **144 de 6690 amostras dentro do corpo**.
- A pior aresta restante é 734–737, **7,45×**. Seus vértices ainda se ligam
  a prismas de regiões diferentes: LowerTorso e LeftUpperLeg. Ou seja, a
  seleção independente da região persiste em outra transição pelve–perna.
- O ponto mais baixo restante é o vértice 371, Z=−0,0610 m, na região
  LeftFoot. Ali o resíduo do prisma é praticamente zero: o próprio ponto
  interpolado na cage alvo está em Z=−0,0610 m. Uma bota pode legitimamente
  ficar abaixo do pé do corpo; a altura isolada **não prova um novo defeito**.
- A auditoria anterior do mesmo resultado registrou 239 desacordos de
  orientação com o frame interno de referência e 10,9% de amostras com
  Jacobiano prismático invertido. São verificações geométricas, não contagens
  definitivas de faces visíveis invertidas. A imagem ainda mostra recortes
  e cobertura imperfeita perto da cintura e das barras.

## Decisão

A experiência radial/prisma corrige os **dois exemplos concretos** do
runtime, mas não resolve a continuidade em outras transições nem passa
em qualidade global. Permanece experimental. O próximo bloqueio concreto
é escolher vínculos de região de forma coerente para uma área conectada
da roupa, mantendo a forma externa e a espessura; a aresta 734–737 é um
novo controle falsificável. Antes de integrar, a mudança também precisa
passar nos seis controles fixos, inclusive camisa no R15 Blocky.
