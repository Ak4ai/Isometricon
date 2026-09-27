# Camisa de catálogo no Blocky R15 oficial

> Consulte `UNIVERSAL_WRAP_REVIEW.md` para a revisão posterior: unidades de
> arquivo não devem ser interpretadas como metros sem conversão explícita;
> grandes alongamentos em regiões não usadas pela camisa não localizam sua
> falha; e a prévia agora usa uma escala isotrópica comum às quatro vistas.

Origem do corpo: `BlockyCharacter.fbx` publicado pela Roblox em sua página de
[arquivos de referência de corpos](https://github.com/Roblox/creator-docs/blob/main/content/en-us/avatar/character-bodies/project-files.md).
O arquivo possui 15 partes `*_Geo` e 15 `*_OuterCage`. A renderização usa as
malhas `Geo`; a transferência da camisa usa exclusivamente as `OuterCage`.
Não se trata do `ClassicMannequin_With-Cages.fbx` testado anteriormente.

Roupa: camisa social preta `133331049150205`, com ReferenceMesh
`80307990380242` e CageMesh `78642992491592`. A cage externa Blocky foi
exportada do FBX sem alterar posições, faces ou UVs. As 1709 UVs lógicas da
referência da camisa correspondem às 1709 UVs da cage Blocky; erro máximo
aproximado de 7,24e-6. No controle em que a camisa é transferida para sua
própria referência, a malha visível é reproduzida com erro numérico zero.

**Resultado visual:** `blocky_r15_office_shirt_depth.png` usa rasterização com
teste de profundidade. A maior parte da superfície da camisa é ocultada pelo
tronco quadrado em frente, costas e 3/4. Há fragmentos azuis deformados ao
redor de pescoço, ombros e laterais. Portanto o algoritmo local não consegue
vestir adequadamente esta camisa no Blocky oficial. A imagem transparente
`blocky_r15_office_shirt_transfer.png` serve apenas para localizar as malhas;
ela não é evidência de encaixe ou ausência de clipping.

**Medidas:** na cage externa transferida, o percentil 99 do alongamento de
arestas é 9,97x, com 1722 arestas acima de 3x. Na malha visível da camisa, o
percentil 99 é 6,98x; 849 arestas originalmente maiores que 3 cm passam de
3x. O percentual de pixels azuis visíveis na silhueta projetada é 5,3% na
frente e 15,3% nas costas. Esse percentual também inclui oclusão entre faces
da própria camisa; a conclusão de penetração se apoia na imagem com
profundidade, não nele isoladamente.

Arquivos: `BlockyCharacter.fbx` (download oficial),
`BlockyCharacter_OuterCages.obj` (export local),
`blocky_r15_office_shirt_depth.png`,
`blocky_r15_office_shirt_transfer.json`, e
`scripts/test_r15_shirt_transfer.py` (reprodução).

Este teste elimina a cage feminina como causa necessária da falha. Ainda é
preciso decompor a transferência entre as cages e o vínculo da malha visível
para apontar precisamente qual etapa produz a maior parte da penetração.

## Diagnóstico das bordas (26/09/2026)

O relatório JSON agora mede separadamente a transferência da cage de referência
para a cage corporal e da cage externa original para a externa transferida. Na
primeira etapa, antes de vincular qualquer vértice da camisa, a mediana de
alongamento de arestas é 1,89x e o p99 é 9,97x. Há 2.032 arestas acima de 3x.
Uma aresta concreta da referência (vértices 332–334) mede 0,04793 no espaço
original e 1,0 no Blocky: 20,86x. Os extremos possuem UVs distintas e a cage
Blocky as posiciona em lados opostos de uma região quadrada. Isso demonstra
que correspondência por UV, mesmo exata, não garante deformação local suave.

Um teste temporário elevou o limite de escala tangencial de `_local_map` de
1,5x para 24x. A prévia de frente, lado e costas piorou: apareceram picos no
ombro/pescoço e a lateral da camisa ficou mais irregular. O limite foi
restaurado e a prévia original regenerada. Portanto, liberar a escala local
não resolve o problema. O próximo algoritmo precisa construir um campo
espacial contínuo para volumes próximos da cage e tratar as grandes mudanças
de forma entre cage de referência e corpo, em vez de transportar cada ponto
por um único triângulo com escala limitada.

## Experimentos de continuidade

`python -m scripts.experiment_blocky_continuous_field` compara a camisa
original com dois métodos experimentais sobre o mesmo FBX Blocky. O campo
afim ponderado por proximidade espacial (32 vizinhos) reduziu o número de
arestas da camisa acima de 3x de 1.555 para 1.140, mas abriu buracos no
tecido e diminuiu a visibilidade lateral de aproximadamente 60% para 38%.
Vizinhanças de 8 e 16 vértices também pioraram as métricas de alongamento.
Isso confirma que proximidade euclidiana mistura superfícies que não devem
compartilhar uma transformação (por exemplo, manga e tronco).

O vínculo coerente guiado pelas arestas da malha reduziu as arestas acima de
3x para 1.232 e o p99 de 9,17x para 7,53x, mantendo a visibilidade frontal
próxima à original (94,6% versus 94,3%). A imagem
`blocky_coherent_binding_depth.png` ainda mostra falhas na gola, ombros e
laterais. O experimento não entra no runtime: ele usa uma energia empírica
de escolha de faces e não resolve as grandes deformações da própria cage.
Os números e caminhos das quatro prévias estão em
`blocky_continuous_field.json`.
