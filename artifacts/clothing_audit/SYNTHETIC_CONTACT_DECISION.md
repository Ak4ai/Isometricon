# Proximidade entre partes: falha radial reproduzida e isolada

2026-09-27. Diagnóstico experimental; produção preservada.

[Comparações](synthetic_contact/index.html) · [Métricas e testemunhos](synthetic_contact/SUMMARY.json).

## Resultado

Ao aproximar a cage de um volume parado da cage de um braço que dobra, a busca
radial passa a misturar previsões de movimentos diferentes. A malha da manga
fica fora da posição esperada. O ensaio **não reproduziu penetração no corpo**
nem prova que essa é a causa das falhas de ombro no Blocky.

Há dois volumes desconectados e uma manga no braço, não uma junção humana
costurada nem uma camisa contínua cobrindo braço e tronco. É o próximo controle
de interação espacial após a dobra isolada, com resposta analítica conhecida.

## Experimento que mudou uma variável

`scripts/experiment_synthetic_contact.py:fixture` preserva braço, manga,
deformação e resposta. Move apenas o volume parado e suas cages. Distâncias
entre eixos: 0,80; 0,76; 0,74; 0,72; 0,70; 0,68; 0,64; 0,60.
O raio de influência permanece igual à espessura, como no controle anterior.
Não ajustamos parâmetros do deformer por caso.

Em todos os casos, os corpos originais estão separados, e a manga original
fica fora do corpo vizinho. Em d=0,74, as cages externas tocam: raios 0,34 e
0,40. A distância entre superfícies corporais ainda é 0,24; entre manga e
corpo vizinho, 0,15. Nos casos mais próximos, as outer cages se intersectam,
embora os corpos e a manga não se intersectem na origem. Essa condição de
cage é declarada; não estamos afirmando que corresponde ao contrato de um
asset oficial do Roblox.

## Separação das etapas

Cinco variantes mantêm a mesma resposta e escala de visualização:

1. Resposta analítica.
2. Radial completo com vínculo automático por prisma.
3. Mesma outer radial, vínculo da manga fixado no braço isolado.
4. Influências radiais calculadas separadamente por componente, com a mesma
   escala global do radial completo e o vínculo automático original.
5. Vínculo automático recebendo a outer analítica correta.

A variante 4 usa informação conhecida do fixture. É um **controle diagnóstico**,
não proposta de algoritmo universal por componentes. Experimentos topológicos
anteriores já existem; não os estamos reapresentando como uma solução nova.

## Evidência quantitativa

Erro p99 de posição, percentual da folga da manga (0,09):

| Distância | Radial completo | Vínculo fixado no braço | Influências separadas | Outer correta |
|---|---:|---:|---:|---:|
| 0,80 | 8,2% | 8,2% | 8,2% | 8,9% |
| 0,76 | 8,2% | 8,2% | 8,2% | 8,9% |
| 0,74 | 232,7% | 232,7% | 8,2% | 8,9% |
| 0,72 | 267,6% | 267,6% | 8,2% | 8,9% |
| 0,70 | 310,9% | 310,9% | 8,2% | 8,9% |
| 0,68 | 451,7% | 451,7% | 8,3% | 8,9% |
| 0,64 | 673,0% | 673,0% | 8,2% | 8,9% |
| 0,60 | 431,6% | 431,6% | 8,2% | 8,9% |

Os critérios são os mesmos da dobra isolada. A partir de 0,74 o radial completo
reprova. A variante separada e a outer correta passam nos oito casos. O erro
não cresce monotonamente: a seleção de vizinhos e seus pesos muda com a distância.
O toque em 0,74 é sensível a arredondamento, mas a falha em 0,72 confirma que
não se trata apenas de inclusão numérica no limite do raio.

Em d=0,74 há 18 pares de influência entre componentes; o peso estrangeiro
chega a 50% em vértices da outer do braço. Nenhum vértice da manga está ligado
a um prisma do vizinho. No testemunho do vértice 512, dois vértices da face
de suporte recebem peso estrangeiro 0,5. Portanto, nesse caso, **a associação
ao prisma do braço é correta, mas sua outer já foi contaminada**.

Em d=0,68 aparece uma associação ao outro componente. Fixar todas as associações
no braço não remove o erro grande; a contaminação da outer permanece dominante
neste ensaio. Não generalizar essa conclusão para outros assets.

`cross_weights` reconstrói a seleção e as duas normalizações de pesos de
`src/clothing/multi_influence_shell.py:transfer_outer_cage_radial`. O controle
separado mantém rotações por conectividade e a escala global original; remove
os pares entre componentes e renormaliza as influências permitidas.

## O que isso permite concluir

Identificamos uma condição suficiente para falha na nossa implementação radial:
proximidade das cages permite combinar movimentos incompatíveis com a resposta
esperada da manga. Preservar o vínculo de superfície, sozinho, não corrige isso.

Isso não prova um defeito da patente nem uma cage corporal do usuário errada.
Também não autoriza bloquear todas as influências entre partes: vestidos e
saias podem depender justamente dessas relações para manter continuidade.
No toque de duas outer cages, o fixture permite posições coincidentes com
destinos diferentes porque são superfícies independentes. Uma costura intencional
exigiria outro contrato. Precisamos distinguir essas situações antes de alterar
o algoritmo geral.

O próximo bloqueio é verificar **se o mesmo mecanismo ocorre nas regiões que
falham no Blocky**, usando os pesos reais e as identidades das superfícies,
antes de propor um filtro. O controle já fornece uma hipótese testável sem
precisar repetir ajustes de roupa inteira. Se os vértices problemáticos do
Blocky não receberem tais influências, rejeitar essa explicação para eles.

## Reprodução e validação

```powershell
python scripts/experiment_synthetic_contact.py
python -m pytest tests/test_synthetic_contact.py tests/test_synthetic_wrap_fixture.py tests/test_experimental_refined_reference.py tests/test_experimental_prism_validity.py tests/test_experimental_prism_constraints.py tests/test_experimental_shell_clearance.py tests/test_experimental_canonical_radial.py tests/test_multi_influence_shell.py tests/test_wrap_layer_fit.py tests/test_clothing_uv_cage_mapping.py tests/test_volumetric_cage.py -q -p no:cacheprovider
```

56 testes passaram. Os três novos verificam braço/resposta invariantes no sweep,
ausência de colisão da resposta, detecção no vizinho deslocado e auditoria dos
pesos entre componentes. Os limites e resultados ficam em `SUMMARY.json`;
NPZ guardam entradas, vínculos, saídas, pesos e shells para cada distância.
Renderizamos o controle separado, a primeira falha e a maior proximidade,
com quatro vistas e escala comum ao sweep. Outros casos têm métricas e NPZ.
