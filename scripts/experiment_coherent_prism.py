"""Run one graph-coherent prism-binding candidate on the frozen six-case suite."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.radial_validation_metrics import distortion, body_penetration, normals, seam_report
from scripts.test_r15_shirt_transfer import depth_preview
from src.clothing.experimental_canonical_radial import canonical_cages, normal_frames
from src.clothing.experimental_coherent_prism import coherent_prism_binding

INPUT = ROOT / "artifacts/clothing_audit/radial_frames"
OUT = ROOT / "artifacts/clothing_audit/coherent_prism"
CASES = ("female_133331049150205", "female_72628400373948",
         "female_109837605892174", "female_114590471167431",
         "female_16185652164", "blocky_133331049150205")


def binding_fingerprint(data, binding):
    i, o, f = data["reference_parent"], data["outer_parent"], data["projection_faces"]
    valid = (np.linalg.norm(normals(i, f), axis=1) > 1e-8) & (
        np.linalg.norm(normals(o, f), axis=1) > 1e-8)
    digest = hashlib.sha256()
    for x in (i, o, f[valid], data["garment"]):
        digest.update(x.tobytes())
    digest.update((ROOT / "scripts/experiment_dual_cage_prism.py").read_bytes())
    return str(binding["fingerprint"]) == digest.hexdigest() and np.array_equal(binding["faces"], f[valid])


def edge_ratio(data, mesh, a, b, scale):
    source = np.linalg.norm(data["garment"][a] - data["garment"][b])
    return float(np.linalg.norm(mesh[a] - mesh[b]) / (source * scale))


def main():
    OUT.mkdir(exist_ok=True)
    report = dict(method="graph-coherent prism face reassignment, fixed lambda=1, four ICM rounds, guard against new wrong-way face orientation",
                  cases={})
    for case in CASES:
        data = dict(np.load(INPUT / f"{case}.npz"))
        binding = dict(np.load(INPUT / f"{case}_binding.npz"))
        old = dict(np.load(INPUT / f"{case}_outputs.npz"))
        previous = json.loads((INPUT / f"{case}.json").read_text(encoding="utf-8"))
        if not binding_fingerprint(data, binding):
            raise ValueError(f"Stale binding fixture: {case}")
        scale = previous["common_metric_scale"]
        baseline = old["radial_previous"]
        shell = old["radial_previous_shell"]
        candidate, audit = coherent_prism_binding(data, binding, shell, baseline, scale)
        selected = audit.pop("selected_faces")
        r, o, t, f, inverse = canonical_cages(
            data["reference_parent"], data["outer_parent"], data["target_body"],
            data["projection_faces"], data["uv_index"])
        frames, _ = normal_frames(r, t, f, int(data["cage_normal_sign"]))
        for name, mesh, face_ids in (("radial_prism", baseline, binding["face_ids"]),
                                     ("coherent_candidate", candidate, selected)):
            vertex_frames = frames[inverse][binding["faces"][face_ids]].mean(axis=1)
            stats = distortion(data["garment"], mesh, data["garment_faces"], scale,
                               vertex_frames, int(data["cage_normal_sign"]))
            samples = np.vstack((mesh, mesh[data["garment_faces"]].mean(axis=1)))
            penetration = body_penetration(samples, data["body"], data["body_faces"])
            report["cases"].setdefault(case, {})[name] = dict(distortion=stats, penetration=penetration)
        report["cases"][case]["audit"] = audit
        report["cases"][case]["shell_seams"] = seam_report(
            data["outer_parent"], shell, data["uv_index"])
        if case == "female_109837605892174":
            report["cases"][case]["witness_edges"] = {
                str((a, b)): {name: edge_ratio(data, mesh, a, b, scale)
                              for name, mesh in (("radial_prism", baseline),
                                                 ("coherent_candidate", candidate))}
                for a, b in ((2396, 2397), (734, 737))}
            report["cases"][case]["witness_faces"] = {
                str(v): dict(previous=int(binding["face_ids"][v]),
                             candidate=int(selected[v])) for v in (2396, 2397, 734, 737)}
        np.savez_compressed(OUT / f"{case}.npz", baseline=baseline, candidate=candidate,
                            selected_faces=selected)
        common = np.vstack((data["body"], baseline, candidate))
        panels = []
        for name, mesh in (("radial_prism", baseline), ("coherent_candidate", candidate)):
            path = OUT / f"{case}_{name}.png"
            visibility = depth_preview(data["body"], data["body_faces"], mesh,
                                       data["garment_faces"], path, shared_garment_vertices=common)
            report["cases"][case][name]["visibility"] = visibility
            panels.append(Image.open(path).convert("RGB"))
        sheet = Image.new("RGB", (panels[0].width, sum(x.height + 24 for x in panels)), "white")
        y = 0
        for name, panel in zip(("radial_prism", "coherent_candidate"), panels):
            ImageDraw.Draw(sheet).text((8, y + 4), case + " " + name, fill="black")
            sheet.paste(panel, (0, y + 24))
            y += panel.height + 24
        sheet.save(OUT / f"{case}_comparison.png")
        row = report["cases"][case]
        print(case, json.dumps({name: dict(edges=part["distortion"]["historical_length_mask"]["over_3"],
            compressed=part["distortion"]["area"]["under_tenth"],
            orientation_proxy=part["distortion"]["orientation_disagreements_with_inner_frame"],
            penetration=part["penetration"]["penetrating_fraction"])
            for name, part in row.items() if name in ("radial_prism", "coherent_candidate")}),
            "changed", audit["vertices_changed"], flush=True)
        (OUT / "SUMMARY.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
