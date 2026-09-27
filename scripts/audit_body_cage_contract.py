"""Audit exported female body and R15 cage correspondence used by runtime.

This checks the exported OBJ files, not the current unsaved Blender scene.
Distances are in the exported model coordinates (metres per package manifest).
"""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.clothing.wear_engine import (
    RobloxWearEngine, _align_target_faces_by_uv, closest_point_on_triangle,
    load_r15_female_cages,
)

MODELS = ROOT / "assets/models"
BODY_NAMES = {
    "Head": "Export_cabeca", "UpperTorso": "Export_torso", "LowerTorso": "Export_pelve",
    "LeftUpperArm": "Export_braco_superior_esquerdo",
    "RightUpperArm": "Export_braco_superior_direito",
    "LeftLowerArm": "Export_antebraco_esquerdo",
    "RightLowerArm": "Export_antebraco_direito",
    "LeftHand": "Export_mao_esquerda", "RightHand": "Export_mao_direita",
    "LeftUpperLeg": "Export_coxa_esquerda", "RightUpperLeg": "Export_coxa_direita",
    "LeftLowerLeg": "Export_canela_esquerda", "RightLowerLeg": "Export_canela_direita",
    "LeftFoot": "Export_pe_esquerdo", "RightFoot": "Export_pe_direito",
}


def load_body_parts(path):
    all_vertices = []
    result = {}
    current = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("o "):
            name = line[2:].strip()
            current = result[name] = {"vertices": [], "faces": [], "offset": len(all_vertices)}
        elif line.startswith("v "):
            point = [float(value) for value in line.split()[1:4]]
            all_vertices.append(point)
            current["vertices"].append(point)
        elif line.startswith("f "):
            polygon = [int(value.split("/")[0]) - 1 - current["offset"]
                       for value in line.split()[1:]]
            current["faces"].extend((polygon[0], polygon[i], polygon[i + 1])
                                    for i in range(1, len(polygon) - 1))
    for part in result.values():
        raw = np.asarray(part["vertices"], dtype=np.float64)
        part["vertices"] = raw[:, [0, 2, 1]] * [1, -1, 1]
        part["faces"] = np.asarray(part["faces"], dtype=np.int32)
    return result


def nearest_surface(points, vertices, faces):
    triangles = vertices[faces]
    distances = np.empty(len(points))
    face_ids = np.empty(len(points), dtype=np.int32)
    for index, point in enumerate(points):
        best = float("inf")
        best_id = -1
        for face_id, (a, b, c) in enumerate(triangles):
            closest, _, _, _ = closest_point_on_triangle(point, a, b, c)
            d = float(np.linalg.norm(point - closest))
            if d < best:
                best, best_id = d, face_id
        distances[index], face_ids[index] = best, best_id
    return distances, face_ids


def face_uv_keys(part):
    return [tuple(np.round(uv, 5)) for uv in part["face_uvs"].reshape(-1, 2)]


def main():
    package = json.loads((MODELS / "female_clothing_package_stage2.json").read_text(encoding="utf-8"))
    source = load_r15_female_cages(str(MODELS / package["reference_cage_obj"]), is_source_cage=True)
    exported = load_r15_female_cages(str(MODELS / package["cage_obj"]), is_source_cage=False)
    runtime = RobloxWearEngine(body_type="female").r15_female_cages
    body = load_body_parts(MODELS / package["body_obj"])
    all_vertices = []
    all_faces = []
    for body_part in body.values():
        offset = sum(len(vertices) for vertices in all_vertices)
        all_vertices.append(body_part["vertices"])
        all_faces.append(body_part["faces"] + offset)
    all_vertices = np.vstack(all_vertices)
    all_faces = np.vstack(all_faces)
    report = {"exported_files": {"reference": package["reference_cage_obj"],
                                  "target": package["cage_obj"], "body": package["body_obj"]},
              "parts": {}}
    for name, body_name in BODY_NAMES.items():
        src, dst, actual = source[name], exported[name], runtime[name]
        uv_faces = _align_target_faces_by_uv(src, dst, name)
        body_part = body[body_name]
        cage = dst["verts"]
        body_vertices = body_part["vertices"]
        cage_to_body, _ = nearest_surface(cage, body_vertices, body_part["faces"])
        cage_to_any_body, _ = nearest_surface(cage, all_vertices, all_faces)
        body_to_cage, _ = nearest_surface(body_vertices, cage, dst["faces"])
        src_uv = face_uv_keys(src)
        dst_uv = face_uv_keys(dst)
        src_keys = set(src_uv)
        dst_keys = set(dst_uv)
        edges = np.unique(np.sort(np.concatenate((src["faces"][:, [0, 1]],
                                                  src["faces"][:, [1, 2]],
                                                  src["faces"][:, [2, 0]])), axis=1), axis=0)
        source_lengths = np.linalg.norm(src["verts"][edges[:, 0]] - src["verts"][edges[:, 1]], axis=1)
        target_lengths = np.linalg.norm(cage[edges[:, 0]] - cage[edges[:, 1]], axis=1)
        valid = source_lengths > 1e-8
        ratios = target_lengths[valid] / source_lengths[valid]
        report["parts"][name] = {
            "source_vertices": len(src["verts"]), "target_vertices": len(cage),
            "source_faces": len(src["faces"]), "target_faces": len(dst["faces"]),
            "uv_triangle_pairing": len(uv_faces),
            "uv_values_only_in_source": len(src_keys - dst_keys),
            "uv_values_only_in_target": len(dst_keys - src_keys),
            "face_indices_equal": bool(np.array_equal(src["faces"], dst["faces"])),
            "runtime_vs_export_max_m": float(np.linalg.norm(actual["verts"] - cage, axis=1).max()),
            "cage_to_body_median_m": float(np.median(cage_to_body)),
            "cage_to_body_p95_m": float(np.quantile(cage_to_body, .95)),
            "cage_to_body_max_m": float(cage_to_body.max()),
            "cage_to_any_body_p95_m": float(np.quantile(cage_to_any_body, .95)),
            "cage_to_any_body_max_m": float(cage_to_any_body.max()),
            "body_to_cage_p95_m": float(np.quantile(body_to_cage, .95)),
            "body_to_cage_max_m": float(body_to_cage.max()),
            "source_target_edge_ratio_p95": float(np.quantile(ratios, .95)),
            "source_target_edge_ratio_max": float(ratios.max()),
            "worst_cage_vertex": int(np.argmax(cage_to_body)),
        }
    rows = report["parts"].values()
    report["summary"] = {
        "parts": len(report["parts"]),
        "uv_mismatched_parts": sum(bool(r["uv_values_only_in_source"] or r["uv_values_only_in_target"]) for r in rows),
        "topology_mismatched_parts": sum(not r["face_indices_equal"] for r in rows),
        "runtime_changed_parts": sum(r["runtime_vs_export_max_m"] > 1e-6 for r in rows),
        "worst_cage_to_body_m": max(r["cage_to_body_max_m"] for r in rows),
        "worst_cage_to_any_body_m": max(r["cage_to_any_body_max_m"] for r in rows),
    }
    output = ROOT / "artifacts/clothing_audit/BODY_CAGE_CONTRACT.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
