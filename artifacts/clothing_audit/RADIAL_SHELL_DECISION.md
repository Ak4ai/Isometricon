# Teste da busca radial por espessura na cage externa

Nota posterior: a sobreposição de cage na imagem antiga
`office_shirt_wraplayer/source_garments_depth.png` tinha um desalinhamento
de `ReferenceOrigin`. Use `office_shirt_wraplayer/source_garments_depth_corrected.png`
para revisar a fonte; o decote baixo do suéter ainda aparece após a correção.

## Implementado

`src/clothing/multi_influence_shell.py:transfer_outer_cage_radial` constrói influências pela distância entre cada ponto da cage interna e os pontos da cage externa *original*. O raio é proporcional à espessura correspondente entre inner/outer, e as previsões usam a correspondência UV já validada, uma rotação local por vizinhança e a escala global da cage. Pontos próximos da outer cage podem colaborar mesmo quando estão em partes topologicamente separadas. É uma aproximação offline do método descrito na patente US20250265799A1, não código do Roblox.

O teste sintético confirmou identidade, rotação, reflexão e escala uniformes exatas. Outro teste demonstrou que dois pontos coincidentes da outer cage, mas em ilhas desconectadas da inner cage, continuam coincidentes após a transferência.

## Cinco roupas no corpo feminino

Com `radius_factor=1`, a contagem de arestas da malha que cresceram acima de 3 vezes o comprimento original foi:

| Roupa | Runtime atual | Cage radial + prisma |
| --- | ---: | ---: |
| Camisa | 9 | 1 |
| Jaqueta | 11 | 1 |
| Jeans com botas | 33 | 0 |
| Vestido | 86 | 9 |
| Suéter amplo | 240 | 0 |

As imagens de quatro vistas mostram separação das pernas do jeans e saia muito mais coesa. Ainda aparecem defeitos em ombros, decotes e pequenos recortes. O suéter original já possui decote profundo e ombros expostos (`office_shirt_wraplayer/source_garments_depth.png`); essa parte da silhueta não é causada pela transferência. O resultado tem 84 de 3989 faces do jeans com menos de 10% da área esperada após escala, ante 101 no baseline; redução de esticamento não elimina triângulos comprimidos. O número de normais mudadas em relação ao baseline não é, sozinho, uma contagem confiável de faces inválidas porque o baseline também está deformado.

Com `radius_factor=2`, o vestido fica visualmente mais liso, mas a busca do suéter pode dar influência a mais de 2300 pontos em um único vértice; com fator 1, o alcance é menor e o vestido mantém algumas irregularidades. Esse parâmetro ainda não foi validado universalmente.

## Corpo oficial Blocky

O mesmo método, sem parâmetro por roupa, reduziu arestas acima de 3 vezes da camisa de 1230 para 972 em relação ao runtime atual. A imagem continua com falhas nos ombros (`radial_blocky_133331049150205_candidate.png`). A mudança de proporção entre a referência da camisa e o Blocky é grande, então a contagem absoluta de arestas não prova, isoladamente, que o encaixe visual piorou. A falha visível confirma que **o método ainda não está pronto para runtime universal**.

## Avaliação do texto do Gemini

- Correto: os OBJs exportados do corpo/cage passaram nas verificações de topologia, UV e cobertura; a vinculação independente de cada vértice visível é uma fraqueza real; o suéter pode receber influências demais num raio grande.
- Não demonstrado: que a busca espacial é fundamentalmente errada. O método publicado a usa justamente para aproximar pontos sobrepostos da costura da saia. Nosso teste radial melhorou a separação do jeans e a saia, embora ainda não resolva todos os detalhes.
- Incorreto como garantia: coordenadas de um prisma não impedem penetração se o vértice de origem fica fora do prisma, se há residual/extrapolação ou se o prisma alvo dobra. Para este vestido, o percentil 99 da distância à fonte prismática é ~0,16 unidade nativa.
- Incorreto como operação direta: os UVs da textura da malha visível não identificam sua ilha na cage R15. Os UVs das cages servem para parear cages entre si. Uma ilha da malha visível precisa ser inferida da geometria/conectividade ou vir de metadados confiáveis. Bloquear toda influência entre ilhas também pode destruir a costura central de saias.
- Ancorar saias à bacia por regra de categoria seria uma heurística; não foi demonstrado como operação universal do Roblox.

## Decisão

Manter a cage radial como candidata isolada. A próxima implementação deve tratar o vínculo da malha visível, com correspondência coerente entre triângulos/painéis e controle de orientação, além de testar no Blocky. Não mover scripts experimentais nem substituir `wrap_layer_fit.py` enquanto esse controle falhar.

Reprodução: `python scripts/experiment_radial_shell.py --preview --radius=1`, `python scripts/experiment_radial_blocky.py`, `python -m pytest tests/test_multi_influence_shell.py tests/test_wrap_layer_fit.py tests/test_clothing_uv_cage_mapping.py -q -p no:cacheprovider`. Dados: `WRAP_RADIAL_SHELL_1.json`, `WRAP_RADIAL_SHELL.json` (primeira execução com raio 2), `WRAP_RADIAL_BLOCKY.json`.
