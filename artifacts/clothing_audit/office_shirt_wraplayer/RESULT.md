# Office shirt WrapLayer audit

The cached RBXM contains `WrapLayer.CageMeshId = 78642992491592` and
`WrapLayer.ReferenceMeshId = 80307990380242`. Both downloaded meshes have
1709 distinct UV positions. Their UVs match the R15 body cage within
1.42e-5, but only 1410 of 2690 UV triangles match exactly because some
quads use different diagonals.

The RBXM stores `CageOrigin = (0.007, -1.089375, 0.003094)` and
`ReferenceOrigin = (0.007, -1.089375, -0.005759)`, with identity rotation.
The runtime's hard-coded `+1.222` Y translation differs by 0.132625 Roblox
units from the garment's cage origin. Applying the recorded origin and
projecting the shirt onto its own outer cage gives a median source distance
of 0.028 Roblox units, compared with 0.041 using `+1.222` and about 0.150
with no translation.

The prototype transfers the garment reference UV positions to the female
body cage, adds the garment outer cage displacement, and projects the
visible shirt through this changed cage. It saves `shirt_reference_to_body.obj`.
The corrected orthographic depth-buffer preview `four_view_depth_audit.png`
shows central torso coverage of 97.8% front and 85.5% back for the current
runtime, versus 100% on both sides for the prototype. The prototype still
has bulky shoulders, an incorrect sleeve silhouette, and gaps near the
collar and armpits, so it is not connected to `wear_engine.py`.

The camera labels are correct: `+Z` is front in the native renderer and
`-Z` is back. The earlier Matplotlib four-view image has correct camera
labels but incorrect occlusion because of the renderer's cross-mesh sorting.
Use `four_view_depth_audit.png` for visual assessment.
