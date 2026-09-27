# Decisão: os testemunhos exigem tratamento geométrico de contato, não reposicionamento do FBX

2026-09-27. Auditoria somente de leitura; não houve novo fitting nem alteração de modelos.

[Cortes geométricos nos três pontos](blocky_target_placement/sections.png) ·
[Dados e hashes](blocky_target_placement/SUMMARY.json).

## Pergunta fechada nesta rodada

As colisões nos vértices 93 e 377 poderiam ser explicadas por omissão de
transformações, montagem incorreta dos braços ou diferença entre a pose atual
e a bind pose do Blocky? Nos objetos e testemunhos examinados, **não**.
Há transformações pequenas ignoradas pelo leitor antigo, mas aplicá-las não
elimina o contato interno nem cria espaço para a direção de transporte usada.

Isso não é uma certificação do importador FBX inteiro, de toda pose ou de todos
os modelos. O leitor de auditoria aceita apenas os recursos efetivamente
necessários neste arquivo e rejeita transformações não suportadas.

## Evidências de montagem e pose

`scripts/audit_blocky_target_placement.py` inspeciona UpperTorso e ambos os
UpperArm/LowerArm, com suas meshes e outer cages. Os dez objetos de geometria
são filhos da raiz. A hierarquia dos ossos é reconstruída usando somente
conexões com Models: ligações OO para skin clusters não são tratadas como pais.

- 1633 entradas da cage congelada foram comparadas por UV diretamente com o FBX.
  Diferença máxima: **7,57e-10** nas coordenadas convertidas para o motor.
- Aplicar as transformações de objeto ignoradas muda as cages selecionadas em
  no máximo **0,000861531** unidade. Isso é principalmente uma translação vertical.
- As matrizes globais atuais dos cinco ossos diferem das bind poses armazenadas
  em no máximo **3,28e-7** por elemento. Não aparece uma rotação grande de braço
  omitida entre essas poses.

O código calcula transformações locais, hierarquia e compara as matrizes de
bind pose. Não faz uma avaliação geral de skinning, constraints ou animações.
As diferenças pequenas foram incorporadas aos probes da geometria nesta rodada.

A especificação pública de corpos aceita exportação em I-pose, A-pose ou T-pose;
não é correto declarar inválido o Blocky apenas por estar com os braços baixos.
[Fonte oficial Roblox](https://github.com/Roblox/creator-docs/blob/main/content/en-us/avatar/character-bodies/specifications.md).
Isso não documenta a preparação interna exata que o WrapLayer faz antes do fit.

## Espaço disponível nos pontos problemáticos

Usamos a inner corrigida pelas transformações e os corpos também transformados.
Testamos deslocamentos em X de ±0,001; ±0,005; ±0,01; ±0,04 e a direção efetiva
de transporte da inner para a outer radial. O classificador usa winding nos
componentes fechados; probes são finitos e incluem tolerância superficial.

**Vértice 93, vinculado ao UpperTorso:** ponto x≈1,000000238. Todos os probes
negativos entram no tronco; todos os positivos entram em LeftLowerArm. A
direção efetiva do transporte também entra no braço já no probe de 0,001.

**Vértice 377, vinculado ao LeftUpperArm:** ponto x≈0,999999916. Probes negativos
entram no tronco; positivos entram no próprio braço. A direção efetiva da
expansão entra no tronco já no probe de 0,001.

Esses dois pontos ficam em interfaces internas de contato entre os volumes.
Permanecer no mesmo ponto correspondente e acrescentar espessura para um dos
dois lados testados não produz uma posição exterior à união. Isso **não prova
inexistência de solução em outras direções ou com redistribuição tangencial**.

**Vértice 1486, RightUpperArm:** há espaço na direção exterior, X negativo.
Os probes negativos ficam fora e os positivos entram no próprio braço. A
direção da outer está livre; a falha já identificada acontece no transporte
residual da malha. Portanto não unificamos esse caso artificialmente com os
outros dois: requer uma correção distinta da entrada em outra parte corporal.

## Decisão prática

Não recomendar remodelar o corpo do usuário nem deslocar seus braços como
correção destes testemunhos. Corrigir somente as pequenas transformações
ignoradas não elimina a condição que quebra o transporte.

A rota necessária neste caso é **reformular como o transporte trata contato
entre partes e a malha residual**, distinguindo a superfície de uma parte da
fronteira externa do personagem completo. A correspondência por UV continua
útil, mas não garante espaço livre para expandir cada ponto localmente.

Esta rodada não implementa nem promete um solver novo. O corretor posterior
de colisão já reprovou nos testes anteriores e não deve ser repetido como se
fosse uma proposta nova. Uma formulação futura precisa satisfazer cobertura,
continuidade e volume conjuntamente, incluindo peças que ligam várias partes.

## Limites e critério de rejeição

O diagnóstico cobre cinco partes e três testemunhos; não valida a montagem de
toda a cabeça, pés, acessórios ou offsets de importação de outros assets. A
concordância com o FBX confirma os dados locais usados, não equivalência total
ao estado interno de um personagem no Roblox Studio.

Rejeitar a conclusão de contato interno se outra importação validada desses
mesmos dados/pose demonstrar espaço livre nos probes, ou se for identificado
um estágio obrigatório de preparação que mude tais interfaces antes do fit.
Não atribuir essa preparação ao Roblox sem evidência.

## Reprodução

```powershell
python scripts/audit_blocky_target_placement.py
python -m pytest tests/test_blocky_target_placement.py tests/test_blocky_radial_influence_audit.py tests/test_synthetic_contact.py tests/test_synthetic_wrap_fixture.py tests/test_experimental_refined_reference.py tests/test_experimental_prism_validity.py tests/test_experimental_prism_constraints.py tests/test_experimental_shell_clearance.py tests/test_experimental_canonical_radial.py tests/test_multi_influence_shell.py tests/test_wrap_layer_fit.py tests/test_clothing_uv_cage_mapping.py tests/test_volumetric_cage.py -q -p no:cacheprovider
```

62 testes passaram. Os quatro novos verificam transformação suportada, rejeição
de pivôs/rotações não suportados e interpolação de cortes triangulares. O PNG
mostra cortes XY na altura dos pontos, com a direção 3D projetada em XY; não é
uma renderização de roupa nova. Assets e algoritmo de produção preservados.
