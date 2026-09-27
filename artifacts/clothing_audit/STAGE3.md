# Etapa 3 — validação da cena do Blender

Cena examinada: `assets/models/female_cage_stage2_20260925_001439.blend`.

## Resultado

- 15/15 cages mantêm a quantidade de vértices e o layout UV por face do FBX R15 local (`r15_comparison.json`).
- Faces e UVs permaneceram iguais aos da etapa 1; a maior diferença entre as posições da cena e o plano aplicado ficou abaixo da tolerância numérica (`stage3_validation.json`).
- 138.802 amostras do corpo e pescoço: nenhuma descoberta pela união das 15 cages. A verificação usa tampas temporárias nas aberturas para testar contenção; essas tampas não foram adicionadas aos objetos.
- Nas 15 cages: nenhuma aresta com mais de duas faces, nenhuma incompatibilidade de orientação entre faces vizinhas, nenhuma face apontando para dentro contra a orientação consistente da superfície temporariamente fechada, nenhum triângulo de área abaixo de 1e-12 e nenhum cruzamento detectado entre faces sem vértices comuns. As aberturas nas extremidades das partes são esperadas.
- Comparadas às posições anteriores à etapa 2, não apareceram novos cruzamentos ou degenerações nos critérios acima.
- Revisão das vistas frontal, traseira e lateral: `stage3_front.png`, `stage3_back.png` e `stage3_side.png`. Não foi observado um problema evidente de silhueta nessas vistas.

## Limites e próximo trabalho

- A cabeça contém um triângulo com área aproximada de 1,18e-10 unidades quadradas, já presente antes da etapa 2. É pequeno; o exportador e a deformação devem tratar triângulos quase degenerados sem divisão por zero.
- A checagem de cruzamento não inclui pares de faces que compartilham vértices, nem garante ausência de problemas em todas as poses animadas.
- O teste de cobertura por amostragem e tampas temporárias não é uma prova matemática para todos os pontos da superfície. Uma peça de roupa real deve ser testada após a exportação.
- Etapa 4: exportar preservando coordenadas, faces, UVs e a correspondência R15; reler o arquivo exportado e testar o deformador com uma roupa real.
