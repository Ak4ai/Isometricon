# Wrap frame experiments — 2026-09-26

The baseline includes the already corrected reflected-frame parity. All
alternatives were run against the same five catalog meshes and body cage;
the Blocky control uses the official Blocky R15 FBX cage. No new frame
variant is enabled in clothing production.

| Variant | Shirt | Bomber | Jeans | Dress | Oversized sweater | Blocky shirt |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Existing fitter | 9 | 11 | 33 | 86 | 240 | 1230 |
| Corner-invariant affine map | 8 | 13 | 39 | 119 | 219 | 1229 |
| Rotated shell, global cage scale | 11 | 4 | 29 | 124 | 109 | 1184 |
| Normalized triangle edges, global cage scale | 10 | 4 | 34 | 126 | 102 | 1178 |
| Authored outer-cage faces for garment binding | 8 | 15 | 32 | 83 | 231 | 1200 |

Cells count garment-mesh edges whose length grew by more than 3x. The
measurement does not alone establish silhouette quality, body clearance or
fabric shape. Reports are `WRAP_FRAME_<variant>.json`, produced by
`python scripts/benchmark_wrap_frames.py <variant>`.

The corner-invariant map fixes an algebraic defect but regresses the dress.
Normalized-edge and rotation maps without a global cage scale were worse
than the baseline for several assets. Restoring global scale improves bomber
and sweater substantially but still makes the dress worse. Using the
authored outer cage's own faces is correct to test but not a general cure.
These trials show that changing local shell transport alone cannot fix the
visible-mesh binding across garment regions.

`python scripts/audit_binding_charts.py` produced `WRAP_BINDING_CHARTS.json`.
It reconstructs connected islands from canonical cage UV edges. Of the
baseline edges stretched above 3x, 73/86 in the dress and 30/33 in the jeans
join garment vertices assigned to different cage islands. Only 737/6442
measured dress edges and 738/6646 jeans edges cross islands at all.
These failure edges concentrate at torso–upper-arm boundaries for the dress
(69 of 73), and pelvis–upper-leg boundaries for jeans (26 of 30). The
oversized sweater is different: 134/240 failures occur within a single
island, consistent with its already malformed transferred outer cage.

The earlier one-ring binding experiment reduced dress/jeans stretched-edge
counts to 28/2, but the stored four-view preview still has skirt/leg shape
issues. Edge-length improvement therefore does not justify enabling that
candidate.

The next implementation target is a binding that carries source garment
connectivity and cage UV-chart identity through deformation. Candidate
influences must respect the garment's connected surface and intentional cage
seams, then minimize discontinuity across garment edges. The shell transfer
and garment binding need independent acceptance checks: sweater first fails
at the shell, while dress and jeans mainly fail at visible-mesh binding.
After that, compare identical-camera four-view depth images and body
penetration for all five assets and both bodies before selecting a runtime
algorithm. No item-specific garment-name rules are required.

## Continuous seam blend trial

`python scripts/experiment_chart_blend.py --preview` blends the positions
predicted by neighbouring cage-chart bindings at a garment chart boundary.
It uses source-cage distance and garment connectivity, with no garment-name
rules. The count of edges stretched over 3x drops from 9/11/33/86/240 to
5/3/3/24/101 for shirt/bomber/jeans/dress/sweater. However, it reverses
152/87/253/225/622 garment faces relative to the baseline, and leaves
92/48/184/134/335 faces below one quarter of their original baseline area.
The generated four-view dress and jeans previews visibly develop tears and
missing patches. This blend is rejected despite its edge-length scores.

An offline constrained variant accepts each vertex move only if all of its
incident faces retain their baseline orientation and at least half their
baseline area. It eliminates these newly introduced face inversions and
quarter-area collapses. Its >3x edge counts are 6/6/10/47/162;
the dress and jeans previews still have poor silhouettes, missing coverage,
and unacceptable skirt/leg shapes. The constraint protects local geometry
but does not create a correct correspondence field. Neither variant is
enabled at runtime. Exact numbers and image paths are in
`WRAP_CHART_BLEND.json`.

Next, the binding must be solved as a *single surface correspondence*, not
independent per-vertex projections followed by averaging. Candidate source
cage charts need a consistent assignment over connected garment triangles;
transitions between charts must preserve triangle orientation and area.
Test such a solver first on the dress and jeans, then on the full catalog,
with four-view renders and body coverage alongside edge and face metrics.

`python scripts/audit_chart_transition_consistency.py` tests the boundary
mechanism directly. For every currently stretched cross-chart edge in the
five-asset sample (5/8/30/73/106), mapping *both* endpoints through either
one of their selected cage faces produces an edge shorter than the 3x
threshold. The median disagreement between the two endpoint predictions is
about 0.076/0.060/0.153/0.059/0.369 model units. This establishes that
independent face choice causes these edge breaks; it does **not** select the
correct face, establish body clearance, or prove that the existing shell is
right. Results are in `WRAP_CHART_TRANSITION_CONSISTENCY.json`.

`python scripts/audit_garment_connectivity.py` adds an essential input check
before implementing a surface solver. The exported dress OBJ has 45 raw
vertex-index components; 881 groups of coincident vertices span different
components. The jeans also have 45 components and 554 such groups. Joining
coincident vertices with similarly oriented incident normals (>0.7 dot)
reduces the counts to 24 for both assets. Joining *all* coincident positions
would reduce them to 6 and 13 respectively, but the dress has 130 pairs of
coincident vertices with opposing normals, so such welding could merge
distinct front/back layers. These are diagnostics, not a verified seam map.
The solver must reconstruct intentional seam adjacency from geometry and
UV/topology while retaining separate overlapping panels. Running a graph
optimization on raw OBJ indices would treat many UV splits as disconnected;
blind position welding would create false connections.

The audit now also builds face adjacency from *complete shared geometric
edges* and rejects face pairs with opposing source normals. On that graph,
the dress has 10 face components and the jeans 22, versus 45 raw-index
components each. This is a better starting graph for a surface solver than
raw OBJ indices. It is still provisional: sharp legitimate folds and
overlapping duplicate panels require an explicit seam classification before
this graph can drive production deformation.

A direct seam-gap check narrows the conclusion: every sampled pair of
coincident source vertices still maps to exactly the same target position
under the current pointwise fitter (maximum measured gap 0 in all five
assets). Thus OBJ index splitting is a graph-construction issue for a future
surface solver, **not an established cause of the current visible holes**.
The independently selected cage faces across *noncoincident neighbouring
vertices* remain the demonstrated edge-break mechanism. Do not weld the
source OBJ as a standalone fix.

## Whole-surface gradient trial

`python scripts/experiment_surface_poisson.py --preview` assigns one nearby
cage frame to each garment triangle, transports all three of its edges
together, then solves a global least-squares surface with anchors and
compatible duplicate-vertex seam constraints. It uses only NumPy at runtime
and does not modify the production fitter. The >3x edge counts drop from
9/11/33/86/240 to 2/0/1/10/14, but the output reverses
236/121/298/247/770 faces relative to the baseline. The four-view dress
and jeans previews still show missing patches, folds, and poor skirt/leg
silhouettes. This candidate is rejected; `WRAP_SURFACE_POISSON.json` and
the `surface_poisson_*` images contain the results.

This is a useful falsification: solving edge continuity globally does not
solve oriented surface fitting. A viable solver needs signed face-area or
injectivity constraints, source garment panel identity, and a target cage
field whose correspondence is itself validated. More edge-score-only
variants of this Poisson model would repeat the same failure.

## Outer-cage origin of the skirt/leg failures

`python scripts/audit_outer_cage_clearance.py --preview` renders only the
region where each authored outer cage departs from its reference body cage.
The source dress cage shows one coherent skirt silhouette; the transferred
target cage already has disconnected-looking horizontal bands and side
spikes before the visible dress mesh is fitted. The source jeans cage shows
two baggy legs; the transferred target cage visibly loses their clean
separation and has spikes. The relevant images are `source_outer_cage_*`
and `outer_cage_*`, with measurements in `WRAP_OUTER_CAGE_CLEARANCE.json`.
The outward-normal offset sign is retained on about 98.5% of substantive
points for dress and 98.4% for jeans, so this is a shell *shape/continuity*
failure, not a wholesale inside-out inversion. These images use the cage
surface as the source-body preview, not the original Roblox render.

`python scripts/experiment_shell_global_affine.py --preview` provides a
control: a single least-squares reference-body-to-target-body affine map
transports the authored shell displacement without local leg-frame
rotations. Its dress outer cage recovers a coherent skirt-like silhouette;
the visible dress also looks substantially less torn in the four-view
preview, despite its >3x edge count worsening from 86 to 107. The jeans
still look wrong, and the shirt regresses from 9 to 15 stretched edges.
The sweater has many additional face reversals. This control is **not** a
universal replacement. It establishes that the shell-transfer frame field
is a major cause of the dress failure, while visible-mesh binding remains a
separate issue. Results and images are in `WRAP_GLOBAL_SHELL.json` and the
`global_shell_*` files.

The implementation focus should therefore move upstream to a continuous,
multiple-influence shell field that preserves garment bulk across the leg
and torso transitions. A global affine map is a useful shape-preserving
control; local body frames are needed for close-fitting pieces. Acceptance
must cover both shell images and final mesh orientation/coverage, not edge
counts alone.

## Adaptive shell-frame trial

`python scripts/experiment_shell_adaptive.py --preview` compares three
garment-agnostic ways to interpolate between local shell transport and the
global affine control. One uses authored outer-cage offset relative to cage
edge length; another uses the RMS disagreement among local triangle-frame
predictions for each cage vertex; the third combines both. The disagreement
weight is the most useful of these controls. Its visible dress preview has a
more continuous skirt than the current local transfer while changing only
25 face normals by over 90 degrees relative to baseline, versus 220 with
the fully global shell. The office shirt falls from 9 to 6 edges stretched
over 3x and has 23 changed face normals. However, the dress still has 91
stretched edges (baseline 86), jeans still show a poor leg silhouette, and
the oversized sweater remains distorted. The distance-only blend improves
the dress skirt too, but creates 159 changed face normals there and 1,318
on the sweater. None is accepted as a universal runtime map.

The experiment supports the user's observation that the global skirt result
is a real diagnostic improvement. It also narrows the likely next step: use
a spatially coherent, multiple-influence shell transformation with explicit
surface-orientation checks, then address visible-mesh binding. Per-vertex
interpolation of two predicted cage positions is not enough. Full metrics
and four-view images are in `WRAP_ADAPTIVE_SHELL.json` and `adaptive_*`.

## Direct inner-reference binding control

`python scripts/experiment_inner_reference_binding.py --preview` tests the
architectural distinction in Roblox's public Cage Mesh Deformer description:
the visible mesh is projected to the garment's reference/inner cage, then
transported directly to the target body cage. It leaves the production
outer-cage binding untouched. Source and target cages are compared in their
proper parent/engine coordinate frames; four degenerate reference faces are
excluded (six for the sweater). The same binding with an identity target
reproduces source vertices within 5e-16 across all five garments.

The direct-inner fit reduces >3x garment edges from 9 to 5 for the office
shirt and from 86 to 43 for the dress, but raises jeans from 33 to 42.
The dress preview has fewer broken bands yet develops lateral skirt fins;
the jeans still lose clear leg separation, and the sweater is unusable.
The p99 distance of garment vertices from the source inner cage is 0.462
for the dress and 0.335 for jeans, versus 0.168 and 0.169 from their outer
cages (native model units). A single nearest-triangle frame extrapolates
much farther when bound to the inner cage. This is evidence against a
*simple swap* of binding surfaces, not evidence against the published role
of the inner cage. The public Roblox description also says inner/outer
difference informs thickness; this control omits such multi-influence and
bulk handling. See `WRAP_INNER_REFERENCE_BINDING.json` and
`inner_reference_*` four-view previews.

## Paired dual-cage prism control

`python scripts/experiment_dual_cage_prism.py --preview 114590471167431
109837605892174 133331049150205` tests a coherent composition of the
inner and outer stages. Each visible garment point is located in a prism
between *corresponding* authored reference and outer-cage triangles. Its
barycentric coordinates and depth between the cages are then evaluated in
the paired target body and transferred target outer cage. No garment name,
class, or fixed per-garment interpolation factor enters the map. It is an
offline geometric control, not a reproduction of Roblox's engine.

For the dress, the current baseline has 86 edges stretched >3x; the paired
prism gives 41 with the local shell and 44 with the global shell. The global
prism preview has a more coherent skirt and fewer protruding fins than the
direct inner-cage control. For jeans, the count falls from 33 to 14 with the
local shell and 2 with the global shell; however the legs still look fused
in the four-view images. Relative to baseline, hundreds of garment faces
also rotate over 90 degrees, so the lower edge counts do not establish a
valid surface. Source-prism p99 residual is ~0.160 for dress, ~0.012 for
jeans, and ~0.047 for office shirt (native model units). Being geometrically
near a cage prism is insufficient when multiple body regions offer competing
prisms, especially around pelvis and legs.

The control supports composing the successful ideas as **one mapped volume**
rather than chaining unrelated post-fixes. A production approach still needs
chart/part-aware correspondence and continuous influence across connected
garment regions, plus orientation and coverage checks. Metrics and image
paths are in `WRAP_DUAL_PRISM.json`; preview files are `dual_prism_*`.

The five-asset run also checks bomber and sweater. The adaptive prism reduces
their >3x edge counts from 11 to 5 and 240 to 115, respectively, but the
four-view bomber and sweater images have poor silhouettes and many face
normal changes (60 and 1,183 versus baseline). The control is therefore a
promising *composition model*, not an accepted universal fitter. Its next
missing piece is chart-aware, surface-consistent prism selection: minimum
distance alone can pick the wrong side or leg where several body regions
overlap. No runtime path has been changed.
