"""Junta de novo, nas roupas já encaixadas, os vértices que são um ponto só na roupa original.

O encaixe passou a fazer isso sozinho (``wear_engine.keep_together``); este script aplica a mesma
regra aos caches que já estavam em ``assets/models`` (``character_native_<id>_<corpo>*.obj``), sem
reencaixar o catálogo. Só as linhas ``v`` e ``vn`` dos vértices mexidos mudam. Rodar de novo não
muda mais nada.

    python scripts/weld_fitted_fans.py            # aplica e lista o que mudou
    python scripts/weld_fitted_fans.py --dry-run  # só lista
"""
import argparse
import glob
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.clothing.character_model import CLOTHING_DIR, MODELS_DIR  # noqa: E402
from src.clothing.wear_engine import keep_together  # noqa: E402


def read(path):
    """(lines, row of each "v" line, vertices, row of each "vn" line, triangles of vertex ids) of an OBJ."""
    lines = open(path, encoding="utf-8", errors="ignore").read().splitlines()
    at, vertices, normals_at, faces = [], [], [], []
    for row, line in enumerate(lines):
        if line.startswith("v "):
            at.append(row)
            vertices.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("vn "):
            normals_at.append(row)
        elif line.startswith("f "):
            ids = [int(token.split("/")[0]) - 1 for token in line.split()[1:]]
            faces += [[ids[0], ids[k], ids[k + 1]] for k in range(1, len(ids) - 1)]
    return lines, at, np.array(vertices, dtype=np.float64).reshape(-1, 3), normals_at, np.array(faces, dtype=np.int64).reshape(-1, 3)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sources = {}
    for path in glob.glob(os.path.join(CLOTHING_DIR, "*.obj")):
        match = re.search(r"_(\d{6,})\.obj$", os.path.basename(path))
        if match and not os.path.basename(path).startswith("Hair_fitted"):
            sources[match.group(1)] = path
    changed = 0
    for path in sorted(glob.glob(os.path.join(MODELS_DIR, "character_native_*.obj"))):
        match = re.match(r"character_native_(\d{6,})_", os.path.basename(path))
        if not match or match.group(1) not in sources:
            continue
        lines, at, fitted, normals_at, faces = read(path)
        source = read(sources[match.group(1)])[2]
        if len(source) != len(fitted) or not len(fitted):
            continue
        together = keep_together(source, fitted)
        moved = np.flatnonzero(np.linalg.norm(together - fitted, axis=1) > 1e-6)
        if not len(moved):
            continue
        changed += 1
        print(f"{os.path.basename(path)}: {len(moved)} vértices juntados (o mais longe estava a "
              f"{np.linalg.norm(together - fitted, axis=1).max() * 100:.1f} cm)")
        if args.dry_run:
            continue
        for index in moved:
            x, y, z = together[index]
            lines[at[index]] = f"v {x:.5f} {y:.5f} {z:.5f}"
        if len(normals_at) == len(fitted) and len(faces):  # the smooth normals of the vertices about the ones moved
            corners = together[faces]
            face_normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
            length = np.linalg.norm(face_normals, axis=1, keepdims=True)
            face_normals = np.where(length > 1e-8, face_normals / np.maximum(length, 1e-12), 0.0)
            normals = np.zeros_like(together)
            for k in range(3):
                np.add.at(normals, faces[:, k], face_normals)
            length = np.linalg.norm(normals, axis=1, keepdims=True)
            normals = normals / np.where(length < 1e-8, 1.0, length)
            around = np.unique(faces[np.isin(faces, moved).any(axis=1)])
            for index in around:
                x, y, z = normals[index]
                lines[normals_at[index]] = f"vn {x:.4f} {y:.4f} {z:.4f}"
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    print(f"{changed} arquivo(s) {'mudariam' if args.dry_run else 'mudados'}.")


if __name__ == "__main__":
    main()
