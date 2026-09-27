# Etapa 4 — pacote exportado e conferido

## Arquivos gerados

- `assets/models/female_cages_apose_stage2.obj`: 15 cages, UVs por canto e índices de vértices/faces reordenados para a referência R15 local.
- `assets/models/character_female_clean_apose_stage2.obj`: cópia do corpo limpo validado; a malha corporal não mudou nas etapas 1–3.
- `assets/models/female_clothing_package_stage2.json`: manifesto de coordenadas, arquivos e contagens.

## Verificação

`python scripts/verify_stage2_clothing_package.py` relê os OBJ exportados e verifica as 15 partes contra a cena e a referência FBX. As 1.512 posições das cages têm erro máximo de `8.3e-10`; UVs por face têm erro máximo de `5.0e-10`; faces usam exatamente os índices e winding da referência. O carregador OBJ do motor reproduz exatamente as faces trianguladas de referência. O corpo exportado é byte a byte igual ao OBJ corporal anteriormente validado e sua diferença posicional máxima para o Blender é `7.7e-7`.

`python scripts/test_stage2_runtime_clothing.py` passa a camisa em cache `-_office_shirt__BLACK_133331049150205.obj` pelo deformador feminino usando as cages exportadas. O resultado contém 2.269 vértices, 3.726 faces e posições finitas. OBJ de inspeção: `artifacts/clothing_audit/office_shirt_stage2_fitted.obj`.

## Integração pendente

Os arquivos de runtime atuais não foram substituídos. Uma chamada de teste mostrou que o reparo automático por índices em `_repair_female_cages_symmetry` ainda modifica a cage canônica: 143 vértices da cabeça (até 0,363 unidade), 62 da pelve (0,456) e 89 do tronco superior (0,653). **Não aponte o runtime para o pacote novo até remover/substituir esse reparo e rever a associação índice da cage fonte.** O teste da camisa desativou o reparo para isolar o pacote validado.

O teste confirma que o pipeline produz números finitos, não que a silhueta final da camisa ficou perfeita. A etapa seguinte é integrar o mapeamento canônico no deformador e comparar/renderizar uma roupa com o resultado esperado. O pacote é uma exportação interna para o Isometricon; não foi importado nem certificado no Roblox Studio.

## Update � UV binding integrated

The pending integration note above records the state before the UV-binding implementation. Runtime now loads `roblox_reference_cages.obj`, retains reference/target per-corner UVs, and maps target triangles into reference order by UV. `UV_BINDING.md` documents the current path and validation. This establishes cage correspondence; it does not certify visual fit or Roblox Studio compatibility.
