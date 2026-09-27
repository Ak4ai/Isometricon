# Universal layered-clothing fit audit (2026-09-25)

## What is already sound

- The exported female body's 15 outer cages retain R15 UV correspondence. The
  existing package verifier reports maximum UV export error below 5e-10.
- Garment reference meshes for an office shirt, bomber jacket, oversized
  sweater and cargo pants all expose the same 1709 cage UV locations within
  FileMesh quantization (maximum nearest UV error about 1e-5 for the sampled
  files). The bomber reference differs geometrically from the shirt reference
  by 0.034 Roblox units at the median UV and 0.119 at the largest sampled UV.
- The body cage audit found no exposed points on solid cage surfaces in the
  sampled areas. Joint openings were capped temporarily for the audit, and
  some sampled body points lie outside their individual cage at those caps;
  the union of neighboring cages covered them. This is expected at open joint
  ends but does not validate smooth clothing deformation across those ends.

## Ranked causes of poor fit

1. **Per-asset placement is discarded.** `wear_engine.py` hard-codes a Y
   translation of +1.222 for female tops. Six cached layered assets have
   readable `CageOrigin.Y` values ranging from -1.089 to +1.005. The office
   shirt declares -1.089375; aligning with it reduces median distance to
   its own outer cage from 0.041 to 0.028 Roblox units relative to +1.222.
   `ReferenceOrigin` can also differ from `CageOrigin`. Full CFrame handling
   is needed before claiming generality.
2. **The runtime does not use the garment's inner/reference and outer cages.**
   Its current female top path projects the visible OBJ directly onto a
   single R15 mannequin cage and clips the garment's signed distance to a
   small fixed range. The RBXM supplies `ReferenceMeshId` and `CageMeshId`.
   The sampled jacket reference shares UVs with the shirt reference but not
   identical positions, so one frozen source shape is not valid for all.
3. **The experimental two-stage mapping keeps garment offsets in global
   axes.** The sampled garment upper-arm cage axis is about 29.2 degrees
   from vertical; the target upper-arm cage axis is about 19.6 degrees.
   Lower arms are about 35.2 versus 28.0 degrees. Offsets around shoulders
   and sleeves therefore need a local deformation frame/Jacobian or bone
   transfer rather than a fixed coordinate swap and scale. This is a strong
   explanation for bulky shoulder silhouettes, but it is not yet isolated
   by an A/B render.
4. **Surface selection is ambiguous at joints.** The current runtime picks
   nearby triangle centroids, chooses torso/arm surfaces with heuristics, then
   blends by X thresholds and smooths a seam ring. Joint openings are not
   represented by closed cages. A wrong triangle or body-part choice can
   pull cloth through the body, even when every UV match is correct.
5. **The loader and garment types are incomplete.** Cached sweater and pants
   references are FileMesh 2.00, which the runtime decoder rejects. The
   female UV cage path only handles tops; bottoms still use the older fitting
   path. The RBXM also contains layering/attachment metadata that the runtime
   does not yet apply. The sampled cached assets have six distinct reference
   mesh IDs. Some share geometry within quantization; others do not.
6. **Visual verification was misleading.** The previous Matplotlib four-view
   preview sorted the body and shirt as separate transparent collections.
   `four_view_depth_audit.png` uses a true per-pixel depth buffer. It confirms
   front is +Z and back is -Z in the project's native convention. The old
   runtime has gaps in the torso; the prototype covers the central torso on
   both sides but still deforms shoulders, collar and sleeves poorly.

## What to build next

Parse `CageOrigin`, `ReferenceOrigin`, `ReferenceMeshId`, `CageMeshId` and
the attachment transform from each RBXM; decode both FileMesh 2.00 and Draco
reference cages; match their 1709 cage UV locations to the target body cage
with tolerance appropriate to mesh quantization. Then bind visible garment
vertices to the garment outer cage in its local space, transfer the
reference-to-outer displacement through local frames that follow the target
body pose, and use a deterministic per-part binding near joints. Validate
front, back, side and 3/4 with depth buffering, and test tops, coats and
bottoms separately before enabling the path by default.

This audit does not claim byte-for-byte equivalence with Roblox's private
deformer. It identifies observable data and geometric failures in this
project's current implementation.
