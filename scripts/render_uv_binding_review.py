"""Render the current cached female shirt against the exported A-pose body."""
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

ROOT = Path(__file__).resolve().parents[1]
ALTERNATE = len(sys.argv) > 1 and sys.argv[1] == "wraplayer"
OUT = ROOT / ("artifacts/clothing_audit/office_shirt_wraplayer/shirt_reference_to_body.png" if ALTERNATE else "artifacts/clothing_audit/office_shirt_uv_binding_review.png")


def load_obj(path):
    vertices, faces = [], []
    for line in path.open(encoding="utf-8"):
        if line.startswith("v "):
            vertices.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("f "):
            indices = [int(x.split("/")[0]) - 1 for x in line.split()[1:]]
            faces.extend([indices[0], indices[i], indices[i + 1]] for i in range(1, len(indices) - 1))
    vertices = np.asarray(vertices)
    return vertices[:, [0, 2, 1]] * np.array([1, -1, 1]), np.asarray(faces)


body_v, body_f = load_obj(ROOT / "assets/models/character_female_clean_apose_stage2.obj")
shirt_v, shirt_f = load_obj(ROOT / ("artifacts/clothing_audit/office_shirt_wraplayer/shirt_reference_to_body.obj" if ALTERNATE else "artifacts/clothing_audit/office_shirt_stage2_fitted.obj"))

fig = plt.figure(figsize=(14, 7), dpi=140)
for idx, (azim, label) in enumerate([(-90, "Frente"), (0, "Lado"), (90, "Costas"), (-45, "3/4")], 1):
    ax = fig.add_subplot(1, 4, idx, projection="3d")
    for vertices, faces, color, alpha in [(body_v, body_f, "#d7ae96", 0.85), (shirt_v, shirt_f, "#386b9d", 0.96)]:
        polys = vertices[faces]
        coll = Poly3DCollection(polys, facecolor=color, edgecolor="none", alpha=alpha, zsort="average")
        ax.add_collection3d(coll)
    ax.set_xlim(-0.42, 0.42)
    ax.set_ylim(-0.42, 0.42)
    ax.set_zlim(0.7, 1.7)
    ax.set_box_aspect((0.84, 0.84, 1))
    ax.view_init(elev=8, azim=azim)
    ax.set_axis_off()
    ax.set_title(label)
fig.suptitle("Prévia 3D sem teste de profundidade entre malhas; use four_view_depth_audit.png para avaliar cobertura")
fig.savefig(OUT, bbox_inches="tight")
print(OUT)
