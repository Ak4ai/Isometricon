"""Rest pose and walk of a CharacterModel, clothes included, by skinning to the body's game rig.

The body and the garments are fitted in A-pose; the game shows them in its rest pose (arms
hanging, skeleton.rest_rotations) and animates from there.

Every part of the model (skin, garments, hair) is bound once: its vertices get bone weights
(skeleton.Skeleton.weights) from the body part they belong to. Skin parts name their part;
a fitted garment uses the body cage part each vertex was bound to when it was fitted
(wear_engine.body_parts_path), and anything without that record takes the nearest body
cage part. Hair and the head move rigidly with the head. Each frame the rest vertices are
skinned and written back to the GPU.
"""
from __future__ import annotations

import os

import numpy as np

from .skeleton import CAGE_PART_BONES, Skeleton, rest_arm_angle, rest_rotations, skin, walk_rotations

# Model parts that follow one bone as a whole.
RIGID_PARTS = {"head": "Head", "hair_3d": "Head", "hair": "Head", "nose": "Head"}
# Skin parts that name their body part (they still blend at the joints).
SKIN_PARTS = {"neck": "Neck", "arm_left": "UpperArm_L", "forearm_left": "LowerArm_L", "hand_left": "Hand_L",
              "arm_right": "UpperArm_R", "forearm_right": "LowerArm_R", "hand_right": "Hand_R"}
# Walk cycle speed (radians of the cycle per second), as the world token at its default speed.
WALK_SPEED = 11.0


def _nearest(points, targets, chunk=2048):
    nearest = np.empty(len(points), dtype=np.int64)
    for start in range(0, len(points), chunk):
        distance = ((points[start:start + chunk, None, :] - targets[None]) ** 2).sum(-1)
        nearest[start:start + chunk] = distance.argmin(1)
    return nearest


class CharacterAnimator:
    def __init__(self, model, walking: bool = True):
        self.model = model
        self.walking = walking
        self.walk_time = 0.0
        self._bound_key = None
        self._bindings = []
        self._shown = None  # "rest" or "walk": what the GPU buffers hold

    def _body_cage(self):
        from .character_model import MODELS_DIR
        from .hsr import engine_to_body_mesh
        from .wear_engine import BODY_CAGES, load_r15_cages
        cages = load_r15_cages(os.path.join(MODELS_DIR, BODY_CAGES[self.model.body]))
        points, bones = [], []
        for part, bone in CAGE_PART_BONES.items():
            verts = engine_to_body_mesh(cages[part]["verts"])
            points.append(verts)
            bones.append(np.full(len(verts), self.skeleton.index(bone)))
        return np.vstack(points), np.concatenate(bones)

    def _rest_arm_angle(self, cage_points, cage_bones):
        """Rest angle of the arms that keeps the hands off this body's hips."""
        names = np.array(self.skeleton.names)[cage_bones]
        trunk_and_legs = ~(np.char.find(names.astype(str), "Arm") >= 0) & ~(np.char.find(names.astype(str), "Hand") >= 0)
        arm_radius = []
        for bone in ("LowerArm_L", "Hand_L"):
            b = self.skeleton.index(bone)
            head, axis = self.skeleton.heads[b], self.skeleton.tails[b] - self.skeleton.heads[b]
            offset = cage_points[cage_bones == b] - head
            along = offset @ axis / (axis @ axis)
            arm_radius.append(np.linalg.norm(offset - along[:, None] * axis, axis=1))
        return rest_arm_angle(self.skeleton, cage_points[trunk_and_legs], float(np.median(np.concatenate(arm_radius))))

    def _fitted_bones(self, part, rows):
        """Bones from the cage parts the garment's vertices were bound to, or None."""
        from .wear_engine import body_parts_path
        if not part.source_obj or not os.path.exists(body_parts_path(part.source_obj)):
            return None
        names = np.load(body_parts_path(part.source_obj))
        with open(part.source_obj, encoding="utf-8", errors="ignore") as fp:
            verts = np.array([[float(x) for x in line.split()[1:4]] for line in fp if line.startswith("v ")])
        if len(verts) != len(names):
            return None
        mesh_space = np.c_[verts[:, 0], verts[:, 2], -verts[:, 1]]  # as parse_obj_as_mesh places them
        bone_of = np.array([self.skeleton.index(CAGE_PART_BONES[n]) for n in names])
        return bone_of[_nearest(rows[:, :3].astype(np.float64), mesh_space)]

    def _bind(self):
        self.skeleton = Skeleton.load(self.model.body)
        cage_points, cage_bones = self._body_cage()
        self.rest = rest_rotations(self.skeleton, self._rest_arm_angle(cage_points, cage_bones))
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
                    bones = self._fitted_bones(part, rows)
                    if bones is None:
                        bones = cage_bones[_nearest(rows[:, :3].astype(np.float64), cage_points)]
                indices, weights = self.skeleton.weights(rows[:, :3], bones)
            self._bindings.append((part, rows, indices, weights))
        self._bound_key = self._key()
        self._shown = None

    def _key(self):
        return tuple(id(p.mesh) for p in self.model.parts)

    def update(self, dt: float) -> None:
        """Advance the walk by ``dt`` seconds and pose the model (the rest pose when not walking)."""
        if self._bound_key != self._key():
            self._bind()  # the model was rebuilt (outfit, body or skin change)
        if not self.walking and self._shown == "rest":
            return
        rotations, root = dict(self.rest), (0.0, 0.0, 0.0)
        if self.walking:
            self.walk_time += dt * WALK_SPEED
            walk, root = walk_rotations(self.walk_time)
            for bone, rotation in walk.items():
                rotations[bone] = rotation @ rotations[bone] if bone in rotations else rotation
        matrices = self.skeleton.pose(rotations, root)
        for part, rows, indices, weights in self._bindings:
            part.mesh.update_vertices(skin(rows, indices, weights, matrices))
        self._shown = "walk" if self.walking else "rest"
