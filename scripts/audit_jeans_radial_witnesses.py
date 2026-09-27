"""Replay cached jeans witnesses across production, radial shell, and prism binding."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.experiment_canonical_radial import evaluate_binding
from scripts.audit_jeans_foot_binding import chart_labels
from scripts.experiment_shell_global_affine import remap_visible
from scripts.radial_validation_metrics import distortion, body_penetration
from scripts.test_r15_shirt_transfer import depth_preview
from src.clothing.wrap_layer_fit import _local_map
from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.multi_influence_shell import transfer_outer_cage_radial

ASSET = "109837605892174"
BASE = ROOT / "artifacts/clothing_audit/radial_frames" / f"female_{ASSET}"
OUT = ROOT / "artifacts/clothing_audit/female_jeans_runtime"
EDGE = (2396, 2397)
BOOT = 1464


def prism_terms(data, binding, shell, vertex):
    face_id = int(binding["face_ids"][vertex])
    face = binding["faces"][face_id]
    t = float(binding["levels"][vertex])
    bary = binding["bary"][vertex]
    residual = binding["residual"][vertex]
    inner, outer = data["reference_parent"][face], data["outer_parent"][face]
    target_inner, target_outer = data["target_body"][face], shell[face]
    source = (1 - t) * inner + t * outer
    target = (1 - t) * target_inner + t * target_outer
    transform = _local_map(*source, *target, normal_sign=int(data["cage_normal_sign"]))
    if transform is None:
        transform = _local_map(*inner, *target_inner, normal_sign=int(data["cage_normal_sign"]))
    if transform is None:
        transform = _local_map(*outer, *target_outer, normal_sign=int(data["cage_normal_sign"]))
    base = bary @ target
    mapped_residual = transform @ residual
    return dict(face=face.tolist(), face_id=face_id, layer_t=t,
                source_residual_norm=float(np.linalg.norm(residual)),
                target_base=base.tolist(), transported_residual=mapped_residual.tolist(),
                reconstructed=(base + mapped_residual).tolist())


def main():
    data = dict(np.load(BASE.with_suffix(".npz")))
    binding_path = BASE.with_name(BASE.name + "_binding.npz")
    binding = dict(np.load(binding_path))
    outputs = dict(np.load(BASE.with_name(BASE.name + "_outputs.npz")))
    runtime = dict(np.load(OUT / "stages.npz"))
    previous = json.loads(BASE.with_suffix(".json").read_text(encoding="utf-8"))

    # The saved prism bindings must belong to these exact source cages/mesh
    # and the current binding implementation before using them as evidence.
    f = data["projection_faces"]
    i, o = data["reference_parent"], data["outer_parent"]
    norm_i = np.linalg.norm(np.cross(i[f[:, 1]] - i[f[:, 0]], i[f[:, 2]] - i[f[:, 0]]), axis=1)
    norm_o = np.linalg.norm(np.cross(o[f[:, 1]] - o[f[:, 0]], o[f[:, 2]] - o[f[:, 0]]), axis=1)
    usable = (norm_i > 1e-8) & (norm_o > 1e-8)
    digest = hashlib.sha256()
    for item in (i, o, f[usable], data["garment"]):
        digest.update(item.tobytes())
    digest.update((ROOT / "scripts/experiment_dual_cage_prism.py").read_bytes())
    if str(binding["fingerprint"]) != digest.hexdigest() or not np.array_equal(binding["faces"], f[usable]):
        raise ValueError("Saved prism binding does not match current source/cage implementation")
    if not np.array_equal(data["baseline"], runtime["wrap_before_runtime_postprocess"]):
        raise ValueError("Archived production fit differs from fresh runtime")
    engine = RobloxWearEngine(body_type="female")
    charts, chart_names = chart_labels(engine, data)

    production_shell = outputs["production_shell"]
    radial_shell = outputs["radial_previous_shell"]
    shell_replay = transfer_outer_cage_radial(
        data["reference_parent"], data["outer_parent"], data["target_body"],
        data["projection_faces"], parity=int(data["cage_normal_sign"]), radius_factor=1)
    shell_replay_error = float(np.linalg.norm(shell_replay - radial_shell, axis=1).max())
    if shell_replay_error > 1e-8:
        raise ValueError(f"Archived radial shell differs from current implementation by {shell_replay_error}")
    variants = {
        "production_outer_binding": data["baseline"],
        "radial_shell_outer_binding": remap_visible(data, radial_shell),
        "production_shell_prism_binding": evaluate_binding(data, binding, production_shell),
        "radial_shell_prism_binding": outputs["radial_previous"],
    }
    replay = evaluate_binding(data, binding, radial_shell)
    replay_error = float(np.linalg.norm(replay - variants["radial_shell_prism_binding"], axis=1).max())
    if replay_error > 1e-8:
        raise ValueError(f"Archived radial-prism output differs from current evaluator by {replay_error}")

    a, b = EDGE
    source_length = float(np.linalg.norm(data["garment"][a] - data["garment"][b]))
    scale = previous["common_metric_scale"]
    faces = data["garment_faces"]
    edges = np.unique(np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]],
                                             faces[:, [2, 0]]]), axis=1), axis=0)
    source_lengths = np.linalg.norm(data["garment"][edges[:, 0]] - data["garment"][edges[:, 1]], axis=1)
    report = dict(asset=ASSET, source_matches_fresh_runtime=True,
                  saved_binding_fingerprint_matches=True,
                  radial_shell_replay_max_error=shell_replay_error,
                  radial_prism_replay_max_error=replay_error,
                  scale=scale, source_edge_length=source_length,
                  witnesses=dict(edge=list(EDGE), boot=BOOT), variants={})
    common = np.vstack([data["body"], *variants.values()])
    panels = []
    for name, mesh in variants.items():
        samples = np.vstack([mesh, mesh[data["garment_faces"]].mean(axis=1)])
        edge_length = float(np.linalg.norm(mesh[a] - mesh[b]))
        edge_lengths = np.linalg.norm(mesh[edges[:, 0]] - mesh[edges[:, 1]], axis=1)
        ratios = edge_lengths / np.maximum(source_lengths * scale, 1e-30)
        valid_edges = np.flatnonzero(source_lengths >= .01)
        worst_id = int(valid_edges[np.argmax(ratios[valid_edges])])
        lowest = int(np.argmin(mesh[:, 2]))
        row = dict(
            edge_2396_2397=dict(length_m=edge_length,
                                stretch_normalized=edge_length / (source_length * scale),
                                vertex_positions=mesh[list(EDGE)].tolist()),
            boot_1464=dict(position=mesh[BOOT].tolist(),
                           below_body_min_z_m=float(max(0, data["body"][:, 2].min() - mesh[BOOT, 2]))),
            lowest_vertex=dict(index=lowest, z_m=float(mesh[:, 2].min())),
            worst_remaining_edge=dict(vertices=edges[worst_id].tolist(),
                                      stretch_normalized=float(ratios[worst_id]),
                                      length_m=float(edge_lengths[worst_id])),
            distortion=distortion(data["garment"], mesh, data["garment_faces"], scale),
            penetration=body_penetration(samples, data["body"], data["body_faces"]),
        )
        if "prism_binding" in name:
            shell = production_shell if name.startswith("production") else radial_shell
            row["prism_witness_terms"] = {
                str(vertex): prism_terms(data, binding, shell, vertex)
                for vertex in set((*EDGE, BOOT, lowest, *edges[worst_id]))
            }
            for vertex in set((*EDGE, BOOT, lowest, *edges[worst_id])):
                row["prism_witness_terms"][str(vertex)]["reconstruction_error"] = float(
                    np.linalg.norm(mesh[vertex] - row["prism_witness_terms"][str(vertex)]["reconstructed"]))
                face_id = row["prism_witness_terms"][str(vertex)]["face_id"]
                row["prism_witness_terms"][str(vertex)]["body_chart_majority_label"] = chart_names[int(charts[face_id])]
        report["variants"][name] = row
        image_path = OUT / (name + ".png")
        depth_preview(data["body"], data["body_faces"], mesh, data["garment_faces"],
                      image_path, shared_garment_vertices=common)
        panels.append(Image.open(image_path).convert("RGB"))

    sheet = Image.new("RGB", (panels[0].width, sum(p.height + 24 for p in panels)), "white")
    y = 0
    for name, panel in zip(variants, panels):
        ImageDraw.Draw(sheet).text((8, y + 4), name, fill="black")
        sheet.paste(panel, (0, y + 24))
        y += panel.height + 24
    sheet.save(OUT / "radial_prism_witness_comparison.png")
    (OUT / "RADIAL_PRISM_WITNESSES.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({name: {
        "edge_stretch": row["edge_2396_2397"]["stretch_normalized"],
        "boot_z": row["boot_1464"]["position"][2],
        "lowest_z": row["lowest_vertex"]["z_m"],
        "edges_over_3": row["distortion"]["historical_length_mask"]["over_3"],
        "area_under_tenth": row["distortion"]["area"]["under_tenth"],
        "penetration": row["penetration"]["penetrating_fraction"],
    } for name, row in report["variants"].items()}, indent=2))


if __name__ == "__main__":
    main()
