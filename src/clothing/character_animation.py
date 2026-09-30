"""Walk animation of a CharacterModel, clothes included, by skinning to the body's game rig.

Every part of the model (skin, garments, hair) is bound once: its vertices get bone weights
(skeleton.Skeleton.weights) from the body part they belong to. Skin parts name their part;
garments, shoes and anything else take the body cage part nearest to each vertex, which is
the part their cage fit placed them on. Hair and the head move rigidly with the head.
Each frame the rest vertices are skinned with the walk pose and written back to the GPU.
"""
from __future__ import annotations

import numpy as np

from .skeleton import CAGE_PART_BONES, Skeleton, skin, walk_rotations

# Model parts that follow one bone as a whole.
RIGID_PARTS = {"head": "Head", "hair_3d": "Head", "hair": "Head", "nose": "Head"}
# Skin parts that name their body part (they still blend at the joints).
SKIN_PARTS = {"neck": "Neck", "arm_left": "UpperArm_L", "forearm_left": "LowerArm_L", "hand_left": "Hand_L",
              "arm_right": "UpperArm_R", "forearm_right": "LowerArm_R", "hand_right": "Hand_R"}
# Walk cycle speed (radians of the cycle per second), as the world token at its default speed.
WALK_SPEED = 11.0


class CharacterAnimator:
    def __init__(self, model, walking: bool = True):
        self.model = model
        self.walking = walking
        self.walk_time = 0.0
        self._bound_key = None
        self._bindings = []
        self._posed = False

    def _body_cage(self):
        from .hsr import engine_to_body_mesh
        from .wear_engine import BODY_CAGES, load_r15_cages
        import os
        from .character_model import MODELS_DIR
        cages = load_r15_cages(os.path.join(MODELS_DIR, BODY_CAGES[self.model.body]))
        points, bones = [], []
        for part, bone in CAGE_PART_BONES.items():
            verts = engine_to_body_mesh(cages[part]["verts"])
            points.append(verts)
            bones.append(np.full(len(verts), self.skeleton.index(bone)))
        return np.vstack(points), np.concatenate(bones)

    def _nearest_bones(self, points, cage_points, cage_bones):
        nearest = np.empty(len(points), dtype=np.int64)
        for start in range(0, len(points), 2048):
            chunk = points[start:start + 2048]
            distance = ((chunk[:, None, :] - cage_points[None]) ** 2).sum(-1)
            nearest[start:start + 2048] = cage_bones[distance.argmin(1)]
        return nearest

    def _bind(self):
        self.skeleton = Skeleton.load(self.model.body)
        cage_points, cage_bones = self._body_cage()
        self._bindings = []
        for part in self.model.parts:
            if part.transform is not None or not hasattr(part.mesh, "read_vertices"):
                continue
            rows = part.mesh.read_vertices()
            if not len(rows):
                continue
            if part.name in RIGID_PARTS:
                bones = np.full(len(rows), self.skeleton.index(RIGID_PARTS[part.name]))
                indices = np.stack([bones, bones], axis=1)
                weights = np.zeros((len(rows), 2))
                weights[:, 0] = 1.0
            else:
                if part.name in SKIN_PARTS:
                    bones = np.full(len(rows), self.skeleton.index(SKIN_PARTS[part.name]))
                else:
                    bones = self._nearest_bones(rows[:, :3].astype(np.float64), cage_points, cage_bones)
                indices, weights = self.skeleton.weights(rows[:, :3], bones)
            self._bindings.append((part, rows, indices, weights))
        self._bound_key = self._key()

    def _key(self):
        return tuple(id(p.mesh) for p in self.model.parts)

    def update(self, dt: float) -> None:
        """Advance the walk by ``dt`` seconds and pose the model (rest pose when not walking)."""
        if self._bound_key != self._key():
            self._bind()  # the model was rebuilt (outfit, body or skin change)
        if not self.walking and not self._posed:
            return
        if self.walking:
            self.walk_time += dt * WALK_SPEED
            rotations, root = walk_rotations(self.walk_time)
        else:
            rotations, root = {}, (0.0, 0.0, 0.0)
        matrices = self.skeleton.pose(rotations, root)
        for part, rows, indices, weights in self._bindings:
            part.mesh.update_vertices(skin(rows, indices, weights, matrices))
        self._posed = self.walking
