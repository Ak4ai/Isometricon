# Review of the universal clothing fitter — 2026-09-26

> Follow-up experiments and UV-chart localization are in
> `WRAP_FRAME_EXPERIMENTS.md`. The algebraically corrected local map cannot
> replace the runtime map alone: it regressed the dress and jeans.

## Verified errors and limits

1. **Reflected frames were handled in only one of two deformation stages.**
   The office shirt transferred to its own reflected reference cage had an
   exact outer cage but visible-mesh error 0.321721 (native asset units).
   Passing the same frame parity to the visible-mesh transfer makes that
   error zero. A regression test reproduced the failure before the fix.
   Identity and proper rotation controls also remain exact. Cache version
   is now v7. This is a coordinate fix, not a solution to all fitting defects.

2. **The local transform depends on triangle corner numbering.**
   `_local_map` constructs an orthonormal frame around the first edge,
   rescales two axes, and drops tangential shear. Cyclically permuting all
   three corners of the same source/target triangles changes the resulting
   matrix by up to 0.885398 in the synthetic audit. Geometry and winding are
   unchanged. This remains unresolved; raising the scale cap does not fix it.

3. **Scale policy is implicit and clamped.** A target scaled uniformly by 2
   does not reproduce a scaled garment: maximum visible-mesh error 0.124414.
   The cap of 1.5 changes shell thickness as well as tangential displacement.
   A deformation model may intentionally preserve thickness, but that must
   be a declared physical policy distinct from unit/frame conversion.

4. **Incompatible constraints exist for position-only fields.** For the
   Blocky shirt, grouping outer-cage source positions rounded to 5 decimals
   gives 77 groups whose target locations differ from their mean by more
   than 0.01; maximum spread is 0.155262. Some groups may be distinct touching
   regions rather than seams. They must not be welded blindly. A spatial
   function alone cannot exactly satisfy multiple outputs at one input.
   Source chart/topology and intended seams must be part of the binding.

5. **The previous MLS experiment is not guaranteed continuous.** Its hard
   k-nearest-neighbour selection changes the fit discontinuously as neighbours
   enter/leave the selected set. Failure of that particular approximation
   does not establish that a properly constructed continuous field fails.

6. **The validation metric mixed used and unused cage regions.** The reference
   to Blocky edge p99 is ~19.38 in the hands, but this shirt binds zero visible
   vertices there. Large stretching is also expected when different body
   proportions are mapped. Neither global edge stretch nor projected blue
   pixel coverage proves incorrect geometry or successful fitting by itself.
   The runtime's fixed global outer-cage p99 threshold (2.5) is not a universal
   compatibility criterion.

7. **Runtime remains a female single-body fitter.** It selects
   `r15_female_cages`, rejects non-identity BindOffset, assumes 2690 reference
   faces, discards the authored outer-cage faces, and fits each asset to the
   original body. It does not compose successive garment cages by layer order.
   Source skinning is dropped during OBJ conversion. A final female-specific
   X reflection is another convention to replace with explicit coordinate
   transforms before supporting asymmetric targets. These are capability
   gaps, not proven explanations for every current screenshot.

## Corrections to previous evidence

- The previous 0.04793-to-1.0 edge example used native file units. Calling
  these values centimetres/metres was not justified.
- The diagnostic FBX reader ignores model and hierarchy transforms. In this
  Blocky file the inspected UpperTorso/UpperArm mesh objects are root children
  and have near-identity transforms (outer-cage translation ~0.0008615).
  That limitation does not explain the large current distortions, but the
  reader cannot serve as a general FBX importer.
- Four-view depth previews previously fitted horizontal and vertical axes
  independently and refitted each angle. This distorted the apparent body
  proportions, particularly in the side view. They now share an isotropic
  projection scale. Pixel counts from before/after this camera change are
  not directly comparable.
- Closing a cage with temporary caps was a condition of our volumetric
  experiment, not evidence that a Roblox cage must be remodeled that way.
- A full reference-to-Blocky mapping already has large local changes. That
  alone does not establish invalid UVs or invalid user-authored cage geometry.

## Public technical reference

[Roblox's published linear-cage-deformer description](https://patents.google.com/patent/US20250265799A1/en)
separates garment fitting from outer-cage propagation. It describes local
frames, area-weighted offsets, and a later multiple-influence method using
rotations, garment thickness and bulk scale. It explicitly discusses skirt
and dress crossover when their halves follow separate legs. This is a useful
algorithmic specification to evaluate, not proof of the exact current engine
implementation. The present fitter is not equivalent to those methods.

[WrapLayer metadata documentation](https://raw.githubusercontent.com/Roblox/creator-docs/main/content/en-us/reference/engine/classes/WrapLayer.yaml)
describes BindOffset as an optional binding adjustment and Order as layer
composition order. The current exception describing BindOffset as requiring
rig transfer is not justified by that property alone.

## Concrete implementation sequence

1. Normalize explicit units, coordinate transforms and frame parity for mesh,
   reference cage and outer cage; retain each mesh's topology and metadata.
   Preserve actual source skinning for the later pose stage.
2. Replace the corner-order-dependent local transport with a mathematically
   defined transformation and a declared scale/thickness policy. Require
   invariance to cyclic corner permutation, rigid transforms and coordinate
   conversion; test this on synthetic cages before judging screenshots.
3. Build a compatible multi-influence outer-cage deformation. Distinguish
   intended seams from touching charts; use garment outer-cage geometry to
   keep skirts connected rather than splitting them according to leg labels.
   Do not average conflicting constraints simply because positions coincide.
4. Bind the visible mesh with precomputed weights under a defined spatial
   deformation model; validate reproduction of the authored shape and
   continuity across intended seams. A nearest-triangle projection alone is
   not a guarantee of either property for arbitrarily large pose changes.
5. Compose garment layers in order and transfer pose/skinning separately.
   Evaluate shirt, tight pants, skirt/dress and oversized clothing on both
   official and custom bodies. Measure body penetration, inverted faces,
   seam separation and distortion normalized for intended body scaling.
   Compare images at identical scale. Treat remaining unsupported assets
   explicitly; no assertion that all arbitrary meshes can fit every body.

## Reproduction

`python scripts/audit_wrap_contract.py` writes `WRAP_CONTRACT_AUDIT.json`.
The pre-fix measurements are retained in `WRAP_CONTRACT_BEFORE.json`.
`python scripts/test_r15_shirt_transfer.py` regenerates the Blocky preview.
The 29 targeted tests for WrapLayer, volumetric cages, UV mapping and character
model passed after the parity correction. The Blocky preview still has
visible garment defects and is not an accepted final fit.
