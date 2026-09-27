# Auditoria radial canônica — 2026-09-26

**Decisão: ainda experimental, rejeitada para integração.** Foram executados os seis controles. A candidata corrige invariâncias da representação da cage, mas piora casos já melhores no radial anterior. O runtime e os arquivos existentes de modelagem não foram alterados nesta rodada.

[Abrir os seis comparativos e métricas](radial_frames/index.html). Cada imagem tem produção / radial anterior com prisma / candidata com o mesmo prisma, em frente, lado, costas e 3/4. Câmera e escala isotrópica são iguais entre variantes de cada caso. O corpo inteiro entra no enquadramento. Sem texturas, iluminação ou backface culling: uma mancha bege é o corpo vencendo o depth buffer; não é uma normal escura.

## O que foi auditado

Foram consultados `RADIAL_SHELL_DECISION.md`, `WRAP_FRAME_EXPERIMENTS.md`, `UNIVERSAL_WRAP_REVIEW.md` e seus relatórios, em particular `WRAP_CONTRACT_AUDIT.json`, `WRAP_BINDING_CHARTS.json`, `WRAP_CHART_TRANSITION_CONSISTENCY.json`, `WRAP_OUTER_CAGE_CLEARANCE.json`, `WRAP_DUAL_PRISM.json`, `WRAP_RADIAL_SHELL_1.json` e `WRAP_RADIAL_BLOCKY.json`. Os resultados de affine, chart blend, Poisson, shell global/adaptativo e inner binding não foram promovidos a soluções aceitas.

Código relevante:

- `src/clothing/wrap_layer_fit.py:retarget_garment_with_wrap_layer`: correspondência entre cages por UV; transferência da casca; uma face por vértice visível. `_local_map` ainda possui dependência da primeira aresta e limites de escala.
- `src/clothing/multi_influence_shell.py:_neighborhoods`, `_rotation`, `transfer_outer_cage_radial`: vizinhanças por índices brutos, rotação por vetores de posição, escala por razões dos eixos dos bounding boxes, busca espacial radial sobre a outer original.
- `scripts/experiment_dual_cage_prism.py:closest_prism_binding`, `bind_dual_cage`: escolha independente de prisma e transporte de residual por `_local_map`. Nenhuma restrição contra entrar em outra parte do corpo.
- `scripts/test_r15_shirt_transfer.py:depth_preview`: visibilidade na câmera, não teste de volume corporal.

Os contratos já verificados da cage feminina continuam sendo evidência de correspondência e cobertura corporal. Não demonstram que uma casca de roupa transferida cubra o corpo, nem que o volume interpolado entre cages seja válido.

## Defeito mínimo reproduzível encontrado no protótipo radial

A superfície da cage precisa representar a mesma deformação quando apenas os índices do OBJ mudam por separação de UVs/normais. O radial anterior não satisfaz isso.

Na camisa, há 4.895 posições carregadas e 1.709 identidades UV. O algoritmo anterior trata cópias como amostras independentes e calcula rotações com listas incompletas de faces/vizinhos. No jeans e vestido, são 5.410 posições para as mesmas 1.709 identidades; na jaqueta já são 1.709. O suéter possui ainda duas identidades sem face na superfície de projeção; elas não devem influenciar o campo físico.

Controle causal: conservar posições, faces geométricas, alvo, raio e escala antigos, mudando somente para índices canônicos por UV. A maior diferença na casca resultante foi:

| Caso | Diferença máxima em coordenadas do alvo |
|---|---:|
| Camisa feminina | 0,027746 |
| Jaqueta feminina | ~6,7e-16 |
| Jeans feminino | 0,113773 |
| Vestido feminino | 0,106170 |
| Suéter feminino | 0,410046 |
| Camisa Blocky | 0,141461 |

Esses valores estão em `radial_frames/*<asset>.json:old_encoding_dependence`. Não são todos metros. No suéter, essa comparação inclui o problema dos índices sem faces; não isola somente duplicação.

Isso é **um defeito provado**, mas **não é a causa única de todos os recortes**. Os pontos com mesmo UV já terminavam coincidentes no radial anterior. A mudança afeta o campo e os pesos; não prova que cópias do OBJ abriam costuras. Também é diferente da análise antiga sobre índices separados da malha visível: aqui examinamos as cages usadas para gerar rotações e influências.

A escala antiga também depende da orientação dos eixos. Para camisa feminina / Blocky, sua estimativa é 0,37555 / 1,23787; a razão RMS das posições correspondentes é 0,33469 / 1,00415. RMS não é automaticamente a escala física ideal, mas permanece invariável sob rotação. Os testes antigos de rotação fixavam `bulk_scale=1` e não testavam essa escolha automática.

## Uma proposta implementada e seus limites

Novo módulo isolado: `src/clothing/experimental_canonical_radial.py`.

1. `canonical_cages`: reúne somente identidades UV iguais, valida posições correspondentes e reconstrói incidência. Não junta pontos só porque se encostam no espaço.
2. `normal_frames`: usa normais das faces adjacentes correspondentes e SVD, com paridade explícita.
3. `transfer_canonical_radial`: mantém raio igual à espessura e a busca espacial sobre a outer original; uma amostra por identidade UV. Pontos de armazenamento sem faces ficam excluídos das influências.
4. O experimento conserva o vínculo por prisma e seu residual, permitindo comparar a substituição da etapa da casca.

**Publicado:** a [patente US20250265799A1, figuras 21–24](https://patents.google.com/patent/US20250265799A1/en) descreve busca radial na outer original, alcance ligado à espessura, pesos, rotações calculadas com normais adjacentes/SVD e escala global. Também reconhece cruzamentos em saias e possíveis interseções durante a interpolação. Isso não publica necessariamente o runtime atual do Roblox.

**Aproximações nossas:** amostragem por identidade UV; normais unitárias; regularização de 1e-6 com direções de arestas para determinar a rotação em regiões planas; escala RMS; normalização dos pesos por fonte e depois por destino; tratamento de vértices sem faces. O prisma é nosso controle geométrico, não uma implementação demonstrada pela patente.

**Hipótese testada:** remover dependência de exportação e usar essas rotações melhoraria os seis casos sem perder cobertura/forma. Essa hipótese, como solução de integração, foi rejeitada. O teste combina a correção de representação, a política de escala e a construção de frames; não atribui todas as regressões exclusivamente às normais ou à escala.

## Resultados dos controles

Valores abaixo: **radial anterior → candidata**. A escala RMS de cada caso é a mesma para comparar os três métodos. O resumo completo com produção está em `radial_frames/SUMMARY.json`.

| Caso | Arestas >3× após normalizar escala | Faces com área <10% esperada | Amostras dentro de componentes fechados do corpo | Vértices vinculados em volume local invertido |
|---|---:|---:|---:|---:|
| Camisa feminina | 149 → 150 | 7 → 8 | 2,30% → 2,25% | 83 → 78 |
| Jaqueta feminina | 116 → 137 | 2 → 3 | 1,93% → 2,31% | 54 → 114 |
| Jeans com botas | 76 → 64 | 50 → 108 | 2,15% → 11,20% | 172 → 629 |
| Vestido | 190 → 220 | 9 → 3 | 1,57% → 1,58% | 165 → 210 |
| Suéter | 43 → 47 | 4 → 19 | 3,47% → 4,55% | 319 → 558 |
| Camisa Blocky | 957 → 952 | 1 → 9 | 27,82% → 22,67% | 263 → 288 |

Visualmente, o jeans apresenta novas exposições do corpo na cintura, o vestido desenvolve uma ponta na barra, e o suéter ganha irregularidades nas mangas/punhos. A jaqueta perde parte da qualidade do controle radial anterior. A camisa feminina muda pouco. O Blocky mantém recortes visíveis nas mangas/ombros. Portanto, não há aprovação baseada apenas na redução de algumas arestas.

As contagens antigas 1/1/0/9/0 e 972 eram razões em unidades brutas. As contagens desta tabela foram normalizadas pela escala; não constituem uma piora artificial causada por alterar a malha entre medições. O JSON também conserva quantis e o conjunto de todas as arestas não degeneradas, além do filtro histórico de comprimento original >=0,01.

As cópias com mesmo UV e os grupos coincidentes da outer terminam com dispersão de ordem 1e-16 nas duas variantes radiais. Isso **não garante** continuidade entre pontos não coincidentes, nem identifica quais contatos são costuras intencionais. A consistência desses grupos não é o bloqueio restante principal.

## Falha localizada no Blocky: antes e depois do residual

Evidência: `radial_frames/BLOCKY_CLEARANCE_WITNESSES.json`, gerado por `scripts/audit_blocky_clearance_witness.py`.

**Vértice 377, vinculado a LeftUpperArm:** o ponto na cage interna alvo está em x≈1,000; o ponto interpolado na outer transferida está em x≈0,923818. A outer já entra no `UpperTorso_Geo`. Com t≈0,96011, o ponto do prisma, antes de adicionar residual, está dentro do tronco. O residual de origem é somente ~8,48e-12. Logo, trocar a projeção residual ou melhorar a continuidade da malha visível não conserta esse exemplo: o volume alvo já é inadequado.

**Vértice 1486, vinculado a RightUpperArm:** tanto o ponto interno quanto o externo e o ponto prismático sem residual ficam fora do braço. O binding escolhe t=0, e o residual de origem (~0,027799) transformado por `_local_map` leva o resultado para dentro de `RightUpperArm_Geo`, com distância à superfície de ~0,035293. Aqui há uma falha adicional de extrapolação da malha, mesmo com fronteiras locais fora do corpo.

**Vértice 93, vinculado a UpperTorso:** o ponto interno tem x≈1,000; o externo x≈1,139; o resultado chega a x≈1,126 e penetra a região do braço vizinho. Ser exterior à parte do tronco não significa ser exterior à união do corpo.

Nos 595 centros de faces de cage efetivamente usados pela camisa, o alvo interno tem 10 amostras dentro do corpo, com profundidade máxima de ~0,19% da altura. A outer candidata tem 107, com profundidade máxima de ~2,83% da altura. A inadequação aumenta durante a transferência da casca; não há evidência para culpar somente a cage original do usuário. A leitura FBX ainda ignora transformações de hierarquia, conforme a auditoria anterior; as medidas se referem ao corpo carregado pelo programa.

**Menor bloqueio agora demonstrado:** a transferência e o binding não impõem validade geométrica em relação ao corpo alvo completo. Rotação local, correspondência UV e continuidade de alguns pontos não impedem que a casca de uma parte entre em outra; o residual também pode atravessar uma fronteira válida. Não existe evidência de uma única alteração de UV/frame capaz de resolver os dois mecanismos.

O próximo avanço deve ser julgado pela eliminação desses exemplos concretos: exterioridade do volume que realmente conduz os vértices da roupa, seguida de exterioridade do ponto extrapolado. Não iniciar outra varredura de raio ou regras por categoria. A construção exata desse campo com restrições ainda não foi implementada nem demonstrada aqui; não seria honesto chamá-la de solução pronta.

## Como interpretar as medidas

- `scripts/radial_validation_metrics.py:distortion`: comprimentos divididos por s, áreas por s². O indicador de orientação compara normais com frames da inner; é um **proxy**, não uma contagem comprovada de faces inválidas.
- `prism_jacobians`: determinante assinado do volume pareado, descontando paridade. Há auditoria em 12 posições por face e no ponto de binding de cada vértice. Degenerações de origem são excluídas. Inversão local do volume não equivale automaticamente a face da roupa visivelmente invertida; ausência de inversão amostrada tampouco prova injetividade global.
- A coluna de prismas em produção é **contrafactual**, porque produção usa uma face externa, não esse binding. Para as duas variantes experimentais ela mede os prismas efetivamente usados.
- `body_penetration`: vértices e centroides da roupa, winding absoluto por componente fechada do corpo e distância ponto/triângulo. Tolera contatos até 1e-4 da altura. Não une partes distintas por coincidência nas juntas. Há duas componentes abertas em cada corpo; os candidatos nelas são separados. A amostragem não é ponderada por área, inclui cópias e possíveis forros, e não certifica ausência de interseções entre amostras. Os percentuais não são porcentagem da superfície visível descoberta.
- A primeira rodada do medidor unia partes nas juntas e subestimava penetração. Todos os JSON finais foram recalculados com `measurement_version=2`; os números desta decisão são os corrigidos.
- `visibility`: fração da silhueta projetada da roupa que vence o depth buffer, nas quatro vistas. Braço nu à frente de uma roupa também a oculta. Serve como comparação visual, não como prova de cobertura de regiões que deveriam estar vestidas.

## Reprodução e testes

Executar na raiz, com os assets locais já presentes:

```powershell
python scripts/audit_radial_frames.py
python scripts/experiment_canonical_radial.py
python scripts/audit_canonical_radial_results.py
python scripts/audit_blocky_clearance_witness.py
python scripts/summarize_canonical_radial.py
python -m pytest tests/test_experimental_canonical_radial.py tests/test_multi_influence_shell.py tests/test_wrap_layer_fit.py tests/test_clothing_uv_cage_mapping.py tests/test_volumetric_cage.py -q -p no:cacheprovider
```

Resultado executado: **33 testes passaram**. Incluem transformação rígida arbitrária com escala automática, reflexões, escala uniforme, invariância à separação de índices e ordem de faces/cantos, rejeição de posições conflitantes por UV, exclusão de linhas sem faces e controles do medidor de penetração/Jacobiano. Há teste que reproduz a dependência de índices do algoritmo anterior. Não são prova de bom caimento.

`radial_frames/MANIFEST_SHA256.json` registra arquivos de código e assets; `*_outputs.npz` contém as três malhas e cascas; os bindings de origem são reutilizados somente quando o hash da geometria e do script de vínculo confere. Não houve download, mudança no Blender, troca de algoritmo de produção ou ajuste por nome de roupa.

## Evidência de rejeição da própria proposta

Pergunta para o Astra na revisão: **“Qual evidência faria você rejeitar sua própria proposta, mesmo que as arestas melhorassem?”**

Neste experimento, a resposta já tem exemplos: a penetração do jeans cresce de 2,15% para 11,20%, suas faces comprimidas passam de 50 para 108, o volume local invertido afeta mais bindings e as imagens mostram novas exposições na cintura. Isso rejeita a candidata como substituta do radial anterior. Corrigir a dependência de exportação permanece uma melhoria de contrato matemático; não autoriza integrar este conjunto de políticas como vestimenta universal.
