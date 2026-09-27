# Camisa Roblox transferida para cage R15 do projeto

Asset: camisa social preta `133331049150205`.
ReferenceMesh da camisa: `80307990380242`; CageMesh: `78642992491592`.
Alvo: `assets/models/roblox_reference_cages.obj`, carregado pelo mesmo
pipeline de UV/cages do corpo feminino, mas substituído pelas partes R15.
O teste não executa o motor Roblox; usa somente os arquivos locais.

O controle de identidade da camisa passa: usando a própria ReferenceMesh da
camisa como alvo, o erro máximo da cage externa é <3e-17 e da roupa é zero.
A ReferenceMesh da camisa difere da cage R15 local; após ajustar globalmente
eixos, escala e origem, ainda há ~0,305 m de erro mediano. Portanto o ensaio
R15 é uma transferência real entre referências diferentes.

**Escopo real deste teste.** O alvo é o `ClassicMannequin_With-Cages.fbx`
disponível no repositório, **não foi comprovado que seja o avatar Blocky R15
quadrado solicitado**. O `Head_Geo` tem 1777 vértices e detalhes faciais;
o `Head_OuterCage` é outra malha, com 335 vértices. O corpo visível na
segunda prévia vem dos 15 objetos `*_Geo`, e não das cages. A comparação
geométrica mede a transferência para esse mannequin específico; não substitui
o teste em um Blocky R15 autêntico com suas cages correspondentes.

**Correção da avaliação visual.** A primeira imagem usava as superfícies das
cages como corpo e transparência no `Poly3DCollection`. Isso criou uma falsa
impressão de bom encaixe. A imagem `r15_office_shirt_transfer.png` agora usa
as 15 malhas `*_Geo` do mesmo FBX do ClassicMannequin; ainda é transparente.
O resultado com oclusão correta é `r15_office_shirt_depth.png`, com
oclusão por profundidade. Nessa imagem a pele do tronco aparece sobre grande
parte da camisa nas quatro vistas; a camisa está majoritariamente dentro do
corpo Blocky R15 ou mal posicionada em profundidade. A fração visível da
silhueta projetada da roupa é 14,2% na frente, 24,9% no lado, 20,6% nas costas
e 14,3% em 3/4. Essas frações incluem sobreposição da própria malha frente/
costas e não são uma medida direta de área de clipping; a imagem confirma o
problema visualmente nesse mannequin. Não extrapolar automaticamente para o
Blocky R15 solicitado.

Há também deformação mensurável. O percentil 99 do alongamento das arestas da cage é
6,21x, com 586 arestas acima de 3x. Na malha visível, o percentil 99 é
4,75x; 185 arestas com origem >=1 cm passam de 3x, sendo 139 com origem
>=3 cm. Os números e a prévia com profundidade rejeitam a hipótese de que o problema
surge somente da cage feminina: a transferência atual já distorce uma camisa
de outro avatar quando o alvo é o ClassicMannequin de referência do projeto.

Arquivos: `r15_office_shirt_transfer.png` (quatro vistas, antes/depois, corpo
transparente), `r15_office_shirt_depth.png` (corpo opaco e oclusão correta),
`r15_office_shirt_stretched_edges.png` (arestas alongadas),
`r15_office_shirt_transfer.json` (medidas) e
`scripts/test_r15_shirt_transfer.py` (reprodução).

Próxima hipótese a testar: o campo local por UV usado para transferir a cage
externa e o vínculo independente de cada vértice visível a um triângulo. Uma
cage alvo R15 correta não basta para compensar essas escolhas do algoritmo.
