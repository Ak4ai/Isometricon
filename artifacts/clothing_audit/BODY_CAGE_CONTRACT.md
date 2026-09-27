# Checagem do corpo e das cages R15 exportadas

Arquivos efetivamente usados: `assets/models/roblox_reference_cages.obj`, `assets/models/female_cages_apose_stage2.obj` e `assets/models/character_female_clean_apose_stage2.obj`. Execução: `python scripts/audit_body_cage_contract.py`. Dados completos em `BODY_CAGE_CONTRACT.json`.

## Resultado

- As 15 partes da cage têm o mesmo número de vértices, as mesmas faces e os mesmos valores UV que a referência R15 exportada. Todas as faces puderam ser pareadas pela UV. A verificação independente `verify_stage2_clothing_package.py` também confirmou a ordem das faces e UVs por canto contra o snapshot do template, com erro máximo de UV de `5.0e-10`.
- O runtime lê exatamente as posições da cage exportada em todas as 15 partes: diferença máxima zero. Os dois antebraços adicionais presentes no dicionário de runtime são helpers compostos, não partes extras do arquivo R15.
- Distância de cada vértice da cage à superfície da malha visível, considerando o corpo inteiro: máximo 3,00 cm na cabeça; 2,22 cm no torso superior; 2,42 cm no quadril; 2,51 cm no antebraço; 2,20 cm na coxa; 1,98 cm na canela; 1,95 cm nos pés. Esses números são distâncias geométricas, não uma certificação de qualidade visual. Considerar só a malha do torso para medir sua cage elevaria artificialmente o máximo a 4,25 cm na junção com o pescoço.
- A validação de cobertura `stage3_validation.json`, feita no Blender antes da exportação, amostrou 138.802 pontos da superfície do corpo e não encontrou ponto descoberto pela união das cages. Também não relatou cruzamentos próprios, triângulos degenerados ou winding inconsistente nas 15 partes. A verificação da exportação confirmou que o OBJ corresponde ao snapshot validado.

## Conclusão delimitada

Não foi encontrada quebra do contrato básico entre **referência R15, cage feminina exportada e malha visível exportada**. Não há evidência aqui de que faltem vértices, que os UVs tenham sido reordenados ou que a cage esteja amplamente afastada do corpo. Isso desloca a prioridade para o *deformer*, sobretudo a transferência da cage da roupa e a seleção independente de faces/prismas ao vincular a malha visível.

O teste não prova que cada roupa ficará perfeita, nem valida o arquivo `.blend` que possa ter sido editado depois da exportação. Ele também não substitui inspeção de penetração por roupa e por pose.
