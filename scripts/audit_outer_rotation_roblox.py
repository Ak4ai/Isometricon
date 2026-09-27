"""Per region: is our outer-layer error a rotation or a length of the body->garment offset?

For each prism-bound garment vertex, the offset from its body-cage point to the
garment is compared between our fit and Roblox's: angle between them, length
ratio, and the mean rotation axis (ours -> Roblox) in engine axes
(x = side, y = front(-)/back(+), z = up).
"""
import glob
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.batch_compare_roblox import CASES, GT
from scripts.compare_roblox_ground_truth import STUD_CM, align_studio_to_engine, load_obj_groups
from scripts.experiment_dual_cage_prism import closest_prism_binding
from scripts.test_r15_shirt_transfer import CAGE_OBJ, DIRECTORY, FBX, export_outer_cages_obj, load_classic_body
from src.clothing.multi_influence_shell import transfer_outer_cage_radial
from src.clothing.wear_engine import RobloxWearEngine, load_r15_female_cages
from src.clothing.wrap_layer_fit import _local_map, retarget_garment_with_wrap_layer


def binding(points, trace, target_outer):
    inner, outer, target_inner = trace["reference_parent"], trace["outer_parent"], trace["target_body"]
    faces = trace["projection_faces"]
    area = lambda v: np.linalg.norm(np.cross(v[faces[:, 1]] - v[faces[:, 0]], v[faces[:, 2]] - v[faces[:, 0]]), axis=1)
    faces = faces[(area(inner) > 1e-8) & (area(outer) > 1e-8)]
    six = np.concatenate((inner[faces], outer[faces]), axis=1)
    lower, upper = six.min(1), six.max(1)
    rows = []
    for point in points:
        _, (face_id, t, bary, residual) = closest_prism_binding(point, inner, outer, faces, lower, upper)
        face = faces[face_id]
        target_section = (1 - t) * target_inner[face] + t * target_outer[face]
        source_section = (1 - t) * inner[face] + t * outer[face]
        transform = _local_map(*source_section, *target_section, normal_sign=trace["cage_normal_sign"])
        if transform is None:
            transform = _local_map(*inner[face], *target_inner[face], normal_sign=trace["cage_normal_sign"])
        normal = np.cross(*(target_inner[face][1:] - target_inner[face][0]))
        normal /= max(np.linalg.norm(normal), 1e-12)
        if np.dot(normal, bary @ (target_outer[face] - target_inner[face])) < 0:
            normal = -normal
        rows.append((t, np.linalg.norm(residual), bary @ target_section + transform @ residual,
                     bary @ target_inner[face], normal))
    t, res, fitted, body_point, normal = (np.array(c) for c in zip(*rows))
    return t, res, fitted, body_point, normal


def region_names(body_point, normal):
    z = body_point[:, 2]
    height = np.select([z < -1.2, z < -0.4, z < 0.2], ["canela/barra", "joelho/coxa baixa", "coxa alta/bumbum"], "quadril/cintura")
    side = np.where(normal[:, 1] > 0.5, "tras", np.where(normal[:, 1] < -0.5, "frente", "lado"))
    return np.char.add(np.char.add(height.astype(str), " | "), side)


def main():
    names = sys.argv[1:] or ["calca skater", "calca cargo", "jeans com bota", "vestido"]
    body, _, _ = load_classic_body(FBX)
    export_outer_cages_obj(FBX, CAGE_OBJ)
    engine = RobloxWearEngine(body_type="female")
    engine.r15_female_cages = load_r15_female_cages(str(CAGE_OBJ), is_source_cage=True)
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
        shell = transfer_outer_cage_radial(trace["reference_parent"], trace["outer_parent"], trace["target_body"],
                                           trace["projection_faces"], parity=trace["cage_normal_sign"], radius_factor=1.0)
        t, res, ours, body_point, normal = binding(source[keep].astype(float), trace, shell)
        ours_offset, roblox_offset = ours - body_point, roblox - body_point
        length_ours = np.linalg.norm(ours_offset, axis=1)
        length_roblox = np.linalg.norm(roblox_offset, axis=1)
        cosine = np.einsum("ij,ij->i", ours_offset, roblox_offset) / np.maximum(length_ours * length_roblox, 1e-12)
        angle = np.degrees(np.arccos(np.clip(cosine, -1, 1)))
        axis = np.cross(ours_offset, roblox_offset)
        error = np.linalg.norm(roblox - ours, axis=1) * STUD_CM
        usable = (t > 0.8) & (res * STUD_CM < 1) & (length_ours * STUD_CM > 1.5) & (length_roblox * STUD_CM > 1.5)
        regions = region_names(body_point, normal)
        entry = {}
        for name in sorted(set(regions[usable])):
            mask = usable & (regions == name)
            if mask.sum() < 15:
                continue
            mean_axis = axis[mask].sum(0)
            mean_axis = mean_axis / max(np.linalg.norm(mean_axis), 1e-12)
            entry[name] = {
                "vertices": int(mask.sum()),
                "erro_mediano_cm": round(float(np.median(error[mask])), 1),
                "acima_5cm_pct": round(float((error[mask] > 5).mean() * 100), 0),
                "folga_nossa_cm": round(float(np.median(length_ours[mask]) * STUD_CM), 1),
                "folga_roblox_cm": round(float(np.median(length_roblox[mask]) * STUD_CM), 1),
                "angulo_nosso_vs_roblox_graus": round(float(np.median(angle[mask])), 1),
                "eixo_medio_da_correcao_xyz": np.round(mean_axis, 2).tolist(),
                # Share of the error explained by length alone vs direction.
                "erro_so_por_comprimento_cm": round(float(np.median(np.abs(length_roblox[mask] - length_ours[mask])) * STUD_CM), 1),
            }
        report[case] = entry
        print("\n##", case)
        for name, row in sorted(entry.items(), key=lambda kv: -kv[1]["acima_5cm_pct"]):
            print(f"  {name:32s}", row)
    (GT / "outer_rotation_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
