# 🗺️ `src/editor/` — Editor de mapa/objetos voxel

Módulo do modo `--map-editor`. A cena é aberta em uma plataforma desenhada por
shader; os voxels formam uma malha iluminada e texturizada comum, usando o mesmo
`TexturedMesh`/`world_textured` do motor.

| Arquivo | Responsabilidade |
|---|---|
| `voxel_object.py` | Grade de voxels, paleta de materiais (cor + textura), rotação, colagem e JSON. |
| `material_atlas.py` | Atlas 4×4 de tiles 16×16 e consulta de UV por textura. |
| `object_mesher.py` | Malha com face culling e cor/UV por voxel. |
| `platform.py` | Plataforma: superfície, grade, borda e cursor em um único draw. |
| `map_editor.py` | Ferramentas, picking, histórico, arquivos, câmera e render. |
| `editor_hud.py` | Painel 2D com ferramenta, material, grid, objeto e atalhos. |

Shaders em `assets/shaders/platform.vert` e `platform.frag`. Documentação de uso
em [`docs/EDITOR.md`](../../docs/EDITOR.md).
