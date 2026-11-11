# 🗺️ `src/editor/` — Editor de mapa/objetos voxel

Módulo do modo `--map-editor`. A cena é aberta em uma plataforma desenhada por
shader; os voxels formam uma malha iluminada e texturizada comum, usando o mesmo
`TexturedMesh`/`world_textured` do motor.

| Arquivo | Responsabilidade |
|---|---|
| `voxel_object.py` | Grade de voxels, paleta de materiais (cor + textura), rotação, colagem e JSON. |
| `map_project.py` | Volume base + objetos colocados (posição/rotação) e JSON do mapa. |
| `map_world.py` | Mapa estático jogável com colisão (`--terrain --map`). |
| `world_objects.py` | Objetos independentes no mundo procedural, persistência por seed e HUD de colocação. |
| `material_atlas.py` | Atlas 4×4 de tiles 16×16 e consulta de UV por textura. |
| `object_mesher.py` | Malha com face culling e cor/UV por voxel. |
| `platform.py` | Plataforma: superfície, grade, borda e cursor em um único draw. |
| `selection.py` | Caixa delimitadora do objeto selecionado. |
| `map_editor.py` | Ferramentas, picking, seleção, histórico, arquivos, câmera e render. |
| `editor_hud.py` | Painel 2D com ferramenta, material, grid, objeto e atalhos. |

Shaders em `assets/shaders/platform.vert` e `platform.frag`. Documentação de uso
em [`docs/EDITOR.md`](../../docs/EDITOR.md).
