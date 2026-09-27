# Diagnóstico: jeans com botas e cage dos pés

Peça: `Black_Distressed_Designer_Jeans_w__Boots_109837605892174.obj`.
Esta malha inclui botas e já tem pernas muito largas no arquivo original.

- No wrap atual, 478 de 2701 vértices (17,7%) se vinculam à cage dos pés. Eles ficam exclusivamente na extremidade inferior da peça. Portanto, vínculo com os pés é necessário para esta peça; não se pode inferir o mesmo para uma calça sem calçado.
- O contrafactual que proíbe a cage dos pés piora o resultado: abre a barra e desloca a região das botas em 15,6 cm na mediana e 33,1 cm no percentil 99. As arestas acima de 5 vezes o tamanho original sobem de 9 para 11.
- A projeção atual em uma única face da cage externa cria pontas abaixo da barra. As maiores quebras de malha estão no quadril/coxa (26 das 33 arestas acima de 3 vezes), e há quebras adicionais na canela/pé. Portanto, o problema não é simplesmente “usar cage do pé”.
- O experimento **volumétrico entre inner e outer cage**, com transferência global da forma da outer cage, preserva as botas e reduz arestas acima de 3 vezes de 33 para 2. A silhueta permanece larga, como na malha original. Esse resultado é promissor, mas a configuração global ainda inverteu 505 faces em relação ao baseline e não passou em validação universal; não ativá-la no runtime apenas para esta peça.

Imagens: `jeans_foot_binding_baseline.png`, `jeans_foot_binding_no_foot.png`, `dual_prism_109837605892174_global.png`, `source_garments_additional_corrected.png`. A sobreposição de cage na imagem antiga foi corrigida em `SOURCE_OVERLAY_DECISION.md`.
Dados: `JEANS_FOOT_BINDING.json`, `WRAP_DUAL_PRISM.json`.

Próximo critério de implementação: o bind deve preservar a profundidade do vértice entre as cages inner/outer e a continuidade da malha através das transições de partes, inclusive canela/pé; a presença de botas deve emergir da geometria e das cages da própria roupa, sem regra pelo nome do asset ou por categoria “calça”. Comparar visualmente e por distorção de arestas com calças sem botas e outros corpos antes de substituir o algoritmo atual.
