"""Atualiza roblox_female_cage_data.npz com o volume exato do busto e contorno
da modelagem original do usuário em assets/models/clothing/female_cages.obj.
"""
import os, sys
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)
import numpy as np
from src.clothing.wear_engine import load_r15_female_cages
fem_obj = os.path.join(base_dir, "assets", "models", "clothing", "female_cages.obj")
fem_npz = os.path.join(base_dir, "assets", "models", "roblox_female_cage_data.npz")

cages = load_r15_female_cages(fem_obj)
ut = cages["UpperTorso"]
ut_v = ut["verts"]
ut_f = ut["faces"]

data = dict(np.load(fem_npz))
fv_rest = data["cage_verts_rest"].copy()
fv_apose = data["cage_verts_apose"].copy()
faces = data["cage_faces"]

# Máscara da frente do UpperTorso: Z in [1.10, 1.45], |X| < 0.20, Y < -0.02
mask = (fv_rest[:, 2] > 1.10) & (fv_rest[:, 2] < 1.45) & (abs(fv_rest[:, 0]) < 0.20) & (fv_rest[:, 1] < -0.02)
indices = np.where(mask)[0]

def get_ut_front_y(x, z):
    d = (ut_v[:, 0] - x)**2 + (ut_v[:, 2] - z)**2
    idx = np.argsort(d)[:6]
    return float(np.min(ut_v[idx, 1]))

updated = 0
for i in indices:
    x, y, z = fv_rest[i]
    front_y = get_ut_front_y(x, z)
    if front_y < y:
        fv_rest[i, 1] = front_y
        fv_apose[i, 1] = front_y
        updated += 1

# Suavização Laplaciana 1D ao longo de Y para transições orgânicas suaves
adj = {}
for f in faces:
    for i in range(3):
        adj.setdefault(f[i], set()).add(f[(i+1)%3])
        adj.setdefault(f[i], set()).add(f[(i+2)%3])

for _ in range(3):
    new_y = fv_rest[:, 1].copy()
    for i in indices:
        if fv_rest[i, 1] > -0.217:  # Preserva os cumes principais do busto (-0.218m)
            nbrs = [n for n in adj[i] if n in indices]
            if nbrs:
                new_y[i] = 0.50 * fv_rest[i, 1] + 0.50 * float(np.mean(fv_rest[nbrs, 1]))
    fv_rest[:, 1] = new_y
    fv_apose[:, 1] = new_y

data["cage_verts_rest"] = fv_rest
data["cage_verts_apose"] = fv_apose

np.savez(fem_npz, **data)
print(f"Sucesso: {updated} vértices do busto atualizados a partir de female_cages.obj!")
print(f"Busto mínimo Y atualizado: {fv_rest[mask, 1].min():.6f}m (corresponde a Z={-fv_rest[mask, 1].min():.4f}m no mundo OpenGL)")
