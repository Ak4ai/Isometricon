# Static garment-to-cage binding audit

Later correction: the cage overlay in
`office_shirt_wraplayer/source_garments_depth.png` omitted `ReferenceOrigin`.
Use `office_shirt_wraplayer/source_garments_depth_corrected.png` when assessing
source garment versus reference cage; see `SOURCE_OVERLAY_DECISION.md`.

Run `python scripts/audit_wrap_bindings.py` to regenerate the per-asset JSON
and vertex-colored OBJ files. The OBJ colors show which R15 cage part each
visible garment vertex selected. Values are from the same source-cage nearest
triangle search as the production WrapLayer fitter.

| Asset | Vertices | Edges >3x after retarget | p99 edge stretch | Cross-part edges >3x |
|---|---:|---:|---:|---:|
| Oversized sweater 16185652164 | 2984 | 240 | 4.33x | 60 |
| Bomber 72628400373948 | 1989 | 11 | 1.65x | 7 |
| Office shirt 133331049150205 | 2269 | 11 | 1.65x | 5 |
| Cargo pants 16899958482 | 4765 | 2 | 1.52x | 1 |

The sweater has 399 vertices assigned to upper-leg cage faces and 542 to
hand cage faces. Its worst edge grows 12.23x. However, several of the worst
edges have *both* endpoints assigned to the same part. Therefore, simply
forcing a sleeve-to-arm label is insufficient: triangle assignment and the
local deformation field also need spatial continuity. Some clothing may
legitimately approach hands or thighs, so counts alone are not proof of a
wrong assignment for every vertex.

The output confirms that this garment is an outlier under the current
nearest-triangle method. The production quality guard still rejects it and
uses the existing fallback. No unvalidated fitting change was enabled.

Next experiment: form several source-cage triangle candidates per garment
vertex, then select them jointly across garment mesh edges using source
distance, face normal agreement, part affinity, and target edge-distortion
cost. Compare against all four assets, and keep it only if the sweater
improves without regressions. Preserve original FileMesh skinning separately
for animated poses; missing weights do not by themselves explain a static
pose distortion.

## One-ring coherent binding experiment

`python scripts/experiment_wrap_binding.py` considers each vertex's current
triangle and triangles selected by its neighbouring garment vertices. It
chooses assignments using source distance and excessive target edge stretch.
This is an offline experiment, not enabled in the runtime fitter.

| Asset | Edges >3x, baseline | Edges >3x, experiment | p99, baseline | p99, experiment |
|---|---:|---:|---:|---:|
| Sweater | 240 | 89 | 4.33x | 3.15x |
| Bomber | 11 | 4 | 1.65x | 1.63x |
| Office shirt | 11 | 1 | 1.65x | 1.49x |
| Cargo pants | 2 | 0 | 1.52x | 1.51x |

The four-view depth image `experiment_binding_four_view.png` shows that the
sweater still has pronounced shoulder spikes and torso gaps despite the
numerical improvement. The current one-ring candidate set cannot repair a
whole connected sleeve region already attached to the wrong cage region. The
next prototype should add broader candidate regions and a more explicit
surface/part affinity term, then compare silhouette and topology as well as
edge stretch. Do not activate this version in production.

## Upstream outer-cage failure

`python scripts/experiment_wrap_mls.py` tested two continuous weighted-affine
fields as further offline alternatives. Both worsen the sweater. More
importantly, it measures distortion *before* visible garment projection:

| Sweater transfer | p99 edge stretch | Edges >3x (source edge >= .01) |
|---|---:|---:|
| Garment reference cage to female body cage | 1.53x | 0 |
| Garment reference cage to its authored outer cage | 7.68x | 1404 |
| Authored outer cage to our transferred outer cage | 4.61x | 192 |

For the office shirt, the corresponding authored inner-to-outer p99 is
1.74x and our outer-cage transfer has no edge above 3x. The sweater's outer
cage is therefore a much harder geometry case by itself. Large authored
inner-to-outer expansion can be legitimate for oversized clothes; it is not
evidence that the asset is corrupt. The current local-frame shell transfer
cannot faithfully carry it to the female body. UV duplicates in the mesh
decode were also checked: all vertices with the same cage UV have the same
position to within ~3e-7, so duplicate UVs are not the cause.

Any next fitter should first validate the *transferred outer cage* and
repair its deformation while preserving the authored shell. Only then does
optimizing visible-mesh-to-outer-cage bindings make sense. The continuous
field attempted here produced 424 garment edges >3x for the sweater, versus
240 in baseline, so it was rejected.

## Part-affine shell experiment

`python scripts/experiment_wrap_part_affine.py` fits one linear transform
per R15 body part from the garment reference cage to the female body cage.
It carries only the authored inner-to-outer shell offset through that
transform and pins the result to the exact target cage position at each UV.
This reduced the sweater's transferred outer-cage edges above 3x from 192
to 4, and visible-garment edges above 3x from 240 to 4. It also reduced
severe edge stretch in the bomber. However, office-shirt p99 visible edge
stretch rose from 1.65x to 2.01x, and cargo pants edges above 3x rose from
2 to 33. This variant is not enabled in production.

The four-view image `part_affine_four_view.png` shows a second limitation:
the sweater's shoulder spikes mostly disappear, but the neckline and torso
sit too low, exposing the chest. Inspection of
`office_shirt_wraplayer/source_garments_depth.png` shows the *raw source*
sweater mesh already sits low relative to its original mannequin/cage,
unlike the office shirt. The sweater MeshPart contains a skinned FileMesh
with 15 bones; the current OBJ extraction ignores the skinning block.
It is plausible that the missing rest/bind pose transform contributes to
this raw source misalignment, but this has not yet been proven by decoding
the bone transforms. The RBXM audit `python scripts/audit_rbxm_structure.py
16185652164` confirms a MeshPart with `HasSkinnedMesh` and a WrapLayer.

The production WrapLayer path now records transferred outer-cage p99 edge
stretch and rejects an asset if that exceeds 2.5x. The known good office
shirt, bomber, and cargo pants remain below that threshold; the sweater
is rejected before a malformed shell can reach the final mesh.
