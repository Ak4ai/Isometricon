"""Audit reference-to-female cage seams shared by distinct R15 body parts."""
from collections import defaultdict
from pathlib import Path
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine


def uv_positions(part):
    result = {}
    for face, uv_face in zip(part["faces"], part["face_uvs"]):
        for vertex, uv in zip(face, uv_face):
            key = tuple(np.round(uv, 5))
            value = part["verts"][vertex]
            if key in result and np.linalg.norm(result[key] - value) > 2e-4:
                raise ValueError(f"UV has multiple positions: {key}")
            result[key] = value
    return result


def audit(engine):
    groups = defaultdict(list)
    for name, source_part in engine.r15_source_cages.items():
        if name.endswith("Forearm"):
            continue
        source = uv_positions(source_part)
        target = uv_positions(engine.body_cages[name])
        if source.keys() != target.keys():
            raise ValueError(f"UV set differs in {name}")
        for uv, point in source.items():
            groups[tuple(np.round(point, 5))].append((name, uv, target[uv]))

    report = []
    for source_point, members in groups.items():
        parts = sorted({name for name, _, _ in members})
        if len(parts) < 2:
            continue
        target = np.array([point for _, _, point in members])
        spread = float(np.linalg.norm(target - target.mean(axis=0), axis=1).max())
        report.append({"source_xyz": source_point,
                       "parts": parts, "target_spread_m": spread,
                       "members": [{"part": name, "uv": uv,
                                    "target_xyz": point.round(5).tolist()}
                                   for name, uv, point in members]})
    report.sort(key=lambda row: row["target_spread_m"], reverse=True)
    by_pair = defaultdict(list)
    for row in report:
        by_pair["/".join(row["parts"])].append(row["target_spread_m"])
    summary = {name: {"count": len(values), "max_m": max(values),
                      "over_2cm": sum(value > .02 for value in values)}
               for name, values in sorted(by_pair.items())}
    for pair, stats in summary.items():
        names = pair.split("/")
        rows = [row for row in report if row["parts"] == names]
        if len(names) != 2 or len(rows) > 16:
            continue
        a = np.asarray([next(np.asarray(m["target_xyz"]) for m in row["members"]
                             if m["part"] == names[0]) for row in rows])
        b = np.asarray([next(np.asarray(m["target_xyz"]) for m in row["members"]
                             if m["part"] == names[1]) for row in rows])
        distance = np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)
        # Exact minimum-total-cost bijection for these small joint rings.
        costs = {0: (0.0, ())}
        for i in range(len(rows)):
            next_costs = {}
            for mask, (cost, assignment) in costs.items():
                for j in range(len(rows)):
                    if mask & (1 << j):
                        continue
                    new_mask = mask | (1 << j)
                    candidate = (cost + float(distance[i, j]), assignment + (j,))
                    if new_mask not in next_costs or candidate[0] < next_costs[new_mask][0]:
                        next_costs[new_mask] = candidate
            costs = next_costs
        assignment = costs[(1 << len(rows)) - 1][1]
        stats["uv_pair_mean_m"] = float(np.diag(distance).mean())
        stats["geometric_pair_mean_m"] = float(np.mean([distance[i, j]
                                                        for i, j in enumerate(assignment)]))
        stats["geometric_pair_max_m"] = float(max(distance[i, j]
                                                 for i, j in enumerate(assignment)))
        stats["reassigned_count"] = sum(i != j for i, j in enumerate(assignment))
    return {"joint_groups": len(report), "joint_groups_over_2cm": sum(
        row["target_spread_m"] > .02 for row in report),
            "joint_pairs": summary, "largest": report[:30]}


if __name__ == "__main__":
    result = audit(RobloxWearEngine(body_type="female"))
    out = ROOT / "artifacts/clothing_audit/BODY_JOINT_SEAMS.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "largest"}, indent=2))
