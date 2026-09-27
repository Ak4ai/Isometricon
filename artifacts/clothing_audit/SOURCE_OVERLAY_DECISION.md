# Correção da visualização de origem do jeans e vestido

Execução:

```powershell
python scripts/audit_source_garments_depth.py 114590471167431 109837605892174
```

Saídas: `source_garments_additional_corrected.png`,
`source_garments_additional_corrected.json` e
`source_overlay_before_after.png`. A imagem original
`source_garments_additional.png` foi preservada para comparação, mas a
sobreposição da cage nela está desalinhada.

## Erro encontrado

`scripts/audit_source_garments_depth.py` colocava a malha visível no espaço
local da cage externa com `(garment - CageOrigin) @ CageRotation`, porém
desenhava a reference cage em seu espaço local próprio. Para comparar ambas,
a reference cage também precisa de
`(reference @ ReferenceRotation.T + ReferenceOrigin - CageOrigin) @ CageRotation`.

Esses origins vêm do RBXM do asset e não são iguais:

- Jeans: `ReferenceOrigin - CageOrigin = [0, +0,067057, −0,027378]` unidades
  originais; a componente vertical equivale a cerca de 0,0224 m depois da
  escala RMS usada no alvo feminino.
- Vestido: `[+0,000006, 0, −0,024041]` unidades originais, aproximadamente
  0,0076 m de profundidade depois dessa escala.

O programa de vestimenta **não usa esse script de visualização**. Em
`src/clothing/wrap_layer_fit.py`, calcula `reference_parent` e `outer_parent`
com seus origins respectivos; para o vínculo por face externa, coloca a malha
visível no espaço local da cage externa. O experimento de prismas usa as duas
cages em espaço parent e a malha original no mesmo espaço. Logo, o erro
identificado nesta imagem não foi herdado por esses cálculos.

## Diferença observada

Pixels em que a reference cage aparece sobre uma região que a malha visível
ocupa quando desenhada sozinha, na mesma projeção fixa:

| Asset e vista | Imagem antiga | Imagem corrigida |
| --- | ---: | ---: |
| Vestido, costas | 1078 | **142** |
| Jeans, costas | 796 | **0** |
| Vestido, frente | 310 | 408 |
| Jeans, frente | 377 | 321 |

O pequeno valor restante no vestido traseiro fica junto ao decote na imagem
corrigida. Na frente, a referência aparece sobretudo na abertura do pescoço
ou perto do cós. Estes pixels medem **oclusão na projeção**, não provam
penetração geométrica, nem medem quanto da roupa toca a pele. A reference
cage também não é uma malha de pele do avatar Roblox.

A conclusão correta é limitada: as grandes manchas no vestido traseiro e no
jeans traseiro daquela imagem eram causadas principalmente pelo desalinhamento
da visualização. Isto **não** elimina os defeitos reais já medidos após a
transferência: a aresta 2396–2397 do jeans alonga 23,67× no runtime,
e a radial/prisma ainda deixa arestas, faces comprimidas e amostras no corpo.

Não foi comparado o OBJ da roupa com um binário de malha remoto atual;
para estes dois assets há OBJ, PNG e RBXM locais, mas nenhum `.mesh` da malha
visível no cache. A aparência corrigida e as distâncias de vínculo não dão
evidência de um desalinhamento grosseiro na importação local, mas não provam
que a importação original reproduz todos os atributos do Roblox.

Auditoria adicional de `MeshPart` no RBXM: jeans e vestido declaram
`HasSkinnedMesh=true`. O decodificador OBJ em
`scripts/import_roblox_clothing.py` grava pontos, UVs e faces do Draco,
sem pesos de skinning ou pose de ossos. Isso é uma limitação real da importação,
mas **ainda não demonstra** que ela cause a aparência estática destes dois
assets; seria preciso comparar o resultado com o mesh decodificado incluindo
dados de skinning/bind pose. Os RBXM locais não contêm um `.mesh` da roupa
em cache para fazer essa comparação agora. Não usar o erro da imagem antiga
como prova de que o importador seja culpado.
