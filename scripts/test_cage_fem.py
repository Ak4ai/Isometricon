import os, json
import numpy as np

# Load male cage data
base_dir = r"C:\Users\Henrique\Documents\GitHub\Isometricon"
cage_data = np.load(os.path.join(base_dir, "assets", "models", "roblox_cage_data.npz"))
rest_male = cage_data["cage_verts_rest"].copy()
faces = cage_data["cage_faces"]

print("Rest male shape:", rest_male.shape)
print("Faces shape:", faces.shape)
