# Campo da referência refinada: reprovado para integração

Data: 2026-09-27. Produção e experimentos anteriores preservados.

[Abrir as seis comparações](refined_reference/index.html).

## Implementação e controle contra repetição

`src/clothing/experimental_refined_reference.py:RefinedReferenceField` constrói
um campo de similaridades locais, ponderado pela área da referência e distância
espacial. Cada ponto de apoio usa coordenadas baricêntricas correspondentes nas
superfícies de origem e destino. Rotações vêm da decomposição polar por face;
escala comum é a razão RMS das cages canônicas por UV. Reflexão é explícita.

Com nível 0 há um centro por face; com nível 2 há 16 centros de subtriângulos por
face. O refinamento é linear, não inventa curvatura. Para ambos os níveis, a
largura gaussiana usa a mesma regra: raiz de (distância ao centro original mais
próximo ao quadrado + metade da aresta mediana original ao quadrado). Não há
corte por k vizinhos; pesos variam continuamente e incorporam área por amostra.
Essas são escolhas nossas, não parâmetros conhecidos do Roblox.

É diferente do antigo `bind_visible_to_inner`, que escolhe uma única face. Não
é uma nova execução daquele binding nem uma implementação integral da patente.
É uma aproximação espacial, não um campo com associações anatômicas/topológicas
da malha visível. Perto de contatos, partes distintas ainda podem se influenciar.

As duas variantes usam a mesma cage e a mesma regra de pesos. A outer radial
anterior permanece congelada, portanto problemas de camadas não são resolvidos.
O comparativo radial/prisma vem dos NPZ anteriores; não recalculamos seu fitting.

## Resultados no conjunto fixo

Contagens de arestas >3x usam a mesma escala RMS e máscara histórica de comprimento
de origem >=0,01 das auditorias recentes. Não comparar diretamente com contagens
antigas sem normalização pela escala. Penetração usa vértices e centros de faces
contra a união das partes fechadas do corpo; não representa porcentagem de área.

| Caso | Arestas radial | Campo nível 0 | Campo nível 2 | Penetração radial | Nível 0 | Nível 2 |
|---|---:|---:|---:|---:|---:|---:|
| Camisa / Blocky | 957 | 422 | 461 | 27,82% | 35,85% | 34,68% |
| Camisa / feminino | 149 | 5 | 3 | 2,30% | 2,75% | 2,64% |
| Jaqueta / feminino | 116 | 0 | 0 | 1,93% | 7,38% | 6,95% |
| Jeans com botas / feminino | 76 | 8 | 0 | 2,15% | 2,87% | 2,80% |
| Vestido / feminino | 190 | 3 | 4 | 1,57% | 2,80% | 2,73% |
| Suéter / feminino | 43 | 0 | 0 | 3,47% | 3,73% | 3,62% |

Faces com área normalizada <0,1, radial → nível 2: Blocky 1→4, camisa 7→3,
jaqueta 2→2, jeans 50→49, vestido 9→0, suéter 4→0.
Discordâncias de orientação contra o mesmo frame de referência: Blocky 460→515,
camisa 366→224, jaqueta 153→78, jeans 239→133, vestido 174→92, suéter 366→264.
Esta última medida é um proxy, não certificação de inversões ou auto-interseções.

Revisão das imagens: o vestido perde a borda irregular e jeans mostram pernas
mais separadas, mas há recortes de corpo nas botas/quadril. A jaqueta perde
volume nas mangas, com braços expostos. Blocky continua com ombros penetrados
e pior cobertura. Os dois níveis têm forma muito semelhante: a grande mudança
vem de trocar o transporte, não há evidência de que subdividir resolva o encaixe.
Isso não rejeita toda subdivisão possível; rejeita este campo/refinamento.

Cada comparação tem três linhas (radial, nível 0, nível 2), quatro vistas e a
mesma escala entre variantes do caso. Corpo incluído no enquadramento; sem
texturas, iluminação ou culling. Azul é roupa e bege é corpo.

## Onde este candidato falha

`scripts/audit_refined_reference_constraints.py` aplica o próprio campo nos
vértices da cage de referência e compara com o destino conhecido. Essa é uma
checagem diferente de medir apenas a roupa. O campo é uma média aproximante:
normalizar pesos não garante interpolação das correspondências.

No Blocky, nível 2: erro máximo 9,08% da altura do corpo; p99 8,55%; mediana
1,34%; 1041 vértices usados ficam acima de 1%. No nível 0, máximo 9,30%.
Mais amostras não eliminam esse erro. Portanto não faz sentido aprovar o campo
porque ele suaviza arestas: nem os controles geométricos que deveriam guiá-lo
são suficientemente respeitados. Isso não prova que tal erro seja a única
causa da penetração, mas é uma falha direta e reproduzível desta aproximação.

A auditoria também encontra posições de origem coincidentes (arredondadas a
8 casas) com destinos diferentes entre identidades UV. Dispersão máxima em torno
da média do grupo: 0,169% da altura no Blocky e 4,71% no feminino. Isso abrange a
cage inteira, não necessariamente regiões usadas pela roupa. Um campo dependente
apenas de XYZ não consegue satisfazer exatamente alvos distintos para a mesma
posição. Não soldamos essas identidades, mas a avaliação puramente espacial
continua incapaz de distingui-las. A advertência contra misturar controles
conflitantes já existia em UNIVERSAL_WRAP_REVIEW.md; estes números quantificam
a falha neste candidato, não constituem descoberta de uma cage corporal errada.

## Decisão e próximo bloqueio

**Experimental rejeitado.** Não aumentar níveis/raios buscando uma métrica
favorável, nem integrar somente para calça/vestido por nome de roupa.

Antes de outra comparação visual, o próximo candidato precisa demonstrar
fidelidade às correspondências por identidade de superfície e explicitar como
trata posições coincidentes com destinos diferentes. Associar a roupa a essa
superfície de forma consistente continua sendo o bloqueio, junto da penetração
da outer congelada. O teste de controles deverá separar regiões regulares de
contatos/ilhas e medir resíduos por região; acertar movimentos rígidos globais
não basta. Não concluir que remodelar no Blender resolve estes erros de campo.

## Arquivos e reprodução

- `refined_reference/*.npz`: três malhas finais por caso.
- `refined_reference/<caso>.json`: métricas completas, imagens e hashes.
- `refined_reference/CAGE_CONSTRAINTS.json`: erros dos controles e índices piores.
- `scripts/experiment_refined_reference.py`: fitting, métricas e render.
- `tests/test_experimental_refined_reference.py`: similaridade/reflexão, duplicação
  e reindexação, continuidade local e coincidência de consultas.

```powershell
python scripts/experiment_refined_reference.py
python scripts/audit_refined_reference_constraints.py
python -m pytest tests/test_experimental_refined_reference.py tests/test_experimental_prism_validity.py tests/test_experimental_prism_constraints.py tests/test_experimental_shell_clearance.py tests/test_experimental_canonical_radial.py tests/test_multi_influence_shell.py tests/test_wrap_layer_fit.py tests/test_clothing_uv_cage_mapping.py tests/test_volumetric_cage.py -q -p no:cacheprovider
```

50 testes passaram. Os testes unitários aprovam propriedades limitadas do código;
os seis controles de assets reprovam sua integração.

Qual evidência rejeitaria a proposta? Aumento de penetração apesar da melhora de
arestas e falta de fidelidade aos controles. Ambos ocorreram nesta rodada.
