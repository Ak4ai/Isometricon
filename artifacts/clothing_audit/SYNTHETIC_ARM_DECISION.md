# Braço analítico: controle útil aprovado; interpolador espacial reprovado

Data: 2026-09-27. Não é aprovação do runtime universal nem do fitting Roblox.

[Imagens e métricas](synthetic_arm/index.html).

## O que foi criado automaticamente

`scripts/synthetic_wrap_fixture.py` gera braço cilíndrico fechado, cage interna,
cage externa, manga aberta nas extremidades e, opcionalmente, outro cilindro
parado próximo, representando um volume corporal vizinho. Não é um torso humano
modelado. Não usa arquivos Blender nem muda assets reais.

Comprimento 2; raios: corpo 0,20, inner 0,24, outer 0,34, manga 0,29.
Folga esperada 0,09. A manga ocupa z de 0,15 a 1,85. Unidades arbitrárias.
A dobra de 90 graus é F(x,y,z)=((R+x)cos(z/R)-R, y, (R+x)sin(z/R)), R=4/pi.
Ela preserva as seções circulares; det(J)=1+x/R>0 neste domínio. A inversa
analítica permite medir folga e pertencimento ao corpo. Não é uma simulação de
tecido nem uma articulação rígida com quina; é uma dobra curva e contínua.

O destino correto da manga é F(manga_original). Os métodos sob avaliação recebem
as cages origem/destino e a manga original, **não** a manga resposta. Como cages
finitas não determinam de forma única o campo entre vértices, a resposta analítica
é um controle escolhido, não a única deformação fisicamente admissível.

## Casos e métodos

1. Identidade: controle de montagem do experimento.
2. Dobra isolada: cage de 9 anéis x 16 lados.
3. Dobra com cage mais resolvida: 17 x 32.
4. Dobra original com vizinho parado: centro x=0,8, corpo de raio 0,30.

No caso 3, os novos pontos alvo vêm da função analítica. Isso acrescenta
informação sobre a curva, diferentemente de subdividir linearmente faces já
deformadas. Não atribuir o ganho apenas à densidade de amostras de interpolação.

Métodos: `transfer_outer_cage_radial` + `evaluate_binding` por prisma; o mesmo
binding recebendo a outer exata (controle para separar etapas); e
`RefinedReferenceField` níveis 0 e 2. Nenhum representa uma execução completa
do runtime de importação Roblox. Mantivemos os algoritmos existentes intactos.

## Critérios fixados antes de executar

Erro p99 de posição <=10% da folga; máximo <=25%; p99 do erro relativo de arestas
contra a resposta <=10%; nenhuma amostra penetrante; nenhuma face abaixo de 10%
da área correta e nenhuma normal divergindo mais de 90 graus da resposta.
Esses limites são diagnósticos nossos, não requisitos do Roblox. Normal e área
não certificam ausência de auto-interseções. Penetração é medida em vértices e
centros de faces contra volumes analíticos; não certifica cada ponto da malha.

## Resultados

Erro p99 de posição como percentual da folga inicial (menor é melhor):

| Caso | Radial + prisma | Prisma com outer exata | Campo nível 0 | Campo nível 2 |
|---|---:|---:|---:|---:|
| Identidade | ~0% | ~0% | ~0% | ~0% |
| Dobra isolada | 8,24% | 8,94% | 12,92% | 13,92% |
| Dobra mais resolvida | 2,03% | 2,05% | 5,57% | 5,84% |
| Dobra + vizinho parado | 8,24% | 8,94% | 407,95% | 411,63% |

Radial/prisma e prisma com outer exata passam nos quatro controles. Os campos
passam na identidade e na dobra mais resolvida; reprovam nos outros dois.
Nenhum método apresentou amostras penetrantes neste conjunto. Isso demonstra
por que só medir penetração também não basta: uma manga pode ficar fora do corpo
e ainda estar no lugar errado.

No radial/prisma, a folga mínima é 91,72% da esperada na cage inicial e 97,93%
na mais resolvida. Erro p99 de comprimento das arestas cai de 4,34% para 0,28%.
Com outer exata, o erro da malha persiste na cage inicial e diminui na densa:
há erro de representação/interpolação entre amostras, não apenas da outer.
A pequena vantagem do radial sobre a outer exata não prova superioridade:
erros de etapas distintas podem se compensar.

Limitação importante: com raio igual à espessura, neste fixture radial todos os
pontos da outer recebem apenas a influência correspondente. Não exercitamos
as múltiplas influências radiais necessárias em saias ou contatos complexos.
O resultado não contradiz os prismas dobrados encontrados nos assets reais.

## Diagnóstico causal do vizinho

`scripts/audit_synthetic_neighbor.py` testa as duas escalas globais (braço
isolado 0,95653; conjunto 1,16913) com e sem apoio do vizinho. Ao manter a escala
do braço isolado, o erro p99 do campo nível 2 ainda sobe de 13,92% para 421,54%
da folga. Portanto a escala global não explica sozinha a contaminação.

Vértice 512: origem [0,29; 0; 1,85]. No campo padrão com vizinho, **30,41% do peso
vem da superfície parada**. O erro final é 473,14% da folga. O suporte é
construído no espaço de origem; mesmo quando o braço se afasta no destino,
a previsão imóvel do vizinho continua participando da média.

Adicionar o vizinho muda a manga radial/prisma apenas na ordem de 1e-15; no
campo nível 2, muda p99 em 407,73% da folga. As diferenças de índice/topologia
não são a explicação aqui: as cages têm correspondências explícitas e válidas.

## Conclusão e próximo bloqueio

Temos uma base reutilizável em que uma parte do transporte funciona e outro
método falha por mistura de movimentos. Não é necessário descartar todo o
progresso, mas não promover o campo espacial suave rejeitado.

O próximo avanço precisa preservar essa independência entre superfícies com
movimentos diferentes, sem impor uma separação artificial à continuidade de
saias. Esse é um requisito de associação/ponderação a demonstrar em controles,
não autorização para classificar roupas por nome ou soldar cages por posição.
Passar aqui não resolve contatos no ombro Blocky, cages com folds nem camadas.

## Reprodução e arquivos

```powershell
python scripts/experiment_synthetic_wrap.py
python scripts/audit_synthetic_neighbor.py
python -m pytest tests/test_synthetic_wrap_fixture.py tests/test_experimental_refined_reference.py tests/test_experimental_prism_validity.py tests/test_experimental_prism_constraints.py tests/test_experimental_shell_clearance.py tests/test_experimental_canonical_radial.py tests/test_multi_influence_shell.py tests/test_wrap_layer_fit.py tests/test_clothing_uv_cage_mapping.py tests/test_volumetric_cage.py -q -p no:cacheprovider
```

53 testes passaram. Os três novos verificam inversa/Jacobiano da transformação,
folga correta, fechamento do corpo e detecção de pontos internos nos dois volumes.

`synthetic_arm/SUMMARY.json` contém critérios, métricas e hashes. NPZ de entrada
incluem corpo, cages, manga e resposta; NPZ de saída guardam cada variante.
`NEIGHBOR_ABLATION.json` guarda o controle de escala e testemunhos dos pesos.
PNG de cada caso tem cinco linhas (resposta, radial, outer exata, campo 0, campo 2)
e quatro vistas, sempre na mesma escala entre variantes. O vizinho pode ocultar
o braço na vista lateral; não confundir essa oclusão com penetração.

Critério de rejeição: um vizinho parado não deve puxar a manga de um braço cujo
movimento não mudou. O campo espacial viola esse controle mesmo com escala fixa.
