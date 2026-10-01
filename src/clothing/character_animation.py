"""Rest pose and walk of a CharacterModel, clothes included, by skinning to the body's game rig.

The body and the garments are fitted in A-pose; the game shows them in its rest pose (arms
hanging, skeleton.rest_rotations) and animates from there.

Every part of the model (skin, garments, hair) is bound once: its vertices get bone weights
(skeleton.Skeleton.weights) from the body part they belong to. Skin parts name their part;
a fitted garment uses the body cage part each vertex was bound to when it was fitted
(wear_engine.body_parts_path), reconciled with its final position along that limb's
ancestry. Body skin only uses bones belonging to its own anatomical region. Hair and
the head move rigidly with the head. Each frame the rest vertices are skinned and written
back to the GPU; animation never removes skin triangles.
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
# These meshes combine several exported body groups. Proximity must not assign
# their vertices to an adjacent arm or to a different anatomical region.
SKIN_REGIONS = {"trunk_skin": ("Torso", "Pelvis"),
                "legs_skin": ("UpperLeg_L", "LowerLeg_L", "Foot_L", "UpperLeg_R", "LowerLeg_R", "Foot_R"),
                "feet_skin": ("Foot_L", "Foot_R")}
# Distance down the arm (m from the shoulder) past which arm-bound cloth is surely sleeve.
SLEEVE_BLEND = 0.08
# Walk cycle speed (radians of the cycle per second), as the world token at its default speed.
WALK_SPEED = 11.0


def _nearest(points, targets, chunk=2048):
    """Index of the nearest target for each point. Render buffers repeat every vertex once
    per face corner, so the search runs on the distinct positions only."""
    points = np.ascontiguousarray(points, dtype=np.float32)
    targets = np.ascontiguousarray(targets, dtype=np.float32)
    unique, inverse = np.unique(points, axis=0, return_inverse=True)
    nearest = np.empty(len(unique), dtype=np.int64)
    squares = (targets ** 2).sum(1)
    for start in range(0, len(unique), chunk):
        block = unique[start:start + chunk]
        nearest[start:start + chunk] = (squares[None] - 2.0 * block @ targets.T).argmin(1)
    return nearest[inverse.ravel()]


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
        bones = bone_of[_nearest(rows[:, :3].astype(np.float64), mesh_space)]
        cage_points, cage_bones = self._cage_binding
        nearest = cage_bones[_nearest(rows[:, :3].astype(np.float64), cage_points)]
        return self.skeleton.reconcile_fitted_bones(bones, nearest)

    def _bind(self):
        self.skeleton = Skeleton.load(self.model.body)
        cage_points, cage_bones = self._body_cage()
        self._cage_binding = cage_points, cage_bones
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
                elif part.name in SKIN_REGIONS:
                    allowed = [self.skeleton.index(name) for name in SKIN_REGIONS[part.name]]
                    region = np.isin(cage_bones, allowed)
                    bones = cage_bones[region][_nearest(rows[:, :3].astype(np.float64), cage_points[region])]
                else:
                    bones = self._fitted_bones(part, rows)
                    if bones is None:
                        bones = cage_bones[_nearest(rows[:, :3].astype(np.float64), cage_points)]
                indices, weights = self.skeleton.weights(rows[:, :3], bones)
                if part.source_obj is not None:
                    self._attach_sleeves(rows[:, :3], part.mesh.read_indices().reshape(-1, 3), bones, indices, weights)
            self._bindings.append((part, rows, indices, weights))
        self._bound_key = self._key()
        self._shown = None

    def _attach_sleeves(self, points, faces, bones, indices, weights):
        """Smooth arm/torso weights for the cloth around each shoulder (edits ``indices``/``weights``).

        The cage part each cloth vertex was fitted on is a noisy label near the armpit: the
        outer half of a sleeve is bound to the arm and its inner half to the torso, so a
        swinging arm (it moves rigidly, independent of the torso) would open the sleeve like
        a ring. The labels are kept only where they are certain: arm cloth well down the
        sleeve, and torso cloth away from the arm. In between, the arm's weight is the
        harmonic interpolation over the garment's own mesh, so the sleeve stays one piece,
        joined to the body of the garment. Torso cloth away from the arm and the skin are
        untouched.
        """
        if not len(faces):
            return
        key = {}
        weld = np.array([key.setdefault(tuple(p), len(key)) for p in np.round(points, 5).tolist()])
        count = len(key)
        position = np.zeros((count, 3))
        position[weld] = points
        bone_of = np.zeros(count, dtype=np.int64)
        bone_of[weld] = bones
        welded = weld[faces]
        edges = np.unique(np.sort(np.concatenate([welded[:, [0, 1]], welded[:, [1, 2]], welded[:, [2, 0]]]), axis=1),
                          axis=0)
        edges = edges[edges[:, 0] != edges[:, 1]]
        degree = np.bincount(edges.ravel(), minlength=count).astype(np.float64)
        torso = self.skeleton.index("Torso")
        for side in "LR":
            arm = self.skeleton.index(f"UpperArm_{side}")
            if not (bone_of == arm).any():
                continue
            head, tail = self.skeleton.heads[arm], self.skeleton.tails[arm]
            axis = (tail - head) / np.linalg.norm(tail - head)
            offset = position - head
            along = offset @ axis
            radial = np.linalg.norm(offset - along[:, None] * axis, axis=1)
            reach = 1.25 * np.percentile(radial[bone_of == arm], 90)
            involved = (bone_of == arm) | (bone_of == torso)
            sure_arm = (bone_of == arm) & (along > SLEEVE_BLEND)
            sure_torso = (bone_of == torso) & ((radial > reach) | (along < 0.0))
            free = involved & ~sure_arm & ~sure_torso
            if not free.any():
                continue
            follow = np.where(bone_of == arm, 1.0, 0.0)
            inside = involved[edges[:, 0]] & involved[edges[:, 1]]
            e0, e1 = edges[inside, 0], edges[inside, 1]
            links = np.bincount(np.concatenate([e0, e1]), minlength=count).astype(np.float64)
            solve = free & (links > 0)
            for _ in range(300):
                total = np.zeros(count)
                np.add.at(total, e0, follow[e1])
                np.add.at(total, e1, follow[e0])
                follow[solve] = total[solve] / links[solve]
            rows = np.flatnonzero(free[weld])
            indices[rows] = [arm, torso]
            weights[rows] = np.stack([follow[weld[rows]], 1.0 - follow[weld[rows]]], axis=1)

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
