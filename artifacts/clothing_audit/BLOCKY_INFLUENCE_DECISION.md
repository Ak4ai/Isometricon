# Blocky: mistura entre partes não explica os principais testemunhos

2026-09-27. Diagnóstico com dados congelados; nenhuma alteração no runtime.

[Antes/depois do controle](blocky_influences/comparison.png) ·
[Pesos e métricas](blocky_influences/SUMMARY.json) ·
[Rastreamento das etapas](blocky_influences/UNMIXED_STAGES.json).

## Hipótese testada e resultado

O teste sintético mostrou que influências entre componentes podem deslocar a
manga incorretamente. A hipótese seguinte era que o mesmo mecanismo explicasse
os ombros problemáticos da camisa no R15 Blocky.

Essa hipótese **não explica os testemunhos 93, 377 e 1486**: todos recebem
somente influências da própria parte no suporte da outer. Ao remover as
influências de outras partes, suas posições permanecem exatamente iguais.

Não se conclui que toda influência cruzada seja benéfica ou que nunca cause
problemas reais. Conclui-se que bloqueá-las não resolve este caso e não é uma
correção justificável para o runtime.

## Como isolamos a variável

`scripts/audit_blocky_radial_influences.py:replay` reconstrói exatamente a busca,
rotações, pesos e soma de `transfer_outer_cage_radial`. A outer reconstruída
coincidiu com o NPZ radial salvo: erro máximo 0,0. A roupa baseline também é a
radial/prisma congelada; não confundimos com a variante canônica antiga.

Todas as 4895 entradas da cage têm identificação única de parte por UV da
referência R15. Nenhuma foi classificada por posição ou nome de roupa.
No controle removemos pares de partes diferentes, mantendo os pesos de origem,
rotações, escala e binding. Renormalizamos apenas os pesos restantes por destino.
Isso é um teste causal, não uma implementação proposta de filtro anatômico.

## Métricas do controle

| Medida | Radial anterior | Influências estrangeiras removidas |
|---|---:|---:|
| Amostras penetrantes (5995 vértices + centros de faces) | 27,82% | 28,47% |
| Arestas normalizadas >3x, máscara histórica | 957 | 1018 |
| Vínculos com determinante invertido | 263 | 183 |
| Dispersão máxima de grupos coincidentes da outer | ~4,4e-16 | 0,11780 |

13 vértices deixaram de penetrar; 32 passaram a penetrar; 652 continuaram dentro.
Mesmo com menos inversões de binding, o encaixe global piorou. 88 grupos antes
coincidentes se separaram acima de 1e-5 (69 acima de 1e-3). Nem toda coincidência
é necessariamente uma costura intencional; a mudança deve ser tratada como risco
de continuidade, não como prova de 88 buracos visíveis.

925 vértices da roupa têm algum peso estrangeiro no suporte baricêntrico da
outer. **345 vértices penetrantes não têm nenhum**. A ausência foi determinada
pelos pesos, não por aparência da imagem.

## Onde esses 345 vértices entram no corpo

`scripts/audit_blocky_unmixed_stages.py` mede pontos correspondentes na inner,
na outer, na interpolação prismática sem residual e na posição final. Contra a
união dos componentes fechados do corpo congelado:

| Estágio | Pontos dentro do corpo, entre os 345 selecionados |
|---|---:|
| Ponto interpolado da inner alvo | 122 |
| Ponto interpolado da outer radial | 310 |
| Prisma antes do residual | 314 |
| Posição final | 345 |

31 entram somente depois do residual. As linhas da tabela não são subconjuntos
aninhados; o número 31 é calculado diretamente comparando as duas últimas etapas.
A inner alvo interpola a cage corporal, mas isso não garante estar na fronteira
externa da união das partes ou fora da malha do corpo em todo ponto da face.

Testemunhos concretos, todos sem influência estrangeira:

- **377, LeftUpperArm:** inner x≈1,000; outer x≈0,913. A outer e a roupa entram
  em UpperTorso. Residual de origem ~8,48e-12: o erro existe antes dele.
- **93, UpperTorso:** inner x≈1,000; outer x≈1,166. A expansão do tronco entra
  em LeftLowerArm. Residual pequeno (~9,69e-5), sem explicar a colisão principal.
- **1486, RightUpperArm:** inner, outer e ponto prismático estão fora/na fronteira;
  o residual de origem ~0,02780 leva a posição final para dentro do próprio braço.

Os hits por nome usam o leitor diagnóstico FBX já empregado nas auditorias.
As contagens agregadas usam diretamente a malha de corpo congelada do experimento.

## O que é novo e o que já sabíamos

CANONICAL_RADIAL_REVIEW.md e BLOCKY_CLEARANCE_WITNESSES.json já continham colisões
entre partes e defeitos de extrapolação. Não estamos anunciando isso novamente
como descoberta. O avanço aqui é a **reprodução exata dos pesos**, a remoção
controlada das influências e a quantificação do conjunto que falha sem mistura.
Isso rejeita a explicação sugerida pelo teste sintético para esses testemunhos.

O bloqueio geométrico remanescente é formar um envelope que respeite o corpo
completo: expandir a superfície de cada parte localmente pode entrar na vizinha.
Há ainda o transporte residual que pode entrar no próprio corpo. São problemas
distintos; não serão resolvidos só por densidade de amostragem ou rótulos de parte.

O corretor posterior de colisão já foi tentado em SHELL_CLEARANCE_DECISION.md e
PRISM_CLEARANCE_DECISION.md, com falhas de distorção/volume. **Não repetir esse
corretor nem promover um novo filtro de partes** com base nesta auditoria.
Uma futura formulação deve demonstrar cobertura da união corporal e transporte
residual válido sem destruir continuidade; este relatório não afirma já tê-la.

## Reprodução

```powershell
python scripts/audit_blocky_radial_influences.py
python scripts/audit_blocky_unmixed_stages.py
python -m pytest tests/test_blocky_radial_influence_audit.py tests/test_synthetic_contact.py tests/test_synthetic_wrap_fixture.py tests/test_experimental_refined_reference.py tests/test_experimental_prism_validity.py tests/test_experimental_prism_constraints.py tests/test_experimental_shell_clearance.py tests/test_experimental_canonical_radial.py tests/test_multi_influence_shell.py tests/test_wrap_layer_fit.py tests/test_clothing_uv_cage_mapping.py tests/test_volumetric_cage.py -q -p no:cacheprovider
```

58 testes passaram. Os dois novos verificam replay exato, normalização dos pesos
e que a ablação é uma operação neutra quando há apenas uma parte.
JSON contém hashes e testemunhos; `blocky_influences/outputs.npz` guarda shells,
malhas, identidades e contribuições por parte. As imagens usam as mesmas quatro
vistas e escala entre variantes. Penetração é uma medida amostrada, não fração
de área, e nenhum resultado aqui certifica compatibilidade universal.
