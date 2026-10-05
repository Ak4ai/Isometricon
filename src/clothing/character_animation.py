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
# Bones a garment worn on the lower body can follow.
LOWER_BODY = ("Pelvis", "UpperLeg_L", "LowerLeg_L", "Foot_L", "UpperLeg_R", "LowerLeg_R", "Foot_R")
# Distance down the arm (m from the shoulder) past which arm-bound cloth is surely sleeve,
# and down the thigh (m from the hip) past which leg-bound cloth is surely trouser leg.
SLEEVE_BLEND = 0.08
LEG_BLEND = 0.10
# (limb pair, trunk, blend distance) of the joints where cloth weights are smoothed over the garment.
LIMB_BLENDS = [("UpperArm_", "Torso", SLEEVE_BLEND), ("UpperLeg_", "Pelvis", LEG_BLEND)]
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


def _reaches(count, e0, e1, seeds):
    """Mask of the vertices connected, through the edges (e0, e1), to a seed vertex."""
    parent = list(range(count))

    def find(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for a, b in zip(e0.tolist(), e1.tolist()):
        parent[find(a)] = find(b)
    roots = np.array([find(v) for v in range(count)])
    return np.isin(roots, np.unique(roots[seeds]))


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
        if part.name == "bottom":
            # Wide trousers hang next to the hands in the fitting pose and some of their cloth
            # was fitted on the arm cages; a garment of the lower body follows the lower body.
            lower = np.isin(cage_bones, [self.skeleton.index(name) for name in LOWER_BODY])
            stray = ~np.isin(bones, cage_bones[lower])
            bones[stray] = cage_bones[lower][_nearest(rows[stray, :3].astype(np.float64), cage_points[lower])]
            nearest[~np.isin(nearest, cage_bones[lower])] = self.skeleton.index("Pelvis")
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
                    indices, weights = self._attach_limbs(rows[:, :3], part.mesh.read_indices().reshape(-1, 3),
                                                          bones, indices, weights)
            self._bindings.append((part, rows, indices, weights))
        self._bound_key = self._key()
        self._shown = None

    def _subtree(self, bone):
        """Indices of a bone and every bone it carries."""
        found = [bone]
        for other in range(len(self.skeleton.names)):  # parents come first
            if self.skeleton.parents[other] in found:
                found.append(other)
        return found

    def _attach_limbs(self, points, faces, bones, indices, weights):
        """(indices, weights) with smooth limb/trunk weights for the cloth around the shoulders and hips.

        The cage part each cloth vertex was fitted on is a noisy label near the armpit and
        the hip: the outer half of a sleeve is bound to the arm and its inner half to the
        torso, so a swinging arm (it moves rigidly, independent of the torso) would open the
        sleeve like a ring; the seat of a pair of trousers is bound to the pelvis right next
        to cloth bound to a thigh, so a raised leg would tear it. The labels are kept only
        where they are certain: limb cloth well down the limb, and trunk cloth away from the
        limbs. In between, each limb's weight is the harmonic interpolation over the
        garment's own mesh, so the garment stays one piece; cloth between the two limbs
        (the crotch) gets a share of both. Trunk cloth away from the limbs and the skin are
        untouched.
        """
        if not len(faces):
            return indices, weights
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
        for limb_stem, trunk_name, blend in LIMB_BLENDS:
            trunk = self.skeleton.index(trunk_name)
            sides = []  # (limb, certain limb cloth, trunk cloth away from this limb)
            for side in "LR":
                limb = self.skeleton.index(limb_stem + side)
                if not (bone_of == limb).any():
                    continue
                head, tail = self.skeleton.heads[limb], self.skeleton.tails[limb]
                axis = (tail - head) / np.linalg.norm(tail - head)
                offset = position - head
                along = offset @ axis
                radial = np.linalg.norm(offset - along[:, None] * axis, axis=1)
                reach = 1.25 * np.percentile(radial[bone_of == limb], 90)
                sure = (bone_of == limb) & (along > blend)
                # Where the garment joins this limb's cloth to the opposite limb's (the crotch
                # seam of trousers), the limb is certain only past the end of that seam.
                opposite = bone_of == self.skeleton.index(limb_stem + ("R" if side == "L" else "L"))
                seam = np.concatenate([edges[opposite[edges[:, 1]] & (bone_of[edges[:, 0]] == limb), 0],
                                       edges[opposite[edges[:, 0]] & (bone_of[edges[:, 1]] == limb), 1]])
                if len(seam):
                    sure &= along > along[seam].max() + blend
                if sure.any():
                    sides.append((limb, sure, (radial > reach) | (along < 0.0)))
            if not sides:
                continue
            limbs = np.isin(bone_of, [limb for limb, _, _ in sides])
            involved = limbs | (bone_of == trunk)
            away = (bone_of == trunk) & np.all([far for _, _, far in sides], axis=0)
            certain = np.any([sure for _, sure, _ in sides], axis=0)
            free = involved & ~away & ~certain
            if not free.any():
                continue
            inside = involved[edges[:, 0]] & involved[edges[:, 1]]
            e0, e1 = edges[inside, 0], edges[inside, 1]
            links = np.bincount(np.concatenate([e0, e1]), minlength=count).astype(np.float64)
            solve = free & (links > 0)
            follows = []
            for limb, sure, _ in sides:
                follow = np.where(bone_of == limb, 1.0, 0.0)
                for _ in range(300):
                    total = np.zeros(count)
                    np.add.at(total, e0, follow[e1])
                    np.add.at(total, e1, follow[e0])
                    follow[solve] = total[solve] / links[solve]
                follows.append(follow)
            follows = np.stack(follows, axis=1)
            # A loose piece (a pocket, a chain) with nothing certain in it has no weights of
            # its own: it takes those of the nearest cloth of the rest of the garment.
            anchored = _reaches(count, e0, e1, involved & ~free)
            loose = solve & ~anchored
            if loose.any() and (involved & anchored).any():
                source = np.flatnonzero(involved & anchored)
                follows[loose] = follows[source[_nearest(position[loose], position[source])]]
            follows /= np.maximum(follows.sum(1, keepdims=True), 1.0)
            # This joint's cloth weights come from the garment alone: certain cloth is whole.
            joint = [limb for limb, _, _ in sides] + [trunk]
            whole = np.flatnonzero((involved & ~free)[weld] & np.isin(indices, joint).all(1))
            indices[whole] = bones[whole, None]
            weights[whole] = 0.0
            weights[whole, 0] = 1.0
            # The limb's share of a vertex goes to the bones it already had down that limb
            # (its knee or elbow blend); what is left stays with the trunk.
            rows = np.flatnonzero(free[weld])
            had = indices.shape[1]
            pad = len(sides) + 1
            indices = np.concatenate([indices, np.repeat(indices[:, :1], pad, axis=1)], axis=1)
            weights = np.concatenate([weights, np.zeros((len(weights), pad))], axis=1)
            share = follows[weld[rows]]
            old_indices, old_weights = indices[rows, :had].copy(), weights[rows, :had].copy()
            weights[rows] = 0.0
            for column, (limb, _, _) in enumerate(sides):
                down = np.isin(old_indices, self._subtree(limb)) & (old_weights > 0)
                kept = np.where(down, old_weights, 0.0)
                own = kept.sum(1) > 0
                weights[rows[own], :had] += (kept[own] / kept[own].sum(1, keepdims=True)) * share[own, column, None]
                indices[rows, had + column] = limb
                weights[rows[~own], had + column] = share[~own, column]
            indices[rows, had + len(sides)] = trunk
            weights[rows, had + len(sides)] = 1.0 - share.sum(1)
        return indices, weights

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
