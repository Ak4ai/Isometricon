# Decisão: primeiro protótipo de transferência com múltiplas influências

O protótipo `src/clothing/multi_influence_shell.py` usa a correspondência dos vértices das cages interna, externa e do corpo, já estabelecida pelos UVs. Para cada vértice da cage externa, calcula rotações locais a partir da vizinhança da cage interna e combina previsões de vértices conectados. Em uma transformação de identidade, rotação rígida ou reflexão declarada, reproduz a cage externa exatamente. É um controle experimental inspirado na arquitetura publicada, não uma reprodução do deformer privado do Roblox.

O teste `scripts/experiment_multi_influence_shell.py` executou cinco assets com duas formas de vincular a malha visível: projeção externa atual e prisma entre inner/outer cage. Resultados de arestas da malha acima de 3 vezes o tamanho original:

| Asset | Runtime atual | Cage candidata + projeção atual | Cage candidata + prisma |
| --- | ---: | ---: | ---: |
| Camisa | 9 | 17 | 13 |
| Jaqueta | 11 | 4 | 4 |
| Jeans com botas | 33 | 50 | 22 |
| Vestido | 86 | 109 | 55 |
| Suéter largo | 240 | 147 | 152 |

Os previews de quatro vistas mostram botas/barra melhores no jeans, mas ainda mostram pontas na saia e mudanças de forma na jaqueta. A comparação de normais com o baseline muda centenas de faces, o que exige uma avaliação de orientação absoluta; esse número, sozinho, não prova que todas foram invertidas. A queda da distorção das arestas também não certifica a silhueta. Por esses motivos, **o candidato foi rejeitado para o runtime**.

Diagnóstico: transportar offsets com vizinhos da cage interna melhora a estabilidade da cage externa, mas não resolve a seleção independente de prismas/faces da malha visível. O próximo protótipo precisa escolher correspondências por *superfície/painel conectado da roupa*, respeitando UVs e separações intencionais, e impor preservação de orientação e área dos triângulos. Também precisa medir penetração no corpo. Não ajustar pesos por nome de peça nem habilitar a candidata apenas para calças.

Dados completos: `WRAP_MULTI_INFLUENCE_SHELL.json`. Previews: `multi_influence_<asset>_{baseline,candidate,prism}.png` para jeans, vestido e jaqueta. Validação de código: 16 testes direcionados passaram.
