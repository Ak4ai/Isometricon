# Revisão de composição dos experimentos de vestimenta

Data: 2026-09-27. Revisão dos resultados existentes; nenhum deformer foi integrado ou reexecutado. Este documento distingue conclusões atuais de relatórios históricos com métodos, máscaras de aresta e escalas diferentes. Não comparar contagens antigas diretamente com o conjunto normalizado `radial_frames`.

## Resposta

Há componentes aproveitáveis, mas **os resultados arquivados não sustentam que encadeá-los produza um sistema universal**. A melhor composição offline já inclui transferência radial da cage externa e vínculo volumétrico por prisma. O experimento posterior de vínculo coerente acrescenta uma correção local. O bloqueio dominante do Blocky está antes ou fora dessa escolha local: a outer transportada pode entrar na parte vizinha e o resíduo da malha pode entrar no próprio braço. Uma correção posterior precisa preservar ao mesmo tempo contato, continuidade da superfície, forma da roupa e validade do volume; os corretores que tentaram proteger subconjuntos dessas propriedades reprovaram.

## Matriz por etapa

| Etapa | Resultado reaproveitável | Combinação/limite já verificado | Decisão |
|---|---|---|---|
| Entrada e correspondência | `ReferenceOrigin`, `CageOrigin`, cages do asset, UVs correspondentes e paridade de reflexão; controle de identidade reproduz roupa original. Cage feminina carregada coincide com export. | Camisa no Blocky usa a mesma roupa, referência, outer e vínculo de origem do caso feminino. FBX/pose e transforms dos testemunhos Blocky não revelaram deslocamento grande omitido. | Conservar; não atribuir recortes remanescentes a cache, ordem bruta de vértices ou alinhamento global sem novo testemunho. |
| Junções da cage feminina | Os 15 layouts UV, topologia e cobertura amostrada passaram na validação. | `BODY_JOINT_SEAMS.json` ainda registra 45/137 grupos compartilhados da referência abertos mais de 2 cm no alvo, com abertura relevante nos tornozelos e ombro. Cobertura do corpo não certifica continuidade entre partes. | Correção localizada no Blender pode ajudar roupa feminina nessas junções, após classificar quais são costuras reais; não resolve o Blocky oficial nem substitui o deformer. |
| Casca externa | Busca radial por espessura com escala/rotação locais é o melhor controle geral preservado. | Já foi composta com prisma. Part-affine ajudou suéter, mas piorou calça cargo; global affine ajudou saia, mas piorou camisa/jeans; variante adaptativa não passou todos. | Não selecionar campo por nome da peça nem misturar saídas. Falta transporte que preserve contato e forma simultaneamente. |
| Vínculo visível | Prisma pareado removeu ponta de bota e reduziu quebra pelve/coxa; vínculo coerente corrige outra aresta 734–737 de 7,45× para 0,99×. | Ambos ainda deixam Blocky com 938 arestas normalizadas >3× e 27,81% de amostras penetrantes, além de falhas visuais em ombro e vestido. O one-ring e chart blend anteriores já provaram que consertar arestas locais não basta. | Preservar como candidato offline; não habilitar por melhora de um testemunho. |
| Campo alternativo | Campo refinado reduziu esticamento de arestas e global affine preservou melhor a silhueta de algumas saias. | Refinado nível 0 no Blocky: 957→422 arestas >3×, mas penetração 27,82%→35,85%; nível 2 falha em reproduzir controles da cage com erro p99 8,55% da altura. Suavidade sem fidelidade não é correspondência correta. | Rejeitar substituição ou blend automático com o radial. |
| Contato/volume | União das partes corporais, medidor de penetração e limites analíticos de Jacobiano fornecem critérios úteis. | Corretor da shell: penetração 27,82%→11,59%, mas arestas 957→1100 e células invertidas aumentam; guard de prisma: 27,82%→25,40%, arestas 957→1053, ombros ainda falham. | Reaproveitar os critérios de auditoria, não os deslocamentos resultantes. |
| Pose/camadas | Preservar skinning, `BindOffset` e `WrapLayer.Order` é necessário para escopo maior. | OBJ atual descarta skinning; papel da bind pose no suéter está pendente. Isso não explica os testemunhos estáticos 93/377/1486 do Blocky já rastreados. | Tratar como capacidade separada, não remendo para ombro estático. |

## A camisa que parecia boa

`CAGE_NORMAL_ORIENTATION_AUDIT.md` mostrou melhora real ao corrigir a paridade: a camisa saiu de dentro do tronco e a vista frontal ficou majoritariamente azul. Esse reparo foi incorporado. As imagens `blocky_r15_office_shirt_baseline_depth.png` e `coherent_prism/blocky_133331049150205_comparison.png` ainda mostram aberturas de ombro/lateral. `blocky_r15_office_shirt_baseline_transfer.png` usa corpo transparente e pode sugerir encaixe melhor do que a imagem com depth buffer. O teste separado no ClassicMannequin, em `R15_REAL_SHIRT_TRANSFER.md`, nem era o Blocky oficial. Portanto não há um resultado arquivado de camisa Blocky aprovado que esteja esperando apenas ser combinado.

## Bloqueio geométrico, com testemunhos

Em `BLOCKY_INFLUENCE_DECISION.md`, 345 vértices penetrantes não recebem influência de outra parte na outer; remover influências cruzadas não altera os testemunhos principais. O vértice 377 (LeftUpperArm) já está dentro do torso no prisma antes do residual, e 93 (UpperTorso) entra no braço vizinho. O vértice 1486 parte de um prisma externo, mas o residual transportado entra no próprio braço. `BLOCKY_TARGET_PLACEMENT_DECISION.md` verificou que diferenças de transform e bind pose dos objetos inspecionados são pequenas e que deslocar os pontos 93/377 pela direção atual não encontra espaço livre. `DEFORMATION_METHOD_REVIEW.md` detecta 75/595 células prismáticas usadas com sinal misto após transferência radial, contra zero na origem para essa camisa. Estes resultados não provam impossibilidade de um fitter, mas rejeitam a ideia de que uma escolha local de face ou um offset global faltante resolva todos os ombros.

## O que realmente se pode combinar agora

1. **Contrato de entrada já validado:** origins, UVs por identidade de superfície, paridade e proveniência da cage. Manter testes de identidade, reflexão, pose e hashes.
2. **Candidato de base para investigação:** radial + prisma + vínculo coerente, sempre isolado do runtime. Ele contém as melhores correções locais demonstradas para jeans e serve para comparar um novo método, não como saída final.
3. **Critérios de aceitação, não pós-processadores:** amostragem contra a união corporal, validade do volume, área/orientação da malha, continuidade de seams e imagens nas mesmas quatro vistas. Validar primeiro os testemunhos 93/377/1486 no Blocky e 734–737 no jeans; depois os seis controles completos.

Uma próxima implementação só vale se modificar o **modelo conjunto de transporte**: o campo que leva a shell e o residual da roupa deve respeitar a identidade da superfície e a fronteira externa da união corporal, preservando a forma e a orientação da roupa. Isso pode exigir redistribuição tangencial, afastamento variável ou outro domínio; o deslize tangencial com offset fixo já falhou para manga fechada em `SURFACE_SLIDE_DECISION.md`. Não há fórmula comprovada aqui para integrar. O primeiro gate de qualquer formulação nova é eliminar os três testemunhos Blocky sem aumentar esticamento, compressão, inversão ou perder cobertura. Se falhar, parar antes de repetir seis prévias.

## Fontes decisivas

- `UNIVERSAL_WRAP_REVIEW.md`, `WRAP_LAYER_RUNTIME.md`, `BODY_CAGE_CONTRACT.md`, `SOURCE_OVERLAY_DECISION.md`: entrada, convenções e limitações do runtime.
- `GENERAL_CAGE_DEFORMATION_DESIGN.md`, `BODY_JOINT_SEAMS.json`: aberturas de junção no corpo feminino que sobrevivem à validação de cobertura.
- `WRAP_FRAME_EXPERIMENTS.md`, `RADIAL_SHELL_DECISION.md`, `CANONICAL_RADIAL_REVIEW.md`, `COHERENT_PRISM_DECISION.md`: shell, vínculo e controles fixos.
- `BINDING_DIAGNOSIS.md`, `DRESS_JEANS_REVIEW.md`, `JEANS_FOOT_BINDING.md`: resultados anteriores e o que já foi tentado.
- `REFINED_REFERENCE_DECISION.md`, `SHELL_CLEARANCE_DECISION.md`, `PRISM_CLEARANCE_DECISION.md`: regressões ao trocar campo ou corrigir contato depois.
- `BLOCKY_INFLUENCE_DECISION.md`, `BLOCKY_TARGET_PLACEMENT_DECISION.md`, `DEFORMATION_METHOD_REVIEW.md`: causas localizadas e limites de volume.
- `SYNTHETIC_ARM_DECISION.md`, `SYNTHETIC_CONTACT_DECISION.md`, `SURFACE_SLIDE_DECISION.md`: controles sintéticos e limites de generalização.

Conclusões de `PROGRESS.md`, `STAGE3.md`, `STAGE4.md` e `UNIVERSAL_FIT_AUDIT.md` anteriores à integração de WrapLayer/UV são históricas; não tratá-las como descrição do runtime atual quando relatórios posteriores as corrigem.
