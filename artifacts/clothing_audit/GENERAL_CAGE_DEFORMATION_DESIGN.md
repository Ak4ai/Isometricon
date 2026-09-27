# Proposta: deformação volumétrica contínua para roupas Roblox

## Evidência local

A malha original do vestido 114590471167431 e a do jeans 109837605892174
estão íntegras (`source_garments_additional_corrected.png`; a sobreposição
na imagem anterior foi corrigida em `SOURCE_OVERLAY_DECISION.md`). A cage externa transferida
também é relativamente estável: p99 de alongamento 1,41x no vestido e 1,53x
no jeans, sem arestas acima de 3x. O defeito principal ocorre ao vincular
cada vértice visível, de maneira independente, ao triângulo da cage externa
mais próximo: 108/125 arestas excessivamente esticadas do vestido e 29/33
do jeans atravessam regiões de cage distintas. A otimização local por
vizinhança reduz os números para 28 e 2, respectivamente, mas quase não
altera as silhuetas. Logo, suavizar apenas a seleção discreta de faces não
substitui um campo de deformação contínuo.

As cages de vestido e jeans são superfícies conexas após soldar vértices
coincidentes, mas **não são fechadas**. O vestido tem três contornos de
borda (8, 8 e 4 vértices); a cage externa do jeans tem contornos de
12, 8, 8, 3, 3, 3 e 3 vértices. A malha visível tem várias componentes
desconectadas (6 no vestido, 13 no jeans), portanto um remendo que dependa
de uma única componente ou da palavra “saia/calça” não será geral.

As triangulações interna e externa diferem: o vestido tem 244 triplas de UV
da cage interna sem face idêntica na cage externa; o jeans tem 302. Fiz um
teste isolado de projeção usando as faces reais da cage externa, sem mexer
no runtime (`scripts/experiment_outer_topology.py`). O número de arestas
visíveis acima de 3x quase não mudou: vestido 125 → 123, jeans 33 → 32.
Portanto essa diferença deve ser tratada corretamente no novo vínculo,
mas **não explica sozinha** os defeitos visuais.

## Método proposto

**Resultado da etapa 1 (26/09/2026).** O fechamento da topologia de origem é
possível em memória: vestido 3 bordas/14 faces de tampa; jeans 7 bordas/26
faces de tampa. Contudo, a mesma solda não é geometricamente válida na cage
alvo atual. Vértices coincidentes na origem se separam até 10,4 cm no vestido
e 26,2 cm no jeans após a transferência. A cage corporal alvo, antes do
deslocamento da roupa, já se separa até 8,5 cm nas mesmas costuras. Há 85 e
129 grupos de costura, respectivamente, separados por mais de 2 cm na cage
externa transferida. Forçar a média desses pontos cria um volume topologicamente
fechado, mas geometricamente falso; portanto nenhum peso volumétrico deve ser
gerado a partir dele. Dados reproduzíveis em `VOLUMETRIC_CAGE_READINESS.json`.

O passo seguinte é localizar as UVs/partes corporais de cada costura divergente,
separar as descontinuidades legítimas entre partes das falhas de transferência
do deslocamento da cage externa, e construir uma correspondência alvo contínua
ou domínios por parte com junções explícitas. A aceitação exige costuras dentro
de uma tolerância geométrica, ausência de auto-interseções e cobertura real da
malha visível. Só então cabem MVC, coordenadas harmônicas e comparação visual.

**Rastreamento das costuras.** Nas maiores aberturas do vestido aparecem
LowerTorso–UpperLeg e UpperTorso–UpperArm; no jeans predomina LowerLeg–Foot.
A análise por UV corporal mostra duas falhas distintas: no vestido 53 grupos
já têm abertura corporal >2 cm, e 23 têm corpo quase contínuo (≤5 mm) mas
casca da roupa >2 cm; no jeans os números são 53 e 69. Uma solda diagnóstica
somente dos grupos com corpo contínuo reduz as costuras externas >2 cm de
85 para 62 (vestido) e de 129 para 60 (jeans). Ainda sobram lacunas de até
8,5 cm e 26,2 cm, respectivamente. Isso confirma que consertar apenas o
deslocamento da casca não basta. Antes de construir um volume único, é preciso
tratar as junções anatômicas da cage feminina e decidir se cada junção deve ser
contínua na pose de repouso ou representada por domínios separados ligados por
uma ponte. O protótipo de solda é apenas uma medição, sem alteração no runtime.

**Auditoria da cage corporal R15.** `scripts/audit_body_joint_seams.py` compara
as UVs da referência e da cage feminina diretamente, sem depender de roupa.
Encontrou 137 grupos de vértices compartilhados entre partes na referência;
45 se abrem mais de 2 cm no alvo. As 10 correspondências de cada tornozelo
estão abertas em ambos os lados (até 6,5 cm à esquerda e 8,6 cm à direita,
medidos como desvio do centro do grupo). Ombro–braço chega a 5,0 cm; cotovelo
e punho já fecham praticamente à precisão numérica. Uma associação geométrica
ótima alternativa no tornozelo direito muda os pares, mas ainda deixa distância
média entre pontos de 8,6 cm. Portanto uma permuta de UV não basta: a borda
geométrica do pé também está em posição diferente da borda da perna.

Próxima correção de asset: no Blender, editar as posições da cage feminina nos
anéis de junção identificados em `BODY_JOINT_SEAMS.json`, mantendo as UVs e a
ordem de faces intactas. Cada UV de uma costura compartilhada na referência
deve apontar para a mesma posição global no alvo, salvo junção intencionalmente
separada. Depois reexportar e repetir o audit; aceitar apenas com contagens de
abertura e inspeção de forma/auto-interseção. Não soldar todos os pontos
automaticamente: alguns grupos coincidentes da referência incluem contatos
entre as duas coxas, e uma média cega pode destruir o formato anatômico.

**Controle offline sem Roblox (26/09/2026).**
`scripts/audit_wrap_identity.py` usa a cage de referência embutida em cada
roupa como alvo após uma rotação conhecida de eixos. O pipeline reproduz a
cage externa do vestido e do jeans com erro máximo inferior a 2e-16 e a
malha visível com erro inferior a 3e-17. Logo a leitura dos assets, a
conversão básica de espaço e o vínculo ao triângulo funcionam na identidade.
Isso não valida a transferência para um corpo diferente: nesse caso o campo
local por UV e a seleção independente de faces continuam como suspeitas
principais. O OBJ R15 canônico salvo no projeto difere das referências
embutidas nas duas roupas por pose/escala/origem; substituí-lo diretamente
como alvo de identidade seria um controle inválido. Não editar a cage no
Blender com base apenas nessa comparação.

1. **Normalização por UV canônica.** Reconstruir uma malha lógica de cage
   com um ponto por UV, mantendo a posição de cada cópia de vértice e as
   faces originais. Comparar faces da cage interna/externa por triplas de
   UV, não por índice de arquivo; restaurar faces ausentes apenas quando as
   três UVs e seus pontos correspondentes existirem e a face não criar
   auto-interseção. Registrar todos os reparos.
2. **Fechamento geométrico temporário.** Detectar cada contorno de borda da
   cage externa soldada, orientar o loop e triangulá-lo no *domínio de
   cálculo* tanto na cage de origem como na transferida, com a mesma
   conectividade. Verificar manifold, volume assinado, auto-interseções e
   orientação. Não modificar o arquivo Roblox nem a UV da cage exportada.
3. **Campo volumétrico único.** Para cada vértice da roupa original, calcular
   coordenadas generalizadas relativas à cage externa fechada. Como
   primeiro protótipo, usar *mean value coordinates* (MVC) para malhas
   triangulares fechadas; o campo resultante é contínuo e preserva
   transformações afins. A nova posição é `p' = sum_j w_j(p) * C_alvo[j]`.
   Isso substitui a escolha de um único triângulo por vértice e funciona
   com qualquer topologia de roupa, inclusive várias componentes visíveis.
   Verificar numericamente `sum(w)=1` e reprodução da posição original
   `sum(w*C_origem)≈p` antes de aceitar o vínculo.
4. **Controle de geometria.** MVC em cages côncavas pode criar pesos negativos
   e extrapolação. Medir pesos, mudança de área, distorção de arestas,
   inversões de faces, auto-interseções e penetração no corpo. Se MVC não
   passar, a alternativa fundamentada é calcular coordenadas harmônicas
   não negativas no volume tetraedrizado, em pré-processamento por asset.
   Não selecionar algoritmos por nome/categoria de roupa. Uma etapa ARAP
   pode preservar detalhes, mas somente com âncoras derivadas do campo
   volumétrico; ARAP sozinho não corrige correspondências erradas.
5. **Dados de skinning e camadas.** Manter pesos/ossos e aplicar pose de
   repouso antes de criar o vínculo para malhas skinned. Em poses animadas,
   usar o mesmo campo e pesos sobre a cage atualizada. Para sobrepor roupas,
   compor cages na ordem `WrapLayer.Order`, em vez de ajustar cada peça
   independentemente ao corpo nu.

Os pesos por asset podem ser pré-calculados uma vez e armazenados em cache.
Aplicá-los durante a renderização exige apenas NumPy (produto matriz-vetor)
e não requer Blender no runtime. A construção do domínio e dos pesos pode
ocorrer na importação do asset; a viabilidade de uma implementação pura em
Python/NumPy para essa fase deve ser medida antes da integração.

## Plano de prova, sem mudar o runtime antecipadamente

1. Implementar somente fechamento e diagnóstico da cage para vestido e
   jeans. Confirmar que as duas cages fechadas têm a mesma topologia e que
   a roupa fica dentro do volume; medir pontos fora da cage. Se houver
   componentes decorativas externas, registrá-las e testar extrapolação
   controlada por componente, sem fingir que MVC interior se aplica a elas.
2. Calcular e armazenar pesos MVC de vestido/jeans e comparar contra o
   encaixe atual nas quatro vistas. Exigir redução de alongamentos >3x,
   manutenção de saia contínua e duas pernas separadas, sem clipping novo.
3. Rodar a mesma implementação, sem parâmetros por asset, em camisa,
   jaqueta, biquíni, jersey, calça cargo, suéter e peças adicionais.
   Comparar silhueta, UV/textura, orientação frente/costas e arestas.
4. Testar poses A/T e flexão de braços/pernas; depois duas ou mais camadas
   em ordens distintas. Só promover o novo caminho quando ele melhorar os
   casos ruins e não regredir os bons. Casos fora do domínio devem ter
   erro explícito e diagnóstico, não um resultado silenciosamente ruim.

## Fontes técnicas

- [Roblox: aplicação de deformação e correspondência UV](https://create.roblox.com/docs/art/modeling/cage-meshes/apply-deformation)
- [Roblox: cages interna/externa e requisitos](https://create.roblox.com/docs/art/accessories/clothing-specifications)
- [Ju, Schaefer e Warren: Mean Value Coordinates for Closed Triangular Meshes](https://graphics.stanford.edu/courses/cs468-05-fall/Papers/p561-ju.pdf)
- [Joshi et al.: Harmonic Coordinates for Character Articulation](https://dl.acm.org/doi/10.1145/1276377.1276466)
- [Sorkine e Alexa: As-Rigid-As-Possible Surface Modeling](https://diglib.eg.org/items/e0b21a71-350e-41e7-a586-3bfa526ed21c)

Roblox não publica aqui o algoritmo interno completo de WrapLayer; MVC,
coordenadas harmônicas e ARAP são escolhas de engenharia fundamentadas na
literatura, não afirmações de que o motor Roblox usa exatamente essas técnicas.
