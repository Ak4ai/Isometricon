import os
import numpy as np

def check_obj(path):
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return
    objects = {}
    current = 'default'
    verts_dict = {}
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if line.startswith('o ') or line.startswith('g '):
                parts = line.strip().split()
                current = parts[1] if len(parts) > 1 else 'unnamed'
                if current not in objects:
                    objects[current] = {'v': 0, 'f': 0}
                    verts_dict[current] = []
            elif line.startswith('v '):
                if current not in objects:
                    objects[current] = {'v': 0, 'f': 0}
                    verts_dict[current] = []
                objects[current]['v'] += 1
                verts_dict[current].append([float(x) for x in line.strip().split()[1:4]])
            elif line.startswith('f '):
                if current not in objects:
                    objects[current] = {'v': 0, 'f': 0}
                    verts_dict[current] = []
                objects[current]['f'] += 1
    total_v = sum(o['v'] for o in objects.values())
    total_f = sum(o['f'] for o in objects.values())
    print(f"\n=======================================================")
    print(f"FILE: {os.path.basename(path)}")
    print(f"Total verts: {total_v}, Total faces: {total_f}, Total parts: {len(objects)}")
    print(f"=======================================================")
    for k, v in objects.items():
        vs = np.array(verts_dict[k]) if verts_dict[k] else np.empty((0,3))
        if len(vs):
            x_s = f"[{vs[:,0].min():.3f}, {vs[:,0].max():.3f}]"
            y_s = f"[{vs[:,1].min():.3f}, {vs[:,1].max():.3f}]"
            z_s = f"[{vs[:,2].min():.3f}, {vs[:,2].max():.3f}]"
            print(f"  {k:22}: {v['v']:4d} v, {v['f']:4d} f | X:{x_s:16} Y:{y_s:16} Z:{z_s:16}")
        else:
            print(f"  {k:22}: {v['v']:4d} v, {v['f']:4d} f | (no local v)")

for p in [
    'assets/models/clothing/female_cages.obj',
    'assets/models/clothing/roblox_source_cages.obj',
    'assets/models/clothing/roblox_studio_cage.obj',
    'assets/models/clothing/inner_cage_universal.obj'
]:
    check_obj(p)
