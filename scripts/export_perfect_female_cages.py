import bpy, os, sys, traceback
import numpy as np

def run():
    try:
        repo_root = r"C:\Users\Henrique\Documents\GitHub\Isometricon"
        cages_dir = os.path.join(repo_root, "assets", "models", "clothing", "cages")
        out_cages_path = os.path.join(repo_root, "assets", "models", "clothing", "female_cages.obj")

        parts = [
            'Head', 'UpperTorso', 'LowerTorso', 'LeftUpperArm', 'LeftLowerArm', 'LeftHand',
            'RightUpperArm', 'RightLowerArm', 'RightHand', 'LeftUpperLeg', 'LeftLowerLeg', 'LeftFoot',
            'RightUpperLeg', 'RightLowerLeg', 'RightFoot'
        ]

        def get_part_mapping(src_obj_path, blender_obj):
            src_v = []
            src_vt = []
            src_f = []
            with open(src_obj_path) as f:
                for l in f:
                    if l.startswith("v "):
                        src_v.append([float(x) for x in l.split()[1:4]])
                    elif l.startswith("vt "):
                        src_vt.append([float(x) for x in l.split()[1:3]])
                    elif l.startswith("f "):
                        src_f.append([tok.split("/") for tok in l.split()[1:]])
                        
            src_v_to_uv = {}
            for face in src_f:
                for tok in face:
                    if len(tok) > 1 and tok[1]:
                        vi = int(tok[0]) - 1
                        vti = int(tok[1]) - 1
                        src_v_to_uv[vi] = tuple(np.round(src_vt[vti], 4))
                        
            mesh = blender_obj.data
            uv_layer = mesh.uv_layers.active.data
            dst_v_to_uv = {}
            for poly in mesh.polygons:
                for li, vi in zip(poly.loop_indices, poly.vertices):
                    dst_v_to_uv[vi] = tuple(np.round(uv_layer[li].uv[:], 4))
                    
            mapping = {}
            for svi, suv in src_v_to_uv.items():
                for dvi, duv in dst_v_to_uv.items():
                    if suv == duv:
                        mapping[svi] = dvi
                        break
            return mapping, np.array(src_v), src_f

        out_lines = []
        out_lines.append("# Perfect Dual-Cage Export for Female R15 Isometricon\n")
        v_global_offset = 0

        for p in parts:
            blender_name = f"{p}_OuterCage"
            o = bpy.data.objects.get(blender_name)
            if not o:
                print(f"Warning: {blender_name} not found in Blender!")
                continue
                
            src_obj_path = os.path.join(cages_dir, f"{p}.obj")
            mesh = o.data
            mw = o.matrix_world
            
            mapping = {}
            src_v = []
            src_f = []
            if os.path.exists(src_obj_path):
                try:
                    mapping, src_v, src_f = get_part_mapping(src_obj_path, o)
                except Exception as ex:
                    print(f"Mapping error on {p}: {ex}")
                
            out_lines.append(f"o {blender_name}\n")
            
            if len(mapping) == len(mesh.vertices) and len(src_v) == len(mesh.vertices):
                print(f"{p}: 100% UV mapped ({len(mapping)} verts)! Exporting in identical source order.")
                ordered_verts = []
                for svi in range(len(src_v)):
                    dvi = mapping[svi]
                    v = mesh.vertices[dvi]
                    w = mw @ v.co
                    ordered_verts.append([w.x, w.z, -w.y])
                    
                for v in ordered_verts:
                    out_lines.append(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
                    
                for face in src_f:
                    tokens = [str(v_global_offset + int(tok[0])) for tok in face]
                    out_lines.append(f"f {' '.join(tokens)}\n")
                    
                v_global_offset += len(src_v)
            else:
                print(f"{p}: Not fully UV mapped ({len(mapping)}/{len(mesh.vertices)}). Exporting standard Blender mesh.")
                for v in mesh.vertices:
                    w = mw @ v.co
                    out_lines.append(f"v {w.x:.6f} {w.z:.6f} {-w.y:.6f}\n")
                for poly in mesh.polygons:
                    tokens = [str(v_global_offset + vi + 1) for vi in poly.vertices]
                    out_lines.append(f"f {' '.join(tokens)}\n")
                v_global_offset += len(mesh.vertices)

        with open(out_cages_path, "w", encoding="utf-8") as f:
            f.writelines(out_lines)

        print(f"Exported {out_cages_path} with {v_global_offset} vertices successfully!")
    except Exception as e:
        traceback.print_exc()

run()
