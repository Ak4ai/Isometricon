# Contato da camisa ligado à cage prismática — Blocky

Data: 2026-09-27. Experimento isolado com a camisa de catálogo `133331049150205` no `BlockyCharacter.fbx` oficial, usando o mesmo fixture, pose e quatro câmeras do controle `radial_frames`. O runtime de produção permaneceu intacto.

## Pergunta e método

O radial + prisma anterior ainda deixava cerca de 27,8% das amostras da camisa dentro do corpo. A tentativa anterior de clearance movia só a shell; isso podia ignorar o deslocamento residual da camisa. `scripts/experiment_joint_contact_blocky.py` constrói amostras dos vértices da camisa a partir do vínculo prismático e deixa essas colisões moverem a cage externa que as conduz. O passo preserva o limite de orientação da shell e usa `PrismShapeConstraints` para restringir determinantes, comprimentos de aresta e espessura.

Os frames locais do residual são linearizados no radial inicial durante o solve. Após o solve, a camisa é avaliada novamente pelo mapeamento prismático exato antes de medir. O ajuste rodou oito iterações, com todos os vértices da camisa como amostras de contato; os centros das faces entraram na métrica final, não no solve. Os 120 pontos de camisa com profundidade prismática zero não podem ser movidos através da outer cage.

## Resultado

| Medida | Radial + prisma | Contato ligado à roupa |
|---|---:|---:|
| Vértices e centros de faces da camisa dentro do corpo | 27,82% | 25,70% |
| Arestas normalizadas acima de 3x | 957 | 1.025 |
| Arestas abaixo de 1/3 do esperado | 6 | 10 |
| Triângulos com menos de 10% da área esperada | 1 | 0 |
| Triângulos com mais de 9x a área esperada | 235 | 259 |
| Inversões amostradas dos prismas usados | 334 | 317 |
| Vértices com binding invertido | 263 | 261 |
| Silhueta visível frente / lado / costas / 3/4 | 95,51% / 52,27% / 92,05% / 83,99% | 96,58% / 54,59% / 93,47% / 83,87% |

Imagem nas mesmas câmeras: [radial + prisma versus contato](blocky_133331049150205_comparison.png). A pasta `iteration_4` preserva a etapa intermediária, antes das quatro iterações adicionais.

O contato amostrado caiu 2,11 pontos percentuais e a visibilidade melhorou um pouco em três vistas. A manga ainda apresenta falhas. O esticamento extremo piorou: 68 arestas a mais passam de 3x, e aumentaram as áreas excessivas e as inversões prismáticas. O solver parou por limite de iterações, com 972 amostras internas restantes no seu conjunto de contato. Portanto, esta variante também **não está aprovada para integração**.

## Relação com a patente

A patente pública [US20250265799A1](https://patents.google.com/patent/US20250265799A1/en), reivindicações 1–6 e 16–20, descreve a outer cage da roupa como fonte de influências espaciais, com pesos por proximidade, alcance relacionado à espessura e rotações locais. `multi_influence_shell.transfer_outer_cage_radial` já implementa uma aproximação dessa ideia; a variante canônica também usa buscas radiais. O método radial + prisma reduziu as arestas acima de 3x do fixture Blocky de 1.219 no controle de produção para 957.

A patente também descreve consultas centradas tanto na cage fonte quanto na cage destino. Testamos essa extensão em `bidirectional_radial/RESULT.md`: ela reduziu contagens de inversão, mas piorou penetração e esticamento, sem reparar visualmente o ombro. A patente **não descreve inverter faces ou virar a outer cage** como solução para esse problema. A correção de paridade/winding é uma questão separada do radial.

## Próximo bloqueio

O solve ainda mantém o residual local fixo, usa sua transformação linearizada e não consegue mover pontos em profundidade zero. Esses limites correspondem ao conjunto que as auditorias anteriores localizaram: uma parte dos pontos entra no corpo durante o transporte da outer/prisma; outra parte entra depois, pelo residual. A formulação seguinte, se testada, precisa permitir ambos os graus de liberdade no mesmo objetivo e demonstrar melhora conjunta em contato, continuidade, área, arestas e volume. Não atribuímos essa formulação à Roblox.

## Reprodução

```powershell
python scripts/experiment_bidirectional_radial_blocky.py
python scripts/experiment_joint_contact_blocky.py
python -m pytest tests/test_experimental_shell_clearance.py tests/test_experimental_bidirectional_radial.py tests/test_multi_influence_shell.py tests/test_experimental_canonical_radial.py -q -p no:cacheprovider
```

Resultado dos testes direcionados: 25 passaram. Relatório completo e arrays estão em `blocky_133331049150205.json/.npz`. São medições de uma camisa no fixture Blocky, não uma garantia universal.
