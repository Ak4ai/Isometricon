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
# Stretch of the upper arm (m from the shoulder) where a sleeve must have cloth on the outer side.
SLEEVE_PROBE = (0.06, 0.18)
# Skin that may be hidden where it pokes out of the clothes (not the hands, head or neck).
POKING_SKIN = ("arm_left", "arm_right", "forearm_left", "forearm_right", "trunk_skin", "legs_skin", "feet_skin")
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
        return self._sleeveless_on_torso(rows, bone_of[_nearest(rows[:, :3].astype(np.float64), mesh_space)])

    def _sleeveless_on_torso(self, rows, bones):
        """A garment with no sleeve on a side has its arm-bound cloth follow the torso.

        In A-pose the arm cage touches the torso's sides, so the armhole and side panels of a
        sleeveless top get bound to the arm; lowering or swinging the arm would drag them and
        open the top. A sleeve is told by cloth on the outer side of the upper arm, below the
        shoulder: a sleeveless top has none there.
        """
        torso = self.skeleton.index("Torso")
        bones = bones.copy()
        for side, sign in (("L", 1.0), ("R", -1.0)):
            arm = self.skeleton.index(f"UpperArm_{side}")
            mine = np.flatnonzero(bones == arm)
            if not len(mine):
                continue
            head, tail = self.skeleton.heads[arm], self.skeleton.tails[arm]
            axis = (tail - head) / np.linalg.norm(tail - head)
            outward = np.array([sign, 0.0, 0.0]) - axis * axis[0] * sign  # away from the body, across the arm
            outward /= np.linalg.norm(outward)
            offset = rows[mine, :3] - head
            along = offset @ axis
            lateral = offset @ outward
            below_shoulder = (along > SLEEVE_PROBE[0]) & (along < SLEEVE_PROBE[1])
            if (below_shoulder & (lateral > 0.02)).sum() < 10:
                bones[mine] = torso
        return bones

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
        self._hide_skin_poking_out()
        self._bound_key = self._key()
        self._shown = None

    def _hide_skin_poking_out(self):
        """Hide the skin triangles that poke out of the clothes in any pose the game shows.

        HSR decides which skin the clothes cover. Where a garment is tight, or once the arms
        hang or swing, some skin it left comes out through the cloth (a square shoulder
        corner through a sleeve, a triangle's tip through a sweater). A triangle goes when a
        corner has cloth between it and its bone in the fitting pose, the rest pose or the
        walk. Exposed skin never has cloth over it, so it always stays.
        """
        from .layer_clearance import outside_cloth
        cloth = [b for b in self._bindings if b[0].source_obj is not None]
        skin_parts = [b for b in self._bindings if b[0].name in POKING_SKIN and hasattr(b[0].mesh, "read_indices")]
        if not cloth or not skin_parts:
            return
        faces = {b[0].name: b[0].mesh.read_indices().reshape(-1, 3) for b in skin_parts}
        used = {name: np.unique(f) for name, f in faces.items()}
        poking = {name: np.zeros(len(u), dtype=bool) for name, u in used.items()}
        poses = [({}, (0.0, 0.0, 0.0)), (dict(self.rest), (0.0, 0.0, 0.0))]
        for phase in np.linspace(0.0, 2 * np.pi, 4, endpoint=False):
            walk, root = walk_rotations(phase)
            rotations = dict(self.rest)
            for bone, rotation in walk.items():
                rotations[bone] = rotation @ rotations[bone] if bone in rotations else rotation
            poses.append((rotations, root))
        heads, tails = self.skeleton.heads, self.skeleton.tails
        for rotations, root in poses:
            matrices = self.skeleton.pose(rotations, root)
            triangles = []
            for part, rows, indices, weights in cloth:
                posed = skin(rows, indices, weights, matrices)[:, :3]
                triangles.append(posed[part.mesh.read_indices().reshape(-1, 3)])
            triangles = np.concatenate(triangles).astype(np.float64)
            for part, rows, indices, weights in skin_parts:
                name = part.name
                points = skin(rows[used[name]], indices[used[name]], weights[used[name]], matrices)[:, :3]
                # Origins: the closest point of the vertex's own bone, posed.
                bone = indices[used[name], 0]
                head = (matrices[bone, :3, :3] @ heads[bone][..., None])[..., 0] + matrices[bone, :3, 3]
                tail = (matrices[bone, :3, :3] @ tails[bone][..., None])[..., 0] + matrices[bone, :3, 3]
                axis = tail - head
                t = np.clip(((points - head) * axis).sum(1) / (axis * axis).sum(1), 0.0, 1.0)
                poking[name] |= outside_cloth(points, head + t[:, None] * axis, triangles)
        removed = 0
        for part, rows, indices, weights in skin_parts:
            name = part.name
            out = np.zeros(len(rows), dtype=bool)
            out[used[name]] = poking[name]
            hidden = out[faces[name]].any(1)
            if not hidden.any():
                continue
            removed += int(hidden.sum())
            if hidden.all():
                part.mesh.delete()
                self.model.parts.remove(part)  # an empty index buffer would draw every vertex
                self._bindings = [b for b in self._bindings if b[0] is not part]
            else:
                part.mesh.update_buffers(rows.ravel(), faces[name][~hidden].ravel().astype(np.uint32))
        if removed:
            print(f"[Pele] {removed} triângulos de pele furando a roupa escondidos")

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
