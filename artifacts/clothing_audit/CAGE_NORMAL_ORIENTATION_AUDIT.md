# Causa principal da camisa atravessar o Blocky R15

> Revisão posterior: `UNIVERSAL_WRAP_REVIEW.md` e `WRAP_CONTRACT_AUDIT.json`
> demonstram que a paridade também deve ser aplicada à malha visível. O
> controle de reflexão falhava com erro máximo 0,321721 e agora tem erro zero.
> A conclusão abaixo de corrigir apenas a primeira etapa foi superada.

O `ReferenceMesh` da camisa está em um espaço cuja orientação geométrica é
oposta à da cage do `BlockyCharacter.fbx` no motor. As mesmas faces e UVs têm
volume assinado aproximado de +1,524 na referência da camisa e -13,481 no
alvo Blocky. A função `_local_map` anterior preservava o sentido da normal
entre os triângulos. Por isso, o deslocamento da cage externa que deveria
afastar a camisa da superfície corporal passava a apontar para dentro.

Experimentos isolados, sempre sobre o mesmo corpo Blocky oficial:

| Transferência da cage | Posição final da malha | Fração azul visível na frente |
| --- | --- | ---: |
| normal original | normal original | 5,3% |
| **normal invertida** | normal original | **94,3%** |
| normal original | normal invertida | 2,0% |
| normal invertida | normal invertida | 95,9% |

A segunda linha é a correção mais localizada. A imagem
`blocky_r15_office_shirt_baseline_depth.png` mostra a camisa novamente sobre
o tronco. O runtime agora detecta a orientação oposta pelo sinal do volume
assinado de duas cages com as mesmas faces/UVs e inverte **apenas a normal da
transferência da cage externa**. O teste de identidade mantém erro numérico
zero. Para a cage feminina testada com camisa, vestido e jeans, o sinal é
igual ao da referência; portanto esses três assets seguem o caminho anterior.

**Limite:** a correção resolve a penetração dominante no Blocky, mas não a
qualidade final. As arestas da cage ainda têm p99 de alongamento ~9,97x;
1.331 arestas visíveis da camisa originalmente >3 cm agora alongam >3x.
Há defeitos em ombro, barra e lateral. Isso aponta para o campo local por UV,
costuras entre partes e escolha independente de triângulo como problemas
separados a tratar. A fração visível não mede qualidade visual sozinha.

O arquivo oficial é descrito pela Roblox em
[arquivos de referência de corpos](https://github.com/Roblox/creator-docs/blob/main/content/en-us/avatar/character-bodies/project-files.md).
