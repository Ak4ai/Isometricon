# Auditoria do corpo feminino e das cages

## Atualização: comparação direta com o FBX R15 original local

A inspeção anterior comparava principalmente arquivos exportados. Ela não justificava concluir que o usuário tivesse danificado a topologia ao modelar. Foi feita uma comparação adicional, lendo `ClassicMannequin_With-Cages.fbx` diretamente com o parser FBX do Blender, sem importar ou modificar a cena. Script: `scripts/compare_r15_reference.py`; resultados: `r15_comparison.json`.

- **UpperTorso:** 231 vértices, 206 faces; faces por índice e layout UV por face iguais à referência. Não há fundamento para refazer essa cage no Blender com base na divergência do OBJ.
- **Cabeça:** as 324 faces e seus UVs coincidem com a referência. O vértice adicional é o índice 335 (zero-based), solto, não usado por nenhuma face. Ele não representa uma subdivisão ou destruição da superfície original.
- **Seis partes esquerdas:** layout UV por face igual ao da parte esquerda correspondente da referência, ignorando ordem das faces, início do polígono e winding. Isso evita confundir reindexação com alteração de identidade UV.
- **Seis partes direitas:** cada uma tem layout UV por face exatamente igual ao da parte ESQUERDA da referência, e diferente do da parte direita. É compatível com duplicação/espelhamento que preservou UVs esquerdos; a operação histórica que produziu isso não foi observada.
- **LowerTorso:** 92 vértices e 74 faces preservados em quantidade. Quatro loops UV, em dois vértices atuais (79 e 86, zero-based), diferem da referência; as demais faces têm layout UV correspondente. A maior distância ao UV de referência mais próximo é 0,020325. Não é erro de arredondamento.
- A correspondência foi comparada com o FBX R15 local, não com uma certificação no Studio ou uma cópia oficial recém-baixada.
- Uma checagem adicional de cruzamento segmento/triângulo, triangulando quads em leque, encontrou cruzamentos entre a superfície da cage e o corpo correspondente na pelve e nos dois braços superiores. No UpperTorso não encontrou cruzamentos. Resultados em `surface_crossings.json`. Esse teste não certifica contenção completa, não cobre todas as partes e depende da triangulação adotada.

**Conclusão atualizada:** a base R15 está amplamente preservada e o corpo não precisa ser refeito. Há correções pontuais de UVs (direita/pelve), cobertura e limpeza de um vértice solto. As diferenças entre a superfície do tronco no Blender e o OBJ continuam sendo um problema da representação/exportação, não evidência de que seja necessário remodelar o tronco.

Os dados históricos abaixo continuam úteis, mas a verificação de UVs que estava pendente foi agora realizada contra o FBX local.

Inspeção dos arquivos usados pelo motor e da cena aberta `123.blend`, incluindo a malha de edição do UpperTorso. Nenhum objeto, arquivo de modelo ou código do motor foi alterado. Execute `python scripts/audit_clothing_compatibility.py` com o servidor Blender disponível para reproduzir as medições.

## Conclusão

O corpo é uma base aproveitável para um adaptador de roupas Roblox no motor próprio. As cages exportadas e o pipeline atual ainda não podem ser considerados compatíveis de maneira confiável. A pose A, por si só, não resolve correspondência, cobertura e transformações.

## Evidências

- O motor usa `character_female_clean_apose.obj` e `female_cages_apose.obj`. As posições dos vértices das partes do corpo exportado coincidem com as partes correspondentes da cena dentro de aproximadamente 0,000001 unidade.
- As 15 cages exportadas têm contagens de vértices e faces trianguladas idênticas à referência local `roblox_source_cages.obj`. Isto verifica a estrutura dos arrays, não a identidade anatômica dos vértices nem conformidade com um template oficial independente.
- Na cena, as 15 cages têm UVs (o UpperTorso deve ser lido por BMesh em modo de edição). Os dois OBJs usados pelo motor não contêm `vt`. A compatibilidade desses UVs com um template Roblox oficial ainda não foi verificada.
- UpperTorso e LowerTorso têm as mesmas posições geométricas na cena e no OBJ (erro de conjunto inferior a 0,000001), mas ordem de vértices diferente. Reordenação consistente não é um erro por si só.
- Após estabelecer correspondência espacial bijetiva entre cena e OBJ, 17 arestas da cena do UpperTorso e 14 do LowerTorso não existem no OBJ. Triangular quads acrescenta diagonais, mas não deveria remover suas arestas de contorno. Logo, a conectividade exportada não reproduz integralmente a cena nessas regiões. A etapa exata que introduziu a diferença não foi identificada.
- O reparo em runtime altera 4 vértices da cabeça, 4 do UpperTorso e 2 do LowerTorso. Reduz algumas arestas longas (cabeça: 0,282 para 0,116; pelve: 0,478 para 0,280), mas isso não constitui prova de correção integral. As comparações após reparo por vizinho mais próximo são apenas diagnósticas, pois as posições foram alteradas.
- A cabeça da cena tem 336 vértices, enquanto a referência local e o OBJ têm 335. Há divergência geométrica de conjunto de até 0,0307 unidade. É necessário reconciliar as versões antes de reexportar por índice.
- Três vértices da pelve ultrapassam a caixa delimitadora de sua cage em até 0,00277 unidade. Seis vértices de cada canela ultrapassam a respectiva cage em até 0,001665. Isso prova cobertura incompleta por essas cages individuais, inclusive na cena. Não foi medida a cobertura pela união de cages vizinhas. Estar dentro da caixa não prova estar dentro da superfície; não foi feita certificação completa de interseções/autointerseções.
- As partes do corpo inspecionadas usam parentesco com ossos, sem grupos de vértices ou modificador Armature. Isso permite corpo segmentado rígido. Não comprova transferência de skinning para roupas que atravessem articulações.
- O caminho feminino atual usa projeção em referência genérica, sem carregar a inner cage e as transformações específicas de cada roupa. O importador/exportador precisa preservar esses dados para uma solução geral.

## Próxima correção recomendada

1. Estabelecer uma única versão de corpo e cages; reconciliar cabeça e conectividade de tronco/pelve.
2. Preservar UVs e/ou IDs canônicos verificáveis na exportação, mantendo a ligação entre posições e faces.
3. Ajustar cobertura e verificar triângulos cruzados, orientação e costuras sobre o corpo inteiro.
4. Importar cages e transformações do WrapLayer da roupa; testar uma peça conhecida antes de generalizar.
5. Para animação, definir transferência de pesos/transformações articulares para a roupa.

O objetivo aqui é vestir o personagem no Isometricon. Não foi feita certificação de publicação do corpo no Marketplace, que envolve outros requisitos.

## Arquivos

- `metrics.json`: medições por parte.
- `scene_snapshot.json`: geometria/UVs e metadados lidos da cena, sem alterações.
- `comparison.png`: frente e perfil; verde = corpo exportado, ciano = cage. Colunas: OBJ, cage após reparo, cena Blender. Os dois primeiros são triangulados; diagonais extras, isoladamente, não são defeitos.

## Referências oficiais

- https://create.roblox.com/docs/avatar/character-bodies
- https://create.roblox.com/docs/art/characters/creating/caging
- https://create.roblox.com/docs/reference/engine/classes/WrapLayer
