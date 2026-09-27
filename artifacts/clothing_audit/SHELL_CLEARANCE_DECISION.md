# Colisão da cage com o corpo completo — controle Blocky

**Resultado: experimental, rejeitado para integração.** A correção diminui penetração, mas cria pontas laterais e piora a deformação do volume entre as cages. Esse resultado corrige a recomendação anterior: tratar apenas a exterioridade da casca antes do restante do binding é insuficiente.

[Antes/depois da camisa nas quatro vistas](shell_clearance/blocky_133331049150205_garment_comparison.png). [Comparação incluindo as faces de cage usadas](shell_clearance/blocky_133331049150205_comparison.png). Câmera e escala iguais entre os resultados. As linhas de cage mostram somente as 595 faces usadas pelos vínculos da camisa: os espaços entre triângulos também decorrem dessa seleção, não são prova de buracos na cage completa.

## Implementação

`src/clothing/experimental_shell_clearance.py` acrescenta um experimento independente sobre a **casca radial anterior**, que foi um controle melhor que a candidata canônica rejeitada. O vínculo por prisma e o residual continuam idênticos ao controle.

- `ClosedBodyUnion`: considera a união das componentes fechadas do corpo; evita empurrar um ponto para fora do braço e para dentro do tronco. A busca considera projeções nas faces e arestas, rejeitando candidatos que continuem dentro de outra parte. É uma aproximação da menor distância à união, sem garantia de encontrar seu minimizador exato.
- `project_shell_clearance`: distribui as correções dos vértices, centros de arestas e centros de faces pela superfície da cage. Mantém os grupos já coincidentes da casca. Uma busca de passo por variável protege as faces incidentes contra novas reversões em relação à casca inicial e contra área menor que 25% da área inicial.
- Parâmetros fixos em todos os pontos: margem de 1e-4 da altura corporal, 20 iterações máximas, peso de suavização 0,25 e oito passos Jacobi. Nenhuma regra por nome, categoria de roupa ou parte do corpo. São escolhas experimentais nossas, não valores atribuídos ao Roblox.

A primeira execução, com um único passo para a cage inteira, ficou limitada por poucas faces: penetração da camisa 27,82% → 25,24%, centros de cage dentro do corpo 114 → 105. Os artefatos dessa execução estão em `shell_clearance/global_step/`. A busca local permitiu progresso nas outras regiões, produzindo o resultado abaixo. Isso continua sendo o mesmo experimento de restrições de colisão; o controle de passo foi corrigido para não bloquear todas as regiões por uma única face.

## Resultados finais

| Medida | Radial anterior | Correção de colisão |
|---|---:|---:|
| Centros das 595 faces de cage dentro do corpo | 114 | 23 |
| Amostras de superfície de cage dentro do corpo, de 2.075 | 365 | 115 |
| Vértices + centros de faces da camisa dentro do corpo | 27,82% | 11,59% |
| Arestas da camisa >3×, normalizadas pela escala | 957 | 1.100 |
| Faces da camisa com área <10% esperada | 1 | 0 |
| Amostras de volume prismático invertidas, de 7.140 | 334 | 769 |
| Vértices vinculados em volume local invertido | 263 | 414 |

As definições e limitações de amostragem seguem `CANONICAL_RADIAL_REVIEW.md`. Duas componentes corporais abertas são excluídas do teste de interior fechado. Há contagem separada dos candidatos nessas componentes; nenhuma conclusão de ausência global de colisão é feita. A amostragem não mede porcentagem de superfície visível e pode incluir forros.

Verificação visual: a vista frontal fica semelhante; na lateral aparecem saliências novas para frente e para trás. Os recortes nos ombros permanecem. O máximo deslocamento de um ponto da casca chega a 20,45% da altura do corpo. A redução de penetração, portanto, não representa bom caimento.

## Bloqueio demonstrado

`shell_clearance/FAILURE_WITNESSES.json` lista **177 novos vértices vinculados em volumes invertidos**, contra 26 recuperados. Isso acontece mesmo com todas as faces inicialmente válidas da superfície preservando orientação em relação à casca inicial. O menor cosseno entre normais é positivo (~0,000254) e a menor razão de área é ~0,25, confirmando que a trava da superfície funcionou conforme implementada.

Uma superfície externa pode continuar com seus triângulos orientados e ainda fazer o volume que a liga à cage interna dobrar sobre si. A correção proposta não impõe restrições a esse volume nem preserva globalmente os deslocamentos originais de espessura; por isso permite deformações excessivas. A busca pela saída mais próxima também é local, e regiões vizinhas podem preferir saídas diferentes. Esta última é uma limitação do método, não uma prova de que qualquer solucionador de colisões falharia.

**Próximo requisito concreto:** incorporar ao mesmo solucionador a validade dos prismas utilizados e a preservação da forma/espessura, além da colisão. Verificar determinantes nos pontos reais de binding e nos pontos de controle do volume durante a aceitação dos movimentos. Só proteger a superfície externa não satisfaz esse contrato. O residual da camisa continua sendo outra fonte de penetração e não foi alterado nesta etapa.

Não foi demonstrado que essas restrições conjuntas tenham solução para todas as roupas/corpos. A falha deste teste também não justifica remodelar a cage feminina nem atribuir o algoritmo experimental ao WrapLayer original.

## Reprodução e escopo

Partindo dos seis controles congelados em `radial_frames`:

```powershell
python scripts/experiment_shell_clearance.py
python scripts/report_shell_clearance.py
python -m pytest tests/test_experimental_shell_clearance.py tests/test_experimental_canonical_radial.py tests/test_multi_influence_shell.py tests/test_wrap_layer_fit.py tests/test_clothing_uv_cage_mapping.py tests/test_volumetric_cage.py -q -p no:cacheprovider
```

Resultado executado: **37 testes passaram**. Os quatro novos testes verificam saída da união de duas partes encostadas, retirada de uma superfície simples de dentro de um cubo, preservação de superfície já externa e coincidência de cópias exportadas. Esses controles verificam operações do solucionador; não aprovam a geometria real.

`--global-step` reproduz a primeira política de passo. Salve os artefatos atuais antes de usá-lo: o script escreve os resultados do caso no mesmo diretório. Os arquivos originais dessa primeira execução já foram preservados na subpasta `global_step`.

O script aceita identificadores dos outros controles, mas **as cinco roupas no corpo feminino não foram executadas nesta rodada**: o controle Blocky falhou nos critérios de forma e volume. Nenhum algoritmo de produção, arquivo Blender ou experimento anterior foi substituído. `shell_clearance/MANIFEST_SHA256.json` identifica o código e os controles NumPy usados; `blocky_133331049150205.json/.npz` preservam medidas e geometria.

Critério de rejeição atendido: a penetração caiu enquanto as arestas esticadas, as inversões volumétricas e a forma lateral pioraram. A candidata permanece isolada. Pergunta para a revisão do Astra: **qual evidência faria rejeitar a própria proposta mesmo que uma métrica melhorasse?** Neste caso, as 177 novas inversões e as saliências visíveis são evidências suficientes.
