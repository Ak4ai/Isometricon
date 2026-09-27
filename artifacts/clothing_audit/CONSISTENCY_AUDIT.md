# Layered clothing consistency audit

The system is useful for a subset of static female Roblox layered assets,
but it is not yet a consistent general-purpose Roblox clothing fitter.
This audit uses `python scripts/audit_cached_wrap_compatibility.py`, direct
runtime wear calls, and depth-buffer images in four orientations. The
compatibility JSON is `CACHED_WRAP_COMPATIBILITY.json`.

Of 21 cached layered-clothing RBXMs, 8 now have both cage meshes cached and
could be audited without additional downloads. Six pass the current numeric
WrapLayer guard: office shirt, bomber, pink cargo pants, bikini, ruffled
dress, and black designer jeans. Jersey and oversized knitted sweater are
rejected to the old fitting path. Thirteen clothing RBXMs lack cached cage
meshes and are not included in this quality rate.

Passing the guard is not equivalent to a good visual fit. The office shirt,
bomber, pink cargo pants and bikini have plausible static silhouettes in the
available four-view checks. The ruffled dress has an exaggerated side hem
and 125 garment edges stretched more than 3x. The black designer jeans
look crushed near the legs and have 33 edges stretched more than 3x. The
fallback is worse for both: the dress loses its skirt, and the jeans expose
large areas of legs. See `compatibility_four_view.png` and
`dress_jeans_fallback_four_view.png`. The current guard checks garment-to-
outer-cage distance and outer-cage edge distortion, but not distortion of
the visible garment. A visible-edge guard alone would reject these two
without providing a usable replacement.

The bikini initially failed because its reference cage had 1708 unique UVs
versus 1709 body UVs; seven were shifted by 0.0015-0.0082 UV units. Its
inner and outer cages agree with each other. A bounded nearest-UV matching
rule now accepts only up to eight shifted UVs below 0.01, provided unique
source UVs map injectively to distinct body UVs. The bikini then passes
runtime with source-distance median 0.0075, p99 0.0384, no degenerate
faces and outer-cage edge p99 1.62. The four-view silhouette is plausible.
The fitted-OBJ cache tag was raised to v6 so the application regenerates
old v5 results after this mapping change.

The jersey is rejected because visible-mesh-to-outer-cage p99 distance is
0.235, above the 0.2 limit, although its cage transfer is stable and its
direct WrapLayer preview is plausible. The fallback looks at least as good
in four views, so the distance threshold was not relaxed merely to raise
the acceptance count. See `jersey_compare_four_view.png`.

Additional unimplemented pieces prevent Roblox-equivalent behavior:

- Skinned FileMesh data and bone rest/animation transforms are discarded
  when converting meshes to OBJ. The oversized sweater has 15 bones and its
  raw visible mesh already sits low against its own cage. The exact role of
  bind-pose transforms in that static mismatch is not yet proven.
- The engine handles one top and one bottom independently. It does not
  compose multiple WrapLayer outer cages by `Order` or apply `AutoSkin`.
- `BindOffset` other than identity is explicitly rejected. Attachment
  alignment and `ReferenceOrigin`/`CageOrigin` are handled only to the extent
  tested by current cached assets.
- The character renderer cuts body skin and adjusts hems/waists with name
  and geometry heuristics. These can differ from the Roblox hidden-surface
  and layering behavior, especially for open tops and dresses.
- Existing tests mostly check parser/math invariants and the old fitting
  path. They do not establish visual correctness across assets, animated
  poses, texture orientation, or layered outfits.

Priority: preserve mesh skinning and investigate rest/bind pose; improve
visible-mesh binding and validate rendered shape; then add ordered layer
composition and pose tests. A larger asset matrix is needed before calling
the fitter universal. The current targeted tests and 477-test suite pass
with one unrelated pre-existing test deselected.
