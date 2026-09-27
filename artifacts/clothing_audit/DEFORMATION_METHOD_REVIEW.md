# Metodologia após a auditoria de volume

Data: 2026-09-27. Investigação, não solução universal nem implementação do Roblox.

## Nova evidência

`src/clothing/experimental_prism_validity.py:determinant_bounds` calcula os
extremos do Jacobiano de cada prisma linear pareado sobre todo o domínio de
coordenadas baricêntricas e profundidade. O determinante é linear nas coordenadas
baricêntricas e quadrático na profundidade: basta avaliar os três cantos, os
extremos de profundidade e os pontos estacionários internos de cada quadrática.
O cálculo está sujeito a arredondamento; a classificação usa tolerância
1e-12 vezes a diagonal da cage interna ao cubo.

Foi aplicado às faces efetivamente usadas pelos vínculos congelados. Uma célula
com determinantes positivos e negativos não é um domínio localmente invertível.

| Caso | Células usadas | Sinal misto na origem | Sinal misto após radial |
|---|---:|---:|---:|
| Camisa / Blocky | 595 | 0 | 75 |
| Camisa / feminino | 595 | 0 | 98 |
| Jaqueta / feminino | 695 | 13 | 106 |
| Jeans com botas / feminino | 732 | 26 | 169 |
| Vestido / feminino | 491 | 12 | 83 |
| Suéter / feminino | 636 | 74 | 196 |

Na jaqueta há ainda três células próximas de zero na origem sem mudança de sinal.
No Blocky, a correção protegida reduz 75 para 69 células com sinal misto.

Isso **não prova cages originais incorretas**, nem que todos os vértices ligados a
essas células estejam visualmente errados. O prisma é uma representação nossa.
UVs correspondentes não garantem que ligar cada par de triângulos com segmentos
retos forme um volume válido. Os números tampouco medem colisões entre células,
auto-interseções da superfície ou validade de faces não usadas. A camisa tem
origem localmente regular neste critério, e seu defeito aparece na transferência.

`scripts/audit_exact_prism_validity.py` salva faces, extremos, testemunhos e hashes
em `prism_clearance/EXACT_PRISM_VALIDITY.json`. Não executa fitting nem altera dados.

## Pesquisa e decisão

[LIM, Schüller et al. 2013](https://igl.ethz.ch/projects/LIM/) descreve barreiras
contra inversões em mapas planares/volumétricos por elementos lineares.
[IPC, Li et al. 2020](https://ipc-sim.github.io/) trata contato e inversões durante
deformações. São referências para otimização geométrica, não descrições do Roblox.
Não aplicaremos agora uma barreira volumétrica aos prismas existentes: quatro
peças já violam a regularidade local na origem, e não validamos um volume global
conforme. Mesmo Jacobianos positivos não bastam para excluir colisões globais.

A [patente US20250265799A1, descrição da Fig. 20, bloco 2006](https://patents.google.com/patent/US20250265799A1/en)
discute artefatos entre pontos de apoio da cage e processamento com subdivisão,
amostragem adicional e interpolação. Também apresenta uma possibilidade baseada
na cage interna. Isso fornece uma etapa concreta ainda não avaliada nos scripts
revisados; não especifica completamente pesos, suavização e implementação runtime.

**Uma próxima implementação: interpolador local da cage de referência refinada,
sem coordenadas de prisma.** O experimento deverá:

1. Refinar de modo correspondente a superfície de referência e sua superfície
   alvo, transportando a mesma identidade UV e os mesmos coeficientes de subdivisão.
   Não soldar pontos só porque estão próximos; tratar seams pela identidade já
   auditada. Guardar controles sem refinamento para separar o efeito dessa etapa.
2. Pré-calcular suportes locais na origem e interpolar transformações de múltiplos
   pontos refinados para a malha visível. Usar pesos contínuos, normalizados,
   independentes da ordem dos vértices, e transporte rotacional do afastamento.
   Esses pesos/frames são escolhas nossas a documentar, não fórmulas atribuídas
   à patente. Não escolher uma face ou prisma distinto para cada ponto como
   restrição exclusiva; não ajustar por nome da roupa.
3. Manter a transferência radial da outer congelada para comparação/diagnóstico
   de camadas. Assim o teste isola a interpolação visível. Se a outer continuar
   penetrando o corpo, o sistema de camadas continua reprovado mesmo que a roupa
   visível melhore. A nova etapa não promete resolver esse defeito da outer.

O teste antigo `scripts/experiment_inner_reference_binding.py` já tentou projeção
na inner e transporte residual por uma face. Repeti-lo seria loop. A diferença
exigida aqui é **refinamento correspondente e campo com múltiplos apoios**, cuja
continuidade e precisão devem ser verificadas, não apenas um novo nome para o
mesmo nearest-face. Subdividir linearmente sem mudar o campo afim não acrescenta
informação: um controle afim deve continuar igual. Se a densidade não reduzir o
erro do campo não afim, não avançar aumentando subdivisões indefinidamente.

Primeiro verificar identidade, movimento rígido/reflexão/escala, invariância a
reindexação e continuidade ao atravessar limites de faces/seams; depois testar
os seis casos congelados, com métricas e imagens iguais. Aprovação exige avaliar
conjuntamente penetração, distorção, área, orientação, seams e forma visual.
Jacobian de prismas deixa de ser métrica direta do novo interpolador; conservar
apenas como diagnóstico contrafactual, sem confundir com inversão da roupa.

Hipótese: o campo refinado reduz descontinuidades de transporte sem depender de
um volume pareado inválido. Não há evidência ainda de que preserve sozinho o
volume de roupas largas, separe membros ou elimine os problemas de ombro.

## Validação executada nesta rodada

```powershell
python scripts/audit_exact_prism_validity.py
python -m pytest tests/test_experimental_prism_validity.py tests/test_experimental_prism_constraints.py tests/test_experimental_shell_clearance.py tests/test_experimental_canonical_radial.py tests/test_multi_influence_shell.py tests/test_wrap_layer_fit.py tests/test_clothing_uv_cage_mapping.py tests/test_volumetric_cage.py -q -p no:cacheprovider
```

44 testes passaram. O teste novo inclui uma dobra entre t=0 e t=0,5 que a antiga
grade não detecta, reflexão, escala e comparação com amostras aleatórias.
O interpolador refinado acima **ainda não foi implementado**. O código entregue
nesta investigação é o guard experimental e a auditoria analítica; produção
preservada. O ensaio do guard continua rejeitado.

## Critério de rejeição da própria proposta

Astra: qual evidência faria rejeitar esta proposta? Rejeitar se o campo não
reproduzir transformações simples, se apresentar saltos nos seams, se melhorar
arestas mas piorar penetração/volume em qualquer controle, ou se o refinamento
apenas convergir para o mesmo encaixe errado. Não promover uma melhora visual
isolada a compatibilidade universal. Se o bloqueio continuar na outer, registrar
isso explicitamente e não tentar escondê-lo com uma interpolação mais suave.
