# Rastreamento do jeans no runtime feminino — 2026-09-27

## Resultado

O jeans 109837605892174 usa a cage feminina esperada no caminho real de
`RobloxWearEngine.wear()`. As falhas observadas já existem na saída de
`retarget_garment_with_wrap_layer`, antes do espelhamento final, da exportação
OBJ e do parser usado pelo renderizador. Não foi aplicada correção ao motor.

Esta auditoria fecha a dúvida sobre o caminho executado; não descobre um novo
algoritmo nem demonstra que o vínculo atual usa a cage corretamente em sentido
geométrico. Carregar a cage certa e deformar corretamente são coisas distintas.

## Reprodução e escopo

```powershell
python scripts/trace_female_jeans_runtime.py
python scripts/verify_jeans_cage_activity.py
python -m pytest tests/test_wrap_layer_fit.py tests/test_clothing_uv_cage_mapping.py tests/test_character_model.py -q
```

São usados OBJ, PNG, RBXM e cages já locais. A consulta opcional de metadados
online é desabilitada somente no processo de diagnóstico; a classificação local
resulta corretamente em parte inferior, tipo 66. Instrumentação registra chamadas
e copia resultados sem substituir as fórmulas de produção.

Saídas em `female_jeans_runtime/`: `SUMMARY.json`, `runtime.log`, `stages.npz`,
`jeans_fresh.obj`, três imagens individuais e `comparison.png`.
O NPZ contém malha original, cages de origem/alvo, faces de vínculo, índices UV,
saída do wrap e malha final. O JSON inclui hashes para reprodução.
`CAGE_ACTIVITY.json` registra as comparações de caches e o teste de resposta
à cage corporal; os dois arquivos `_decoded_from_mesh.obj` são cópias geradas
na pasta de diagnóstico.

Não foi aberta uma sessão GL. Foi exercitado o parser real com personalização
neutra (glute=1, width=1, waist_offset=0). Configurações da interface em execução
não foram verificadas. As imagens são diagnósticos sem textura, com corpo completo,
mesmas vistas e escala; não reproduzem a ocultação de partes corporais da interface.

## Caminho e exclusão de causas

- `wear_engine.py:753`, `_fit_asset_wrap_layer`: retornou resultado; não houve
  chamada aos fallbacks `fit_bottom_clothing` ou `deform_bottom_mesh`.
- Cage carregada: `assets/models/female_cages_apose_stage2.obj`. A verificação
  anterior `FEMALE_CAGE_PROVENANCE_CURRENT.json` compara suas 15 partes com o
  runtime, erro zero. Nesta execução, o alvo UV coincide exatamente com o fixture
  feminino, assim como a roupa de entrada e a saída de produção congelada.
- O cache existente é v5, rejeitado por `character_model.py:1004`,
  `is_valid_v2_obj`. O OBJ novo é v7 e aceito. Porém, as geometrias diferem no
  máximo 0,00000849 m: o cache antigo não explica este defeito. O arquivo antigo
  foi preservado, confirmado por SHA-256.
- As cages do asset também são armazenadas como OBJ. Reconverti seus `.mesh`
  locais com o decodificador atual: ambos os OBJs produzidos são idênticos,
  byte a byte, aos respectivos caches usados pelo wrap. Isso exclui OBJ de
  cage desatualizado em relação aos `.mesh` locais nesta execução; não verifica
  o estado remoto atual do asset Roblox.
- O módulo importado pelo processo é o arquivo `src/clothing/wrap_layer_fit.py`
  deste workspace; seu SHA-256 coincide com o gravado pelo rastreamento anterior.
  Repetir o fit sobre a malha de origem reproduz a saída registrada, erro zero.
  Ao deslocar **apenas em memória** toda a cage corporal +0,01 m em X, todos os
  vértices vestidos também se deslocam +0,01 m em X, erro máximo de 0,000000021 m.
  Isso comprova que o algoritmo executado usa as posições dessa cage. O teste
  não comprova que as influências escolhidas estejam corretas.
- Saída de `wear()` coincide exatamente com wrap seguido do espelhamento X
  documentado. Exportação e `character_model.py:758`, `parse_obj_as_mesh`,
  introduzem no máximo 0,00000849 m, compatível com arredondamento do OBJ.

## Dois exemplos concretos

### Transição pelve–coxa

Aresta entre os vértices 2396 e 2397: alongamento normalizado de **23,6659×**.
Os vínculos selecionam as faces `[1329,1328,1331]` e `[2934,2935,2936]`.
Os rótulos majoritários dos charts UV são LowerTorso e RightUpperLeg.
Não se trata da cage do pé.

Aplicando as duas transformações ao mesmo ponto médio da aresta original,
as previsões divergem **0,164334 m**. Os resíduos transportados em cada extremo
têm magnitude pequena em relação à separação entre os apoios na cage alvo.
O JSON guarda apoio, resíduo e reconstrução de ambos os vértices; erros de
reconstrução inferiores a 0,00000003 m confirmam a localização do cálculo.

Isso demonstra incompatibilidade local entre as previsões usadas por vértices
vizinhos. Não isola, sozinho, quanto vem da construção da outer alvo, da seleção
da face ou do frame local. Portanto, não justifica declarar que apenas trocar
o seletor de face resolverá.

### Ponta abaixo da bota

Vértice 1464, face `[5290,5291,5292]`, chart RightFoot:

- Apoio na outer alvo: Z = +0,004768 m.
- Todos os vértices dessa face estão acima de Z = +0,002541 m.
- Componente vertical do resíduo transportado: **−0,160864 m**.
- Posição final: Z = **−0,156096 m**.
- Mínimo Z do corpo usado na comparação: −0,025249 m.

Portanto, neste vértice, o deslocamento abaixo da sola é introduzido pelo termo
que transporta a distância até a cage, não pela altura do triângulo de apoio.
A distância original até a face selecionada é 0,224813 em unidades da origem;
não confundir esse valor com metros no corpo alvo.

O cálculo responsável é `wrap_layer_fit.py:367`:
`barycentric @ target_triangle + _local_map(...) @ (point - projection)`.
O frame vem de `_local_map`, linha 199. Ainda não se isolou se a escolha dessa
face ou seu frame é a causa anterior do resíduo inadequado.

## Validação que deixa o defeito passar

O gate em `wear_engine.py:763` verifica distância mediana/p99 à cage e p99 de
alongamento das arestas da própria outer. Esta peça passa: mediana 0,04610,
p99 0,16908, outer p99 1,5255; zero arestas da outer acima de 3×.

Apesar disso, a roupa final tem **584 arestas acima de 3× após normalização pela
escala** e 7,6532% de amostras dentro do corpo. São vértices e centros de faces,
não percentual de área. O cache arredondado tem 585 arestas, por cruzamento do
limiar numérico; a geometria é essencialmente igual.

Os valores antigos de 33 arestas não são diretamente comparáveis: eram razões
sem a mesma normalização. Não houve piora de 33 para 584 nesta auditoria.

## Relação com o histórico e decisão

`JEANS_FOOT_BINDING.md` já descrevia falhas no quadril e pontas na bota, e já
rejeitou excluir o pé: esta roupa contém botas e a exclusão piora o encaixe.
As experiências radiais/prisma também já melhoraram alguns resultados sem
passar em todos os controles. Esses métodos continuam isolados; o caminho
de produção auditado aqui ainda vincula cada vértice a uma única face externa.

O avanço desta etapa é ligar esses defeitos ao caminho atual, afastar cache e
exportação como causas nesta peça e fornecer vértices, faces e decomposições
reproduzíveis. Repetir a auditoria de procedência ou remover novamente a cage
do pé não é o próximo passo indicado.

Próximo critério: usar estes mesmos exemplos para decompor a melhor experiência
radial/prisma já existente e verificar quais falhas ela realmente remove e quais
mantém. Uma alteração posterior precisa tratar a divergência pelve–coxa e o
resíduo da bota sem regredir os seis controles. Não trocar o runtime por uma
variante que apenas melhora a contagem agregada de arestas.

**Estado: diagnóstico concluído; sistema ainda não aprovado como universal.**
Nenhuma remodelagem no Blender é justificada por esta auditoria isoladamente.

## Testes

28 testes direcionados passaram em 2,10 s. Houve somente aviso de permissão
para gravar o cache do pytest; não afetou a execução dos testes.

Evidências que rejeitariam este diagnóstico: wrap intermediário sem os defeitos
com falhas surgindo apenas no parser; execução real caindo em outro ramo; alvo
carregado diferente do export esperado; ou reconstrução dos vértices citados
incompatível com a saída. Nenhuma ocorreu nesta execução. Esta conclusão tem
escopo de um asset, corpo feminino e personalização neutra.
