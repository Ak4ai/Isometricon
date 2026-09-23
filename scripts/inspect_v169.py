import os
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_v169.txt").replace("\\", "/")
code = f"""
import bpy
cage = bpy.data.objects['Roblox_Inner_Cage_Universal']
v = cage.data.vertices[169]
groups = [(cage.vertex_groups[g.group].name, g.weight) for g in v.groups]
with open("{out_path}", "w") as f:
    f.write(f"groups: {{groups}}, co: {{v.co}}\\n")
    # Also find all vertices with displacement > 0.15m
    import numpy as np
    f_npz = np.load(r"assets/models/roblox_female_cage_data.npz")
    m_npz = np.load(r"assets/models/roblox_cage_data.npz")
    disp = np.linalg.norm(f_npz['cage_verts_rest'] - m_npz['cage_verts_rest'], axis=1)
    bad_v = np.where(disp > 0.15)[0]
    for bvi in bad_v:
        bv = cage.data.vertices[int(bvi)]
        bg = [(cage.vertex_groups[g.group].name, g.weight) for g in bv.groups]
        f.write(f"v {{bvi}}: disp {{disp[bvi]:.3f}}, groups {{bg}}, orig_z: {{bv.co.z:.3f}}, fem_z: {{f_npz['cage_verts_rest'][bvi][2]:.3f}}\\n")
"""
execute_blender_code(code)
with open("temp_v169.txt") as f:
    print(f.read())
