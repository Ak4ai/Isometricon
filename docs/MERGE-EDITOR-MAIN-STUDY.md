# Estudo de merge — editor de mapa × main

> **Status:** estudo em andamento; merge **não** foi concluído.
> **Data:** 2026-11-27
> **Branch do editor:** `feat/voxel-editor`
> **Ponto congelado do editor:** `2b0342f`
> **Main de referência:** `origin/main` em `8ac7671`
> **Base comum:** `ae61320`

## 1. Backups do editor

O ponto exato do editor antes de qualquer merge foi salvo localmente e no remoto.

### Branch de backup

```text
backup/voxel-editor-2b0342f
```

Remoto:

```text
origin/backup/voxel-editor-2b0342f
```

### Tag de backup

```text
voxel-editor-2b0342f
```

Remoto:

```text
refs/tags/voxel-editor-2b0342f
```

### Commit

```text
2b0342f119ecfe87ec8f596b1310eb9187a43c88
2b0342f feat: voxel editor UI changes
```

O branch `feat/voxel-editor` também está nesse commit e está limpo.

### Como recuperar

```bash
git fetch --all --tags
git checkout backup/voxel-editor-2b0342f
# ou
git checkout voxel-editor-2b0342f
```

## 2. Worktree de integração

O merge foi iniciado num worktree separado, sem tocar no editor:

```text
/tmp/iso-merge-study
branch: integration/voxel-editor-main
```

O branch foi criado a partir de:

```text
backup/voxel-editor-2b0342f
```

O merge com `origin/main` foi iniciado com:

```bash
git merge --no-commit --no-ff origin/main
```

Ele está **parado nos conflitos**, sem commit de merge.

Se o worktree `/tmp` desaparecer, recriar:

```bash
cd /Users/radsfer/Projects/Isometricon
git worktree add /tmp/iso-merge-study integration/voxel-editor-main
cd /tmp/iso-merge-study
git merge --no-commit --no-ff origin/main
```

## 3. Situação dos branches

| Ref | Commit | Observação |
|---|---|---|
| `feat/voxel-editor` | `2b0342f` | editor preservado; limpo |
| `backup/voxel-editor-2b0342f` | `2b0342f` | backup local |
| `origin/backup/voxel-editor-2b0342f` | `2b0342f` | backup remoto |
| `voxel-editor-2b0342f` | `2b0342f` | tag anotada |
| `origin/main` | `8ac7671` | main de referência |
| `integration/voxel-editor-main` | `2b0342f` | merge em andamento no worktree |

O `main` local **não foi atualizado** porque está divergente:

```text
main: ahead 232, behind 413 em relação a origin/main
```

Não resetar nem fazer merge no `main` local sem decidir o que fazer com os commits locais.

## 4. O que o main ignorou do editor

O `main` **não contém** a UI nova do editor. Ele ficou no branch `feat/voxel-editor`.

### Evidência

| Item | Editor | `origin/main` |
|---|---|---|
| `EditorHud` | 500×840, botões grandes | 470×390, layout antigo |
| Canvas dockado | Sim | Não |
| Modal de exportação | Sim | Não |
| `src/editor/lighting.py` | Sim | Não |
| `src/world/light_blocks.py` | Sim | Não |
| `src/editor/color_wheel.py` | Sim | Não |
| `src/interactive/construction_thumb.py` | Sim | Não |
| `/schem` biblioteca primeiro | Sim | Não |
| Remoção de carimbo por botão direito | Sim | Não |
| Ferramentas unificadas | Sim | Não; ainda tem `erase` |

O `main` só tem uma alteração pequena no editor: troca de caminhos fixos por `src/core/paths.py`.

### Decisão

> **Toda a UI e experiência do editor deve vir de `feat/voxel-editor`. Do `main`, entra apenas caminhos/persistência e o que for compatível.**

Não aceitar a versão do main para:

- `src/editor/editor_hud.py`;
- `src/editor/map_editor.py`, exceto o trecho de caminhos;
- `src/interactive/construction_panel.py`;
- `src/editor/export_dialog.py`;
- `src/editor/lighting.py`;
- `src/world/light_blocks.py`;
- `src/editor/color_wheel.py`;
- `src/interactive/construction_thumb.py`;
- testes de UI do editor.

## 5. Conflitos reais do merge

O merge parou em **5 arquivos**:

```text
src/editor/map_editor.py
src/main.py
src/rendering/shader.py
src/rendering/sun_shadows.py
tests/test_game_menus.py
```

### 5.1 `src/editor/map_editor.py` — baixo risco

Conflito em imports e na lista `TOOLS`.

Decisão:

- manter a UI nova;
- manter `TOOLS = ("build", "paint", "stamp", "select")`;
- importar `RESOURCE_ROOT` e `saves_path` do `main`;
- remover o `PROJECT_ROOT` duplicado criado pelo merge;
- trocar usos restantes de `PROJECT_ROOT` por `RESOURCE_ROOT`/`saves_path`.

O merge automático deixou `PROJECT_ROOT` duas vezes no arquivo. Corrigir mesmo depois de remover os marcadores.

### 5.2 `src/main.py` — médio risco

Três conflitos:

1. `compat_shadows` do editor contra `presentation_requested` do main;
2. fluxo de menu/editor contra o novo fluxo de `selected_world`/`package_smoke`;
3. `shadow_renderer.compat` contra a criação do `ShadowAccumulator`.

Decisão:

- manter os dois no primeiro conflito:
  - compatibilidade macOS do editor;
  - seed fixa da apresentação.
- no fluxo de menu:
  - manter a sessão própria do editor;
  - manter o tratamento novo de `selected_world`;
  - garantir que `custom_seed` só seja lido quando `selected_world` existe.
- no terceiro:
  - manter `shadow_renderer.compat`;
  - manter `shadow_accum`;
  - garantir que o modo compatível do macOS não seja sobrescrito pelo `set_detail` do main.

### 5.3 `src/rendering/shader.py` — alto risco

Mistura duas melhorias:

- editor:
  - unidades únicas para samplers;
  - correção do pipeline no Metal;
- main:
  - troca de variantes com cache de uniforms;
  - `set_define`;
  - novas unidades para sombra acumulada.

Decisão:

- manter as duas arquiteturas;
- no `set_defines`, depois de trocar o programa:
  - ativar o programa novo;
  - chamar `_assign_sampler_units`;
  - sincronizar os uniforms com o cache de valores do main;
  - restaurar o programa que estava ativo.

Mapa de unidades recomendado:

```text
u_TextureAtlas      0
u_ShadowShapeIds    1
u_RoomMask          2
u_ShadowMask        3
u_ShadowHorizon     4
u_CharShadowMap     5
u_FogWarMap         6
u_Distance          8
u_Boxes             9
u_ShadowShapes     10
u_ShadowPlants     11
u_ShadowEmpty      14
u_AccumPrev        15
u_AccumPrevPos     16
```

O main usa `u_ShadowShapeIds: 12`; o editor usa `1`. Como o shader do editor é a base, usar **1** e alinhar `sun_shadows.py`.

### 5.4 `src/rendering/sun_shadows.py` — maior risco

Mistura:

- editor:
  - `sampler2DArray` em vez de `sampler3D`;
  - compatibilidade com Metal/macOS;
  - bind de samplers;
- main:
  - sombra em distância maior;
  - textura de vazio (`u_ShadowEmpty`);
  - sombra acumulada;
  - giro/granulado da penumbra.

Decisão:

- manter a versão do editor como base para o formato das texturas;
- trazer do main:
  - janela de sombra distante;
  - `empty_distances`;
  - `spin_tile`;
  - detalhe/qualidade;
- trocar todas as texturas 3D de sombra para `GL_TEXTURE_2D_ARRAY`;
- trocar o shader de `sampler3D` para `sampler2DArray`;
- manter `SHAPE_IDS_UNIT = 1` e `EMPTY_UNIT = 14`.

O merge automático deixou esta combinação perigosa:

```glsl
uniform sampler2DArray u_ShadowMask;
uniform sampler2DArray u_ShadowShapeIds;
uniform sampler3D u_ShadowEmpty;   // trocar para sampler2DArray
```

Isso é o mesmo tipo de mistura que quebra o pipeline no Metal do macOS.

### 5.5 `tests/test_game_menus.py` — baixo risco

Manter os dois blocos:

- testes do editor do branch;
- testes novos de robustez do main.

## 6. Conflitos semânticos invisíveis

Além dos 5 conflitos, o merge automático introduziu quebras que não aparecem como marcadores.

### 6.1 `export_dialog.py` importando `PROJECT_ROOT`

O main removeu `PROJECT_ROOT` de `object_names.py`; o modal ainda importa:

```python
from src.editor.object_names import EXPORT_OBJECTS, PROJECT_ROOT, slugify
```

Corrigir para `RESOURCE_ROOT`/`saves_path`.

### 6.2 `MapEditor` com dois `PROJECT_ROOT`

O merge automático duplicou a definição. Remover e centralizar em `core.paths`.

### 6.3 `u_ShadowShapeIds` com unidades diferentes

Shader do editor usa unidade 1; `sun_shadows.py` do main usa 12. Alinhar em 1.

### 6.4 `Shader.set_defines` sem reassinalar samplers

O main troca variantes sem chamar `_assign_sampler_units`. Isso pode fazer a variante nova herdar samplers na unidade errada — exatamente o problema que o editor já tinha resolvido no macOS.

## 7. O que o merge automático já combinou bem

Revisar, mas provavelmente está correto:

- `src/world/structure_mesher.py`:
  - limite de quadriláteros do main;
  - emissão de blocos luminosos do editor;
- `src/world/block_rotation.py`:
  - rotação de luzes do editor;
  - `max_mesh_quads` do main;
- `src/interactive/game_menus.py`:
  - ações do editor;
  - novas ações/menus do main;
- `assets/shaders/world_textured.frag`:
  - luzes pontuais do editor;
  - neblina/sombras do main;
  - `COMPAT_SUN_SHADOWS`;
- `src/interactive/character_editor.py` e `src/core/window.py`.

Conferir depois dos testes.

## 8. macOS ARM — riscos e decisões

### 8.1 `sampler3D` novo

O main adicionou `u_ShadowEmpty` como `sampler3D`. No Apple/Metal isso repete o problema já resolvido com `sampler2DArray`.

**Prioridade máxima:** converter textura e sampler.

### 8.2 Sombra acumulada

O main usa:

- `GL_ARB_shader_image_load_store`;
- `image2D` com `imageStore`;
- `glBindImageTexture`;
- `RGBA16F` e `RGBA32F`.

Isso é caro e pode não estar disponível no OpenGL 4.1 do macOS.

Decisão:

- desativar `shadow_accum` por padrão em `sys.platform == "darwin"`;
- manter a opção apenas se o driver expuser a extensão;
- nunca chamar `glBindImageTexture` sem checar suporte.

### 8.3 `EARLY_Z` e `SHADOW_HALF`

Dependem de:

- `GL_ARB_shader_image_load_store`;
- `GL_ARB_derivative_control`.

O fallback por compilação existe, mas precisa ser testado no Apple M2.

### 8.4 Custo de fragmento

O shader combinado agora tem:

- luzes pontuais;
- sombra do sol;
- neblina;
- sombra distante;
- possível acumulação.

No Apple M2 pode ficar pesado. Ordem segura:

```text
modo compatível de sombra
→ sombra acumulada desligada
→ meia resolução como opção
→ distância de sombra padrão baixa
```

### 8.5 O que já está bom no editor

O branch do editor já tem:

- HUD em 2×;
- `sampler2DArray`;
- unidades únicas de sampler;
- fallback `COMPAT_SUN_SHADOWS`;
- câmera com `far` dinâmico;
- canvas dockado responsivo.

Não perder isso no merge.

## 9. Qualidade de vida e performance do main que devem ser preservadas

Trazer do main, sem substituir a UI do editor:

- `src/core/paths.py` e persistência portável;
- snapshots de `.schem` com `sha256`;
- limites de NBT/schematic/malha;
- configurações de distância de render e sombra;
- neblina de borda;
- opções de sombra (distância, meia resolução, granulado);
- preferência de GPU dedicada (Windows; não afeta macOS);
- pacote de texturas Trailers Vision;
- apresentação acadêmica, quando aplicável ao fluxo principal.

## 10. Ordem de resolução recomendada

1. `map_editor.py` + `export_dialog.py` + `object_names.py` — caminhos e imports.
2. `shader.py` — variantes + samplers.
3. `sun_shadows.py` — `2D_ARRAY`, unidades, sombra distante.
4. `main.py` — fluxo de menu/editor + compat + apresentação.
5. `tests/test_game_menus.py` — manter os dois conjuntos.
6. Validar shader no macOS:
   - abrir editor;
   - abrir mundo normal;
   - testar `COMPAT_SUN_SHADOWS`;
   - testar sem acumulação.
7. Rodar a suíte completa.

## 11. Comandos úteis

### Ver conflitos

```bash
cd /tmp/iso-merge-study
git status --short
git diff --name-only --diff-filter=U
```

### Ver o merge em andamento

```bash
git diff --check
git diff --stat
```

### Cancelar e recomeçar

```bash
git merge --abort
git merge --no-commit --no-ff origin/main
```

### Testes após resolver

```bash
python -m pytest -q
```

### Confirmar que o editor original continua intacto

```bash
cd /Users/radsfer/Projects/Isometricon
git status --short --branch
git rev-parse HEAD
# deve ser 2b0342f
```

## 12. Critério de sucesso do merge

- `feat/voxel-editor` permanece recuperável em `2b0342f`;
- UI nova do editor continua funcionando;
- canvas dockado, modal de exportação, luzes, `/schem` e remoção de carimbo preservados;
- caminhos portáveis do main adotados;
- shader combina luzes pontuais + sombras/neblina;
- nenhum `sampler3D` novo no caminho macOS;
- mundo normal e editor abrem no Apple M2;
- suíte completa passa, exceto falhas preexistentes conhecidas;
- só então o branch de integração pode virar PR/merge no main.
