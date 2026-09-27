# Blocky radial influence audit: source and destination centers

Date: 2026-09-27. This is an isolated experiment on the official `BlockyCharacter.fbx` and cached shirt `133331049150205`. The production runtime and existing radial control were not changed.

## Question

The archived radial shell already searches authored outer-cage points around source inner-cage vertices. The public Roblox patent US20250265799A1 additionally describes building influence lists for points on both the source cage and destination cage. We checked whether adding destination-cage query centers improves the Blocky shoulder fit.

## Method

`src/clothing/experimental_bidirectional_radial.py` keeps the existing source-centered radial predictions, local one-ring SVD rotations, bounding-box bulk scale, thickness-based radius, and inverse-distance weights. It adds a second query pass centered on destination-cage vertices. Each pass contributes predictions to the same authored outer-cage points. This is an approximation of the patent description, not Roblox's private implementation. `scripts/experiment_bidirectional_radial_blocky.py` evaluates the same cached prism bindings, garment, body mesh, pose, image scale, and four cameras for both variants.

## Results

| Metric | Source centers only | Source + destination centers |
|---|---:|---:|
| Shirt edges stretched over 3x | 957 | 1,060 |
| Garment vertex + face-center samples inside body | 27.82% | 29.17% |
| Inverted samples in used prism cells | 334 | 278 |
| Garment bindings inverted | 263 | 179 |
| Shirt silhouette visible, front | 95.47% | 93.96% |
| Shirt silhouette visible, side | 52.21% | 52.74% |
| Shirt silhouette visible, back | 92.01% | 91.94% |
| Shirt silhouette visible, 3/4 | 83.95% | 83.40% |

The added pass improves the two inversion counts but worsens edge stretch and sampled penetration. The visual change is small; the shoulder remains broken. On this fixture, most destination queries select only one raw outer-cage point at p95 (the paired fallback), so the target pass contributes little spatial blending. This does not establish that the patent's implementation behaves the same: destination thickness and influence-weight details are not fully specified in the public text, and our source mesh carries split UV samples.

Image comparison: [same-scale four-view comparison](blocky_133331049150205_comparison.png). Full metrics and arrays are in `blocky_133331049150205.json` and `.npz`.

## Decision

This variant is **not approved** for production. We already use the patent's radial outer-cage influence idea in `multi_influence_shell.py`, and the earlier radial+prism candidate improved the Blocky shirt from 1,219 to 957 stretched edges compared with the production fixture. We were not implementing the full published influence-list construction because our radial loop only centers queries on source-cage vertices. Adding destination centers alone did not improve the shoulder and introduced measurable tradeoffs. Do not stack this result into the existing radial output.

Next blocker remains contact across the union of body parts plus the garment residual: outer/prism points at the shoulder can enter an adjacent body part before residual transport, while another witness enters its own arm after residual transport. A new contact-aware formulation must be evaluated against those separate causes and the frozen Blocky metrics; simple post-projection and clearance guards already failed in earlier audits.

## Reproduction

```powershell
python scripts/experiment_bidirectional_radial_blocky.py
python -m pytest tests/test_experimental_bidirectional_radial.py -q -p no:cacheprovider
```

The two targeted tests passed on this implementation. The Blocky experiment is diagnostic evidence only, not universal-fit validation.
