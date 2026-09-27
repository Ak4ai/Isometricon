# Por que as duas pernas do jeans diferem

Reprodução: `python scripts/audit_jeans_leg_asymmetry.py`. Os valores completos
estão em `LEG_ASYMMETRY.json`. A análise usa os dados do mesmo jeans com botas,
do mesmo corpo feminino e do mesmo resultado radial/prisma do relatório anterior.

## Separação das causas

| Geometria, somente parte inferior | Distância mediana até o próprio espelho |
| --- | ---: |
| Roupa original, após aplicar escala RMS de transferência | 0,0180 m |
| Cage externa original da roupa, após a mesma escala | 0,0165 m |
| Cage corporal feminina alvo | ~0,000000015 m |
| Cage externa transferida pelo radial | 0,0230 m |
| Roupa final com radial + prisma | 0,0294 m |

Esta medida procura, para cada vértice, o vértice mais próximo do lado
espelhado em 3D; ela também reflete diferença de amostragem entre malhas,
portanto não mede sozinha assimetria da superfície contínua. Os valores são
úteis para localizar onde ela aparece: a cage corporal é quase simétrica,
enquanto roupa e cage externa fornecidas com o asset já diferem entre as
pernas. A transferência preserva parte dessa diferença e a aumenta em
algumas regiões. A parte "front mesh" de `source_garments_additional_corrected.png`
mostra que a silhueta das pernas já difere na roupa original. As partes que
sobrepõem a reference cage na imagem antiga estavam desalinhadas; ver
`SOURCE_OVERLAY_DECISION.md`.

## Falhas restantes por lado

Usando o sinal X da roupa original para acompanhar seus próprios vértices,
abaixo de Y=−0,8 em espaço da cage:

| Resultado radial/prisma | X negativo | X positivo |
| --- | ---: | ---: |
| Arestas mensuradas | 1667 | 1484 |
| Arestas >3× | 15 | 10 |
| Faces mensuradas | 1039 | 919 |
| Faces com <10% da área esperada | 16 | **32** |

O lado X positivo se vincula majoritariamente às regiões RightLeg/RightFoot,
o X negativo às LeftLeg/LeftFoot. Não há evidência de uma troca geral das
pernas no vínculo. O lado positivo tem menos faces, mas o dobro de faces
fortemente comprimidas após o encaixe. Isso pode contribuir para uma perna
parecer mais estreita ou irregular; a contagem não mede diretamente a silhueta.
Os sinais X de origem e de câmera não devem ser confundidos com esquerda e
direita na imagem final, pois o runtime espelha X ao exportar.

## Conclusão e trabalho proposto

O corpo feminino escolhido não explica sozinho a diferença: sua cage das
pernas é quase simétrica. A roupa original e sua outer cage são assimétricas,
e o método radial/prisma ainda introduz compressão desigual e vínculos
descontínuos em algumas transições, como a aresta 734–737 entre LowerTorso
e LeftUpperLeg. Portanto, “fazer as duas pernas iguais” no Blender apagaria
forma existente no asset e não corrigiria a descontinuidade do algoritmo.

Radial + prisma é a melhor base experimental até aqui para este jeans, mas
não está pronto para produção universal. A próxima mudança verificável é
coerência dos vínculos de prismas entre vértices vizinhos da roupa, sem
forçar simetria e sem regra pelo nome do jeans. Deve manter a forma da cage
radial e comparar, nos seis controles fixos, as arestas de interface, as
faces comprimidas, penetração e orientação. Só então decidir integração.
