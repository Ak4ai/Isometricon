# Deslize de correspondências: funciona no recorte aberto, insuficiente para manga fechada

2026-09-27. Experimental, sem alterações no runtime/modelos.

[Antes/depois do recorte](surface_slide/open_contact_comparison.png) ·
[Controle fechado](surface_slide/closed_contact.png) · [Métricas](surface_slide/SUMMARY.json).

`src/clothing/experimental_surface_slide.py` implementa um QP com conjunto ativo
em NumPy. Variáveis são as coordenadas angulares de associação sobre uma superfície
cilíndrica de raio 0,24, com offset normal fixo de 0,05. Não desloca a outer cage
nem chama o corretor posterior antigo. Coordenadas axiais ficam fixas; todas as
fileiras compartilham as associações angulares pela simetria do fixture.

O objetivo penaliza afastamento da correspondência inicial e variação entre
deslocamentos vizinhos. Restrições limitam variação angular de arestas a 10% e
mantêm os pontos no arco exterior a um segundo cilindro, raio 0,30, distância
0,50 entre eixos. O domínio livre é calculado geometricamente com margem 0,002.
A inicialização viável é uma translação angular rígida obtida desse domínio;
não recebe uma malha-resposta. É uma formulação restrita ao controle analítico,
não um solver geral em triângulos, UVs R15, curvas arbitrárias ou camadas.

## Resultado do teste aberto

17 coordenadas angulares de 0,05 a 0,85 radianos; 13 fileiras axiais. As bordas
do recorte estão livres. O solver converge em 18 iterações. Nas 1209 amostras
(vértices, meios de arestas e centros de triângulos):

- Penetração: 777 → 0.
- Folga mínima ao vizinho depois: 0,002 unidade.
- Comprimento das arestas: entre 90,0018% e 100% do original.
- Área mínima: 90,0018% da original.
- Offset normal preservado, erro ~7e-17.
- Deslocamento máximo de um vértice: 0,15134 unidade.

A melhora exige mover o recorte significativamente (deslize angular máximo
0,528 rad). Não demonstra que uma camisa com bordas/costuras vinculadas aceite
esse movimento. Sem contato, o controle permanece idêntico ao original.
As amostras não certificam colisão contínua de toda a superfície.

## Controle fechado e critério de parada

Uma manga fechada que continua envolvendo o braço percorre todos os ângulos
da seção. No raio fixo de 0,29 existe um intervalo angular ocupado pelo vizinho.
Uma reparametrização tangencial contínua, preservando esse enrolamento, não
pode omitir o intervalo. O domínio viável sob essas hipóteses é vazio; não foi
executada uma otimização fingindo que existia solução. A malha inicial tem
419 amostras penetrantes de 2368.

Isso não prova impossibilidade de vestir o personagem: permitir outro apoio,
offset variável, deslocamento axial fora do contato ou outra configuração do
corpo muda o problema. Prova apenas que **deslizar na mesma superfície com offset
fixo não basta para uma manga fechada neste contato**. Portanto o gate completo
reprova; não levamos este solver ao Blocky e não o chamamos de solução universal.

## Reprodução

```powershell
python scripts/experiment_surface_slide.py
python -m pytest tests/test_experimental_surface_slide.py -q -p no:cacheprovider
```

4 testes novos passaram; a suíte direcionada completa passou com 66 testes.
NPZ preservam corpo, faces, malha inicial/final e coordenadas de associação.
JSON registra parâmetros, métricas, convergência e hashes. A revisão visual
confirma que o recorte passa a ficar exposto na vista de costas; nas outras
vistas o corpo pode ocluir o recorte, sem isso significar penetração.

Durante esta rodada o usuário perguntou se sua cage feminina é realmente usada.
Foi feita uma checagem atual independente em `audit_female_cage_provenance.py`:
loader abre `female_cages_apose_stage2.obj`, as 15 partes coincidem com o export
e os alvos dos cinco fixtures femininos coincidem por UV com a cage atual, todos
com erro máximo 0,0. Ver `FEMALE_CAGE_PROVENANCE_CURRENT.json`. Essa confirmação
não valida associação/influência da roupa, cache da interface ou cena Blender atual.
