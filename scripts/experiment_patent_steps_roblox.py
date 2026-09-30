"""Three steps read from Roblox's patent (US20250265799A1), scored against Studio exports.

1. Area weighting: each cage triangle's contribution to its vertices' offset is
   weighted by the triangle's area (patent: "multiplied by a GIC triangle area").
2. Bulk scale from the bounding boxes of the garment OUTER cage and the avatar
   body cage (ours used the garment inner cage).
3. Local difference (LD) transform: LD = POC_matrix @ inverse(GIC_matrix), with
   the triangle edges u, v kept at their real length (so the map stretches with
   the triangle) and the third basis vector w built three ways:
   unit normal / normal scaled like a length (sqrt area) / like an area (u x v).
Every variant is bound with the same prism binding; only the outer-cage transfer changes.
"""
import glob
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.batch_compare_roblox import CASES, GT
from scripts.compare_roblox_ground_truth import STUD_CM, align_studio_to_engine, edge_ratio, load_obj_groups
from scripts.experiment_dual_cage_prism import bind_dual_cage
from scripts.test_r15_shirt_transfer import CAGE_OBJ, DIRECTORY, FBX, export_outer_cages_obj, load_classic_body
from src.clothing.multi_influence_shell import transfer_outer_cage_radial
from src.clothing.wear_engine import RobloxWearEngine, load_r15_cages
from src.clothing.wrap_layer_fit import _local_map, retarget_garment_with_wrap_layer


def frame(a, b, c, normal_mode, sign=1.0):
    u, v = b - a, c - a
    w = np.cross(u, v)
    area2 = np.linalg.norm(w)
    if area2 < 1e-12:
        return None
    if normal_mode == "unit":
        w = w / area2
    elif normal_mode == "length":
        w = w / np.sqrt(area2)
    return np.column_stack((u, v, sign * w))


def per_face_shell(trace, mode, area_weighted):
    """Outer cage on the target: POC + average over incident triangles of map(LO)."""
    ref, out, tgt = trace["reference_parent"], trace["outer_parent"], trace["target_body"]
    faces, parity = trace["projection_faces"], trace["cage_normal_sign"]
    offsets = out - ref
    total = np.zeros_like(ref)
    weight = np.zeros(len(ref))
    for face in faces:
        if mode == "rotacao (runtime)":
            transform = _local_map(*ref[face], *tgt[face], normal_sign=parity)
        else:
            source = frame(*ref[face], mode)
            target = frame(*tgt[face], mode, sign=parity)
            transform = None if source is None or target is None else target @ np.linalg.inv(source)
        if transform is None:
            continue
        w = 0.5 * np.linalg.norm(np.cross(ref[face[1]] - ref[face[0]], ref[face[2]] - ref[face[0]])) if area_weighted else 1.0
        total[face] += w * (offsets[face] @ transform.T)
        weight[face] += w
    moved = total / np.maximum(weight, 1e-12)[:, None]
    return tgt + moved


def patent_bulk(trace, how):
    outer_box = np.ptp(trace["outer_parent"], axis=0)
    body_box = np.ptp(trace["target_body"], axis=0)
    ratio = body_box / outer_box
    return float(np.median(ratio)) if how == "mediana" else float(np.cbrt(np.prod(ratio)))


def main():
    names = sys.argv[1:] or [c for c in CASES if c != "sueter oversized"]
    body, _, _ = load_classic_body(FBX)
    export_outer_cages_obj(FBX, CAGE_OBJ)
    engine = RobloxWearEngine(body_type="female")
    engine.body_cages = load_r15_cages(str(CAGE_OBJ), is_source_cage=True)
    report = {}
    for case in names:
        asset, export = CASES[case]
        groups = load_obj_groups(export)
        roblox_raw, faces, _ = groups.pop("Handle1")
        _, matrix, shift = align_studio_to_engine(np.vstack([g[0] for g in groups.values()]), body)
        roblox = roblox_raw @ matrix.T + shift
        source, all_faces, _, _ = engine.load_obj(next(p for p in glob.glob(str(DIRECTORY / f"*_{asset}.obj")) if "fitted" not in p))
        keep = np.unique(all_faces[:len(faces)])
        trace = {}
        retarget_garment_with_wrap_layer(engine, source, str(next(DIRECTORY.glob(f"*_{asset}.rbxm"))),
                                         DIRECTORY / "wrap_cages", binding_audit=trace)
        args = (trace["reference_parent"], trace["outer_parent"], trace["target_body"], trace["projection_faces"])
        parity = trace["cage_normal_sign"]
        shells = {
            "radial (referencia)": transfer_outer_cage_radial(*args, parity=parity, radius_factor=1.0),
            "1. por triangulo, sem peso": per_face_shell(trace, "rotacao (runtime)", False),
            "1. por triangulo, peso por area": per_face_shell(trace, "rotacao (runtime)", True),
        }
        for how in ("mediana", "volume"):
            shells[f"2. radial, escala da patente ({how})"] = transfer_outer_cage_radial(
                *args, parity=parity, radius_factor=1.0, bulk_scale=patent_bulk(trace, how))
        for mode, label in (("unit", "normal sem esticar"), ("length", "normal como comprimento"), ("area", "normal como area")):
            shells[f"3. LD, {label}, peso area"] = per_face_shell(trace, mode, True)
        entry = {"escala radial atual vs patente": None}
        ext_s, ext_t = np.ptp(trace["reference_parent"], 0), np.ptp(trace["target_body"], 0)
        entry["escala radial atual vs patente"] = [round(float(np.median(ext_t / ext_s)), 3),
                                                  round(patent_bulk(trace, "mediana"), 3), round(patent_bulk(trace, "volume"), 3)]
        for label, shell in shells.items():
            fitted = bind_dual_cage(source, trace, shell)[0][keep]
            distance = np.linalg.norm(fitted - roblox, axis=1) * STUD_CM
            row = {"acima_5cm_pct": round(float((distance > 5).mean() * 100), 1),
                   "mediana_cm": round(float(np.median(distance)), 2),
                   "arestas_3x": int((edge_ratio(roblox, fitted, faces) > 3).sum())}
            if roblox[:, 2].min() < -0.5:  # trouser hems: lateral centring error
                low = roblox[:, 2] < roblox[:, 2].min() + 0.25
                mask = low & (roblox[:, 0] > 0)
                row["barra_x_cm"] = round(float((roblox[mask, 0].mean() - fitted[mask, 0].mean()) * STUD_CM), 1)
            entry[label] = row
        report[case] = entry
        print(case, json.dumps(entry, ensure_ascii=False), flush=True)
    (GT / "patent_steps_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
