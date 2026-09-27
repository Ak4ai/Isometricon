# Focused visual review: dress and jeans

> Later UV-chart audit (`WRAP_BINDING_CHARTS.json`) locates most extreme
> dress edges at torso–upper-arm boundaries (69/86 baseline failures), and
> most extreme jean edges at pelvis–upper-leg boundaries (26/33). The skirt
> silhouette problem remains a separate visual failure; the edge count alone
> does not measure its shape.

The raw source meshes show a continuous skirt and two separate jean legs in
`source_garments_additional_corrected.png`. The older
`source_garments_additional.png` misaligns the overlaid reference cage because
it omits `ReferenceOrigin`; see `SOURCE_OVERLAY_DECISION.md`. The WrapLayer
output in `dress_jeans_fallback_four_view.png`
introduces an exaggerated sideways skirt flare and crumpled/fused-looking
jean legs. The old fallback is worse for these assets, so switching to it
is not a fix.

| Asset | Source-to-outer distance p99 | Outer-cage stretch p99 | Visible edges >3x | Such edges crossing selected cage parts |
|---|---:|---:|---:|---:|
| Dress 114590471167431 | 0.168 studs | 1.41x | 125 | 108 |
| Jeans 109837605892174 | 0.169 studs | 1.53x | 33 | 29 |

The cage itself passes current geometric checks. Most excessive stretching
occurs when adjacent visible-mesh vertices bind to triangles belonging to
different R15 body parts. This is direct evidence of binding discontinuity.
The dress selects torso triangles for 2337 of 3042 vertices, with some
lower-torso and upper-leg faces near the skirt; the jeans select lower
torso, both legs and feet. A one-ring candidate experiment reduces edges
above 3x to 28 (dress) and 2 (jeans), but the depth-buffer silhouette
remains nearly unchanged (`dress_jeans_coherent_four_view.png`). Local edge
repair alone does not restore the authored skirt or jean-leg shapes.

To fix this generally, visible-mesh binding must respect coherent garment
regions and preserve the two leg components/skirt panel continuity across
body-part seams. Validation must check visible-garment edge distortion and
silhouette in addition to outer-cage quality. Any new binding must be
compared against the office shirt, bomber, bikini, and pink cargo pants.
