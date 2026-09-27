# Asset-specific WrapLayer runtime audit

The female outfit pipeline now prefers each cached layered asset's own
`WrapLayer.ReferenceMeshId`, `CageMeshId`, `ReferenceOrigin`, and `CageOrigin`
when a compatible 2690-face R15 cage is available. It reads RBXM PROP chunks
after LZ4 decompression, supports both `rbxassetid://` and asset delivery URL
IDs, and decodes FileMesh 2.00 alongside the existing Draco and FileMesh 4/5
formats. The 1709 cage UV points bind the clothing reference and outer cage
to the target female body cage with a quantization tolerance. Local triangle
frames transfer the authored outer-cage volume into the target A-pose. Visible
mesh vertices are bound to the garment outer cage in parent-local coordinates.

The asset path is enabled for female tops and bottoms when the visible mesh
lies near its outer cage (median distance <= 0.05 and p99 <= 0.2 Roblox
units). Missing data, incompatible UVs/topology, unsupported BindOffset, or
failed quality checks use the previous fitting path. The male pipeline does
not call this method. Cached cage meshes are stored by asset ID under
`assets/models/clothing/wrap_cages`.

## Tested assets

| Asset | Result | Median / p99 source distance | Observation |
|---|---|---:|---|
| Office shirt 133331049150205 | New path | 0.027 / 0.141 | Front and back torso coverage improves; original wide short-sleeve silhouette is retained. |
| Black bomber 72628400373948 | New path | 0.019 / 0.094 | Open front corresponds to the source mesh; jacket volume retained. |
| Pink cargo pants 16899958482 | New path | 0.050 / 0.158 | Waist and wide legs map through the female target cage. |
| Oversized knitted sweater 16185652164 | Previous path | 0.067 / 0.259 | New path rejected: low, wide sleeves and complex skinning cause visibly poor nearest-surface binding. |

The sweater's FileMesh 4.01 contains 15 bones and vertex skinning data. The
current OBJ cache discards those weights. Without a rig-aware binding, long
sleeves that approach the leg cage can be assigned to the wrong surface.
Restricting vertices by a simple sleeve heuristic regressed the bomber and
was not retained. The previous path also gives the sweater a poor fit; its
fallback keeps existing behavior rather than proving Roblox-equivalent wear.

The depth-buffer images `office_shirt_wraplayer/four_view_depth_audit.png`
and `pants_four_view_depth.png` compare silhouettes with correct occlusion.
These are static-pose geometric checks. Texture, bone motion, layer ordering,
hidden-surface removal, and general compatibility with every Roblox asset
are not yet validated.

Validation: `python -m pytest tests/test_wrap_layer_fit.py
tests/test_clothing_uv_cage_mapping.py -q -p no:cacheprovider` and manual
`RobloxWearEngine(body_type='female').wear(...)` runs for the four assets.
