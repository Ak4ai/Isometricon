# Coherent prism binding: six fixed controls

Decision: **experimental; do not integrate into the runtime.** This test isolates a real binding discontinuity, but it does not solve Blocky shoulders, dress geometry, or body penetration.

## What was tested

`src/clothing/experimental_coherent_prism.py` reassigns an existing garment vertex to a prism face already used by a connected garment neighbor when the two faces are on different cage UV charts. Coincident garment vertices with aligned normals move together, preserving their UV-split seams. The energy combines source-prism residual with normalized garment-edge length error; no garment names or per-asset parameters are used. Four deterministic coordinate-descent sweeps are capped by a face-orientation guard: a previously wrong-way face may be corrected, while a previously correct face cannot become wrong-way under the same frozen baseline frame. The radial shell and all source/target cages are unchanged.

The six archived controls are shirt, bomber jacket, jeans with boots, dress, and sweater on the custom female body, plus the same shirt on official R15 Blocky. The runner checks the source-binding fingerprint before using each archive. All images use the same scale and four views for baseline and candidate. The four-view previews are flat-color depth checks, so they do not verify texture mapping.

Run from the repository root:

```text
python scripts/experiment_coherent_prism.py
python scripts/audit_coherent_prism_outputs.py
python scripts/audit_coherent_prism_witness.py
python -m pytest -q tests/test_wrap_layer_fit.py tests/test_experimental_prism_validity.py tests/test_experimental_prism_constraints.py tests/test_experimental_canonical_radial.py tests/test_blocky_radial_influence_audit.py
```

Complete metrics and per-case meshes are in `coherent_prism/SUMMARY.json` and `coherent_prism/<case>.npz`. Comparison PNGs are in the same directory.

| Control | Edges >3×, normalized | Faces with area <0.1× | Wrong-way orientation proxy | Body penetration samples | Visible front silhouette |
|---|---:|---:|---:|---:|---:|
| Female shirt | 149 → 138 | 7 → 7 | 366 → 349 | 2.30% → 2.34% | 94.3% → 94.3% |
| Female bomber | 116 → 112 | 2 → 1 | 153 → 134 | 1.93% → 1.96% | 94.4% → 94.5% |
| Female jeans/boots | 76 → 71 | 50 → 46 | 239 → 224 | 2.15% → 2.18% | 98.7% → 98.8% |
| Female dress | 190 → 163 | 9 → 10 | 174 → 172 | 1.57% → 1.61% | 96.9% → 96.8% |
| Female sweater | 43 → 37 | 4 → 4 | 366 → 355 | 3.47% → 3.56% | 94.1% → 94.3% |
| Blocky shirt | 957 → 938 | 1 → 1 | 460 → 443 | 27.82% → 27.81% | 95.5% → 95.5% |

The edge count uses the existing source-edge-length ≥0.01 mask and each case's archived RMS scale. Area uses original triangle area and the square of that scale. Body penetration samples garment vertices and triangle centers against closed body components. Visible silhouette fraction is an image-space occlusion measure, **not** a body coverage proof. The orientation metric is a frame-based proxy, not a watertight-mesh proof.

The waist witness on jeans (garment edge 734–737) goes from 7.45× to 0.99×. Vertex 734 switches from prism 1355 to the neighbor's prism 1496. Moving it alone reverses two triangles relative to the old output, but the frozen cage-frame check shows that **both triangles were already wrong-way** and become correctly oriented. This is why a guard against every change of normal direction incorrectly blocked the fix. The earlier boot witness edge 2396–2397 remains 1.17×. There are no newly wrong-way relative reversals under this audit, and aligned coincident UV-split garment vertices stay coincident; source cage shell seams also remain coincident.

The improvement is local. The Blocky shirt still has 938 edges above 3× and 27.81% penetrating samples, with shoulder holes visible from side/back. The dress still has a pronounced side separation and one additional compressed face. Sweater neck/shoulder placement remains visibly poor. Penetration fraction increases slightly on all five female controls. These failures reject runtime integration even though the jeans witness is repaired.

The next blocking question is **where the remaining Blocky shoulder and dress errors arise before local reassignment**: source binding, target prism deformation, or a missing influence/pose relationship. Audit the same failed vertices and triangles through those stages, with source/target prism orientation and distance to the body. A second local edge-energy tweak is not justified by these results. No production clothing algorithm or Blender cage asset was modified.
