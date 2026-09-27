"""Validate the decoded HSR mask against the body triangles Roblox Studio removed.

HiddenSurfaceRemovalAsset.HSRData (decoded here): 5 header bytes, uint32 garment
face count, uint32 (unknown count), uint32 0, then one bit per vertex of the
garment's reference cage, LSB first; bit 0 = body surface under this vertex is
hidden. The mask is carried to any body through the shared cage UV layout.

For each Studio export on the Blocky, every FBX body triangle is predicted
hidden when its vertices' nearest body-cage points are hidden, and compared
with whether Studio kept that triangle.
"""
import glob
import gzip
import json
from pathlib import Path
import re
import struct
import sys

import lz4.block
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.batch_compare_roblox import CASES, GT
from scripts.compare_roblox_ground_truth import align_studio_to_engine, load_obj_groups
from scripts.import_roblox_clothing import fetch_roblox_asset
from scripts.test_r15_shirt_transfer import CAGE_OBJ, DIRECTORY, FBX, export_outer_cages_obj, load_classic_body
from src.clothing.wear_engine import RobloxWearEngine, load_r15_female_cages
from src.clothing.wrap_layer_fit import _rbxm_properties, _unique_uv_positions, retarget_garment_with_wrap_layer

HSR_DIR = DIRECTORY / "hsr"


def hsr_asset_id(rbxm_path):
    data = Path(rbxm_path).read_bytes()
    data = gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data
    payload = _rbxm_properties(data)["HSRAssetId"][1]
    return re.search(r"id=(\d+)", payload[4:4 + struct.unpack_from("<I", payload)[0]].decode()).group(1)


def hsr_data(asset_id):
    path = HSR_DIR / f"{asset_id}.bin"
    if not path.exists():
        HSR_DIR.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fetch_roblox_asset(asset_id))
    data, index = path.read_bytes(), 32
    if data[:2] == b"\x1f\x8b":  # some assets are served gzip-compressed
        data = gzip.decompress(data)
    while index + 16 <= len(data):
        name, compressed, size, _ = struct.unpack_from("<4sIII", data, index)
        body = data[index + 16:index + 16 + (compressed or size)]
        index += 16 + (compressed or size)
        if compressed:
            body = lz4.block.decompress(body, uncompressed_size=size)
        if name == b"PROP":
            length = struct.unpack_from("<I", body, 4)[0]
            if body[8:8 + length] == b"HSRData":
                payload = body[9 + length:]
                return payload[4:4 + struct.unpack_from("<I", payload)[0]]
    raise ValueError("HSRData ausente")


def hidden_reference_vertices(data, count):
    bits = np.unpackbits(np.frombuffer(data[17:17 + (count + 7) // 8], np.uint8), bitorder="little")[:count]
    return bits == 0


def main():
    body, body_faces, _ = load_classic_body(FBX)
    export_outer_cages_obj(FBX, CAGE_OBJ)
    engine = RobloxWearEngine(body_type="female")
    engine.r15_female_cages = load_r15_female_cages(str(CAGE_OBJ), is_source_cage=True)
    target_uv, cage_points = _unique_uv_positions(engine.r15_female_cages)
    centroids = body[body_faces].mean(1)
    report = {}
    for case, (asset, export) in CASES.items():
        rbxm = next(DIRECTORY.glob(f"*_{asset}.rbxm"))
        source, *_ = engine.load_obj(next(p for p in glob.glob(str(DIRECTORY / f"*_{asset}.obj")) if "fitted" not in p))
        trace = {}
        try:
            retarget_garment_with_wrap_layer(engine, source, str(rbxm), DIRECTORY / "wrap_cages", binding_audit=trace)
        except Exception as exc:
            report[case] = {"erro": str(exc)}
            continue
        hidden_ref = hidden_reference_vertices(hsr_data(hsr_asset_id(rbxm)), len(trace["uv_index"]))
        hidden_uv = np.zeros(len(target_uv), bool)
        visible_uv = np.zeros(len(target_uv), bool)
        np.logical_or.at(hidden_uv, trace["uv_index"][hidden_ref], True)
        np.logical_or.at(visible_uv, trace["uv_index"][~hidden_ref], True)
        # Body vertex -> nearest body-cage point.
        nearest = np.concatenate([((body[i:i + 512, None] - cage_points[None]) ** 2).sum(-1).argmin(1)
                                  for i in range(0, len(body), 512)])
        # Roblox kept a body triangle if its centroid is present in the Studio export.
        groups = load_obj_groups(export)
        groups.pop("Handle1")
        _, matrix, shift = align_studio_to_engine(np.vstack([g[0] for g in groups.values()]), body)
        kept_centroids = np.vstack([(v @ matrix.T + shift)[f].mean(1) for v, f, _ in groups.values()])
        kept = np.concatenate([((centroids[i:i + 512, None] - kept_centroids[None]) ** 2).sum(-1).min(1)
                               for i in range(0, len(centroids), 512)]) < 1e-6
        entry = {"triangulos_corpo": int(len(body_faces)), "Roblox_escondeu": int((~kept).sum())}
        for rule, vertex_hidden in (("UV escondido em qualquer copia", hidden_uv[nearest]),
                                    ("UV escondido em todas as copias", (hidden_uv & ~visible_uv)[nearest])):
            predicted = vertex_hidden[body_faces].all(1)
            entry[rule] = {"previstos_escondidos": int(predicted.sum()),
                           "acertos_escondidos": int((predicted & ~kept).sum()),
                           "escondidos_a_mais": int((predicted & kept).sum()),
                           "escondidos_a_menos": int((~predicted & ~kept).sum()),
                           "concordancia_pct": round(float((predicted == ~kept).mean() * 100), 2)}
        report[case] = entry
        print(case, json.dumps(entry, ensure_ascii=False), flush=True)
    (GT / "hsr_mask_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
