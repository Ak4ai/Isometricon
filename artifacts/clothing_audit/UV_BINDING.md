# Binding the R15 reference cage to the edited target cage

The runtime now loads `assets/models/roblox_reference_cages.obj` as the source cage and `assets/models/female_cages_apose_stage2.obj` as the edited target. The reference OBJ is exported from the local `ClassicMannequin_With-Cages.fbx` snapshot and retains each face corner's UV. The stage-2 target already retains the same reference UV layout.

`load_r15_female_cages` now keeps the UV coordinate for each triangulated face corner. `_align_target_faces_by_uv` finds the target triangle with the same three UV corners and puts its target vertex indices in reference-corner order. The deformer then finds a point on the reference triangle, computes its barycentric weights, and applies those weights to the matching target triangle. Vertex and face array indices are no longer treated as correspondence IDs. If UVs are missing, duplicated ambiguously, or unmatched, the female dual cage is disabled with a diagnostic instead of silently using incorrect indices.

The binding uses **cage UVs**, not the clothing texture UVs. Clothing texture UVs stay with the clothing mesh; its 3D vertices are projected onto the reference cage and transferred through the UV-paired reference/target triangles.

## Validation

- `python scripts/export_stage2_clothing_package.py` exports both the reviewed target and the UV-bearing reference cage.
- `python scripts/verify_stage2_clothing_package.py` verifies the target export against the R15 FBX snapshot and checks UV triangle pairing for all 15 body cages.
- `python -m pytest tests/test_clothing_uv_cage_mapping.py -q` checks reindexed triangles, missing-UV failure, and all 15 exported part mappings.
- `python scripts/test_stage2_runtime_clothing.py` runs a cached shirt through the dual-cage mapper and confirms finite output positions.

The runtime shirt test is a data-path check, not proof of a visually perfect fit. The separate cage/body audit still records local intersections around the pelvis and upper arms, and clothing-specific WrapLayer cage and animation/skin data are not imported by this mesh-only fitting path.
