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

from . import body_shape
from .skeleton import CAGE_PART_BONES, Skeleton, partial_rotation, rest_arm_angle, rest_rotations, skin, walk_rotations

# Model parts that follow one bone as a whole.
RIGID_PARTS = {"head": "Head", "hair_3d": "Head", "hair": "Head", "nose": "Head", "ears": "Head"}
# Skin parts that name their body part (they still blend at the joints).
SKIN_PARTS = {"neck": "Neck", "arm_left": "UpperArm_L", "forearm_left": "LowerArm_L", "hand_left": "Hand_L",
              "arm_right": "UpperArm_R", "forearm_right": "LowerArm_R", "hand_right": "Hand_R"}
# These meshes combine several exported body groups. Proximity must not assign
# their vertices to an adjacent arm or to a different anatomical region.
SKIN_REGIONS = {"trunk_skin": ("Torso", "Pelvis"),
                "legs_skin": ("UpperLeg_L", "LowerLeg_L", "Foot_L", "UpperLeg_R", "LowerLeg_R", "Foot_R"),
                "feet_skin": ("Foot_L", "Foot_R")}
# Distance down the arm (m from the shoulder) past which arm-bound cloth is surely sleeve,
# and down the thigh (m from the hip) past which leg-bound cloth is surely trouser leg.
SLEEVE_BLEND = 0.08
LEG_BLEND = 0.10
# (limb pair, trunk, blend distance) of the joints where cloth weights are smoothed over the garment.
LIMB_BLENDS = [("UpperArm_", "Torso", SLEEVE_BLEND), ("UpperLeg_", "Pelvis", LEG_BLEND)]
# Cloth that does not wrap a limb follows it fully up to the first distance (m) from the bone and
# not at all past the second.
FAR_CLOTH = (0.20, 0.40)
# Cloth wraps a stretch of a limb when most of its slices this long (m) leave no gap this wide (rad)
# around the bone.
WRAP_SLICE, WRAP_GAP = 0.08, np.radians(120)
# How far (m) along the garment trunk cloth counts as part of a patch of limb cloth.
WRAP_REACH = 0.15
# A sleeve has a wall between the arm and the torso: cloth within this angle of the way to the
# torso, nearer the arm than this share of the way. A cape or a whole-body costume wraps the arm
# together with the torso and has none.
SLEEVE_WALL_CONE, SLEEVE_WALL_SHARE = np.radians(60), 0.5
# A connected piece of a garment with at least this share of its vertices on one limb is all on it.
LIMB_PIECE = 0.6
# A connected piece of a garment with no more vertices than this moves as one.
SMALL_PIECE = 30
# The arms open at rest as far as the clothes need and no further than this. From the study of the
# catalogue (scripts/study_rest_arm_angle.py): every ordinary garment, the widest trousers and
# coats included, is cleared by 30 degrees; only ball gowns and whole-body costumes ask for more,
# and those ask for the fitting pose itself.
REST_ARM_LIMIT = np.radians(30.0)
FITTING_ARM_ANGLE = np.radians(45.0)
# Shares of the walk's arm swing tried, most first, and the cloth (m2) the arms may tear beyond
# what the legs tear (1500 cm2: an ordinary top stretches up to ~1200 under a swinging arm
# without showing; costumes and capes tear several thousand). A cloth
# triangle is torn when an edge grows past TEAR_RATIO and by more than TEAR_GROWTH (m).
ARM_SWINGS, ARM_SWING_TEAR = (1.0, 0.6, 0.35), 0.15
TEAR_RATIO, TEAR_GROWTH = 2.5, 0.02
# Bones that can move one cloth vertex.
CLOTH_INFLUENCES = 4
# How fast (1/s) the pose eases into the walk when starting and back to rest when stopping.
STRIDE_EASE = 10.0
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


def _components(count, e0, e1):
    """A label per vertex, equal for the vertices joined by the edges (e0, e1)."""
    parent = list(range(count))

    def find(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for a, b in zip(e0.tolist(), e1.tolist()):
        parent[find(a)] = find(b)
    return np.array([find(v) for v in range(count)])


def _reaches(count, e0, e1, seeds):
    """Mask of the vertices connected, through the edges (e0, e1), to a seed vertex."""
    roots = _components(count, e0, e1)
    return np.isin(roots, np.unique(roots[seeds]))


def _spread(bone_of, stray, edges):
    """Give the stray vertices the bone of the cloth around them, from their edge inwards (in place)."""
    stray = stray.copy()
    while stray.any():
        took = False
        for a, b in ((edges[:, 0], edges[:, 1]), (edges[:, 1], edges[:, 0])):
            fill = stray[a] & ~stray[b]
            if fill.any():
                bone_of[a[fill]] = bone_of[b[fill]]
                stray[a[fill]] = False
                took = True
        if not took:
            break


def _torn_area(rows, posed, faces):
    """Area (m2) of the cloth triangles a pose tears: an edge grown past TEAR_RATIO and by TEAR_GROWTH."""
    torn = np.zeros(len(faces), dtype=bool)
    for i, j in ((0, 1), (1, 2), (2, 0)):
        before = np.linalg.norm(rows[faces[:, i], :3] - rows[faces[:, j], :3], axis=1)
        after = np.linalg.norm(posed[faces[:, i], :3] - posed[faces[:, j], :3], axis=1)
        torn |= (before > 1e-5) & (after > TEAR_RATIO * before) & (after - before > TEAR_GROWTH)
    a, b, c = (posed[faces[torn, k], :3].astype(np.float64) for k in range(3))
    return float(0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1).sum())


def _within(position, edges, seeds, limit):
    """Mask of the vertices no farther than ``limit`` from a seed, walking along the edges."""
    distance = np.where(seeds, 0.0, np.inf)
    if not seeds.any():
        return seeds
    length = np.linalg.norm(position[edges[:, 0]] - position[edges[:, 1]], axis=1)
    while True:
        closer = distance.copy()
        np.minimum.at(closer, edges[:, 0], distance[edges[:, 1]] + length)
        np.minimum.at(closer, edges[:, 1], distance[edges[:, 0]] + length)
        closer[closer > limit] = np.inf
        if np.array_equal(closer, distance):
            return np.isfinite(distance)
        distance = closer


class CharacterAnimator:
    def __init__(self, model, walking: bool = True):
        self.model = model
        self.walking = walking
        self.walk_time = 0.0
        self.stride = 0.0  # how far into the walk the pose is: 0 at rest, 1 walking
        self._bound_key = None
        self._bindings = []
        self._shown = None  # "rest" or "walk": what the GPU buffers hold
        self._shape, self._warped, self._scales, self._height = None, False, {}, 1.0  # body adjustments in use
        self._lift, self._cloth_normals, self._bound_nose_style = 0.0, {}, None
        self._posed = None  # the bones of the last points given to posed()
        self._arms = []     # the bones of the two arms
        self.arms_out = False     # stand with the arms at 90 degrees (the character editor's fine adjustment)
        self._arms_shown = False
        self._bound_rows = []

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

    def _rest_arm_angle(self, cage_points, cage_bones, cloth_points=None, sleeve_radius=0.0):
        """Rest angle of the arms that keeps the hands off this body's hips, and off the clothes
        the arms do not carry (a wide coat, a ball gown). The arm is as thick as what it wears
        (``sleeve_radius``): a wide sleeve must clear the hips too."""
        names = np.array(self.skeleton.names)[cage_bones]
        trunk_and_legs = ~(np.char.find(names.astype(str), "Arm") >= 0) & ~(np.char.find(names.astype(str), "Hand") >= 0)
        arm_radius = []
        for bone in ("LowerArm_L", "Hand_L"):
            b = self.skeleton.index(bone)
            head, axis = self.skeleton.heads[b], self.skeleton.tails[b] - self.skeleton.heads[b]
            offset = cage_points[cage_bones == b] - head
            along = offset @ axis / (axis @ axis)
            arm_radius.append(np.linalg.norm(offset - along[:, None] * axis, axis=1))
        radius = float(np.median(np.concatenate(arm_radius)))
        alone = rest_arm_angle(self.skeleton, cage_points[trunk_and_legs], radius)
        beside = cage_points[trunk_and_legs]
        if cloth_points is not None and len(cloth_points):
            beside = np.vstack([beside, cloth_points])
        elif sleeve_radius <= radius:
            return alone
        dressed = rest_arm_angle(self.skeleton, beside, max(radius, sleeve_radius), largest=FITTING_ARM_ANGLE)
        if dressed >= FITTING_ARM_ANGLE:
            return alone  # a costume the arms are inside of: no opening clears it
        return max(alone, min(dressed, REST_ARM_LIMIT))

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

    def posed(self, points, normals):
        """Points given in the fitting pose, and their normals, as the body is posed now: each
        follows the bones of the part of the body cage nearest it (None before the first pose)."""
        bones = getattr(self.model, "bones", None)
        if bones is None or getattr(self, "_cage_binding", None) is None:
            return None
        if self._posed is None or len(self._posed) > 4:
            self._posed = {}
        found = self._posed.get(id(points))
        if found is None or found[0] is not points:
            cage_points, cage_bones = self._cage_binding
            where = np.asarray(points, dtype=np.float64)
            found = self._posed[id(points)] = (points,) + tuple(self.skeleton.weights(where, cage_bones[_nearest(where, cage_points)]))
        rows = skin(np.column_stack((np.asarray(points, dtype=np.float64), np.asarray(normals, dtype=np.float64))),
                    found[1], found[2], np.asarray(bones, dtype=np.float64))
        return rows[:, :3], rows[:, 3:6]

    def _bind(self):
        self._posed = None
        self.skeleton = Skeleton.load(self.model.body)
        cage_points, cage_bones = self._body_cage()
        self._cage_binding = cage_points, cage_bones
        self.rest = rest_rotations(self.skeleton, self._rest_arm_angle(cage_points, cage_bones))
        # The meshes that stay from the last binding (the clothes, when only the skin was cut again)
        # hold in their buffers the vertices as adjusted: they are bound again from the vertices
        # they came with, or every adjustment would be applied over the last one.
        kept = {id(part.mesh): (part.mesh, rows) for (part, *_), rows in zip(self._bindings, getattr(self, "_bound_rows", None) or [])}
        self._bindings = []
        reused = False
        no_arm = ~np.isin(cage_bones, [b for side in "LR" for b in self._subtree(self.skeleton.index("UpperArm_" + side))])
        beside = cage_bones[no_arm]  # the body part beside a point, the arms aside
        for part in self.model.parts:
            if part.transform is not None or not hasattr(part.mesh, "read_vertices"):
                continue
            before = kept.get(id(part.mesh))
            rows = before[1] if before is not None and before[0] is part.mesh else part.mesh.read_vertices()
            reused = reused or (before is not None and before[0] is part.mesh)
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
                if part.source_obj is not None:
                    indices, weights = self._cloth_weights(rows[:, :3], part.mesh.read_indices().reshape(-1, 3), bones,
                                                           beside[_nearest(rows[:, :3].astype(np.float64), cage_points[no_arm])])
                else:
                    indices, weights = self.skeleton.weights(rows[:, :3], bones)
            self._bindings.append((part, rows, indices, weights))
            if hasattr(part.mesh, "set_skin"):
                part.mesh.set_skin(indices, weights)
        arms = [b for side in "LR" for b in self._subtree(self.skeleton.index("UpperArm_" + side))]
        self._arms = arms
        beside_arms = [rows[np.where(np.isin(indices, arms), weights, 0.0).sum(1) < 0.05, :3]
                       for part, rows, indices, weights in self._bindings if part.source_obj is not None]
        if beside_arms:
            # How thick the forearms and hands are with what they wear: most of that cloth lies within it.
            around = []
            for side in "LR":
                for bone in (self.skeleton.index("LowerArm_" + side), self.skeleton.index("Hand_" + side)):
                    for part, rows, indices, weights in self._bindings:
                        if part.source_obj is not None:
                            worn = rows[np.where(indices == bone, weights, 0.0).sum(1) > 0.5, :3]
                            if len(worn):
                                around.append(self._around(bone, worn.astype(np.float64))[1])
            sleeve = float(np.percentile(np.concatenate(around), 90)) if around else 0.0
            self.rest = rest_rotations(self.skeleton, self._rest_arm_angle(cage_points, cage_bones, np.vstack(beside_arms), sleeve))
        self.arm_swing = 1.0
        self.arm_swing = self._arm_swing()
        self._bound_rows = [rows for _, rows, _, _ in self._bindings]  # as fitted, before any body adjustment
        # Taken again from the model on the next update; a mesh kept may hold the last adjustments, so all are written again.
        self._shape, self._warped = None, reused
        self._cloth_normals = {}
        # The style the nose's mesh was built in: the style chosen may have changed since then
        # (a command or a saved character applied before the first frame), and is then put on in _reshape.
        self._bound_nose_style = getattr(self.model, "built_nose_style", self._nose_style())
        self._bound_key = self._key()
        self._shown = None

    def walk_pose(self, walk_time, stride=1.0):
        """(rotations, root) of the walk at ``walk_time``, ``stride`` of the way from the rest pose."""
        # ``arms_out``: the arms straight out to the sides, to see and reach what they hide at rest.
        rotations, root = dict(rest_rotations(self.skeleton, np.pi / 2) if self.arms_out else self.rest), (0.0, 0.0, 0.0)
        if stride > 0.0:
            walk, root = walk_rotations(walk_time)
            for bone, rotation in walk.items():
                swing = self.arm_swing if bone.startswith(("UpperArm_", "LowerArm_")) else 1.0
                rotation = partial_rotation(rotation, stride * swing)
                rotations[bone] = rotation @ rotations[bone] if bone in rotations else rotation
            root = tuple(stride * np.asarray(root, dtype=np.float64))
        return rotations, root

    def _arm_swing(self):
        """How much of the walk's arm swing the clothes allow: the most (of ARM_SWINGS) that
        tears no more than ARM_SWING_TEAR of cloth beyond what the legs alone tear. An arm
        inside a costume or under a cape, swinging fully, drags the cloth that stays with
        the trunk (or comes out through it)."""
        cloth = [(rows, indices, weights, part.mesh.read_indices().reshape(-1, 3))
                 for part, rows, indices, weights in self._bindings if part.source_obj is not None]
        if not cloth:
            return 1.0

        def torn(amount):
            self.arm_swing = amount
            area = 0.0
            for phase in (0.0, np.pi):
                matrices = self.skeleton.pose(*self.walk_pose(phase))
                area = max(area, sum(_torn_area(rows, skin(rows, i, w, matrices), f) for rows, i, w, f in cloth))
            return area

        legs_alone = torn(0.0)
        for amount in ARM_SWINGS:
            if torn(amount) - legs_alone <= ARM_SWING_TEAR:
                return amount
        return ARM_SWINGS[-1]

    def _subtree(self, bone):
        """Indices of a bone and every bone it carries."""
        found = [bone]
        for other in range(len(self.skeleton.names)):  # parents come first
            if self.skeleton.parents[other] in found:
                found.append(other)
        return found

    def _mirror(self):
        """For each bone, the same bone on the other side of the body (itself in the middle)."""
        names = self.skeleton.names
        swap = {"L": "R", "R": "L"}
        return np.array([names.index(n[:-1] + swap[n[-1]]) if n[-2:] in ("_L", "_R") else i for i, n in enumerate(names)])

    def _clean_labels(self, bone_of, edges):
        """The bone of each cloth vertex with the labels a garment cannot have removed.

        The cage part a vertex was fitted on only says which cage was nearest. A skirt that
        hangs next to the hands has cloth labelled with the hand, and a leg warmer has cloth
        labelled with the other leg. Within one connected piece of the garment:
        - a small piece (a chain link, a button) is rigid: it goes with the bone most of it has;
        - a piece on the limbs alone (a glove, a leg warmer) that is almost all on one side
          belongs to that side;
        - a piece that is mostly on one limb (a sleeve sewn apart from the body of a coat) is
          all on that limb, whatever body part its inner side was nearest to;
        - in a piece that reaches the trunk, cloth of a bone must join, through the garment,
          cloth of that bone's parent, down from the trunk (a sleeve is hand, forearm,
          upper arm, torso); cloth that does not takes the bone of the cloth around it.
        """
        bone_of = bone_of.copy()
        count = len(bone_of)
        parents = self.skeleton.parents
        chains = {stem: [self._subtree(self.skeleton.index(stem + side)) for side in "LR"] for stem, _, _ in LIMB_BLENDS}
        on_limb = np.isin(np.arange(len(parents)), [b for pair in chains.values() for chain in pair for b in chain])
        mirror = self._mirror()
        piece = _components(count, edges[:, 0], edges[:, 1])
        for root in np.unique(piece):
            inside = piece == root
            if inside.sum() <= SMALL_PIECE:
                bone_of[inside] = np.bincount(bone_of[inside]).argmax()
            elif on_limb[bone_of[inside]].all():
                for left, right in chains.values():
                    is_left, is_right = inside & np.isin(bone_of, left), inside & np.isin(bone_of, right)
                    few, many = sorted((is_left, is_right), key=lambda mask: mask.sum())
                    if few.any() and few.sum() < 0.35 * (few.sum() + many.sum()):
                        bone_of[few] = mirror[bone_of[few]]
            else:
                for chain in (chain for pair in chains.values() for chain in pair):
                    own = np.isin(bone_of, chain)
                    if (inside & own).sum() >= LIMB_PIECE * inside.sum():
                        _spread(bone_of, inside & ~own, edges)
        same = bone_of[edges[:, 0]] == bone_of[edges[:, 1]]
        region = _components(count, edges[same, 0], edges[same, 1])
        region_bone = {int(r): int(bone_of[r]) for r in np.unique(region)}  # a root vertex stands for its region
        borders = {}
        for a, b in zip(region[edges[~same, 0]].tolist(), region[edges[~same, 1]].tolist()):
            borders.setdefault(a, set()).add(b)
            borders.setdefault(b, set()).add(a)
        rooted = {r for r, bone in region_bone.items() if not on_limb[bone]}
        grew = True
        while grew:
            grew = False
            for r, bone in region_bone.items():
                if r in rooted:
                    continue
                if any(n in rooted and region_bone[n] == parents[bone] for n in borders.get(r, ())):
                    rooted.add(r)
                    grew = True
        with_trunk = np.isin(piece, np.unique(piece[~on_limb[bone_of]]))
        stray = with_trunk & ~np.isin(region, list(rooted))
        _spread(bone_of, stray, edges)
        return bone_of

    def _stretches(self):
        """(bone that gives the axis, bones of the stretch) for the two stretches of each limb:
        the upper one, and the lower one with its hand or foot."""
        found = []
        for stem, _, _ in LIMB_BLENDS:
            for side in "LR":
                chain = self._subtree(self.skeleton.index(stem + side))
                found += [(chain[0], chain[:1]), (chain[1], chain[1:])]
        return found

    def _around(self, bone, points):
        """(distance along, distance from, angle around) a bone's axis for each point."""
        head, tail = self.skeleton.heads[bone], self.skeleton.tails[bone]
        axis = (tail - head) / np.linalg.norm(tail - head)
        offset = points - head
        along = offset @ axis
        across = offset - along[:, None] * axis
        u = np.cross(axis, [0.0, 0.0, 1.0] if abs(axis[2]) < 0.9 else [1.0, 0.0, 0.0])
        u /= np.linalg.norm(u)
        return along, np.linalg.norm(across, axis=1), np.arctan2(across @ np.cross(axis, u), across @ u)

    def _wrapping(self, position, bone_of, edges):
        """Mask of the cloth that wraps the limb it is labelled with (a sleeve, a trouser leg,
        however wide), as opposed to cloth that only lies or hangs near it (the side of a coat
        next to the arm, a cape behind the legs). Each connected patch of a stretch of limb
        wraps it when most of its slices leave no wide gap around the bone, and, on an arm,
        have a wall between the arm and the torso (a sleeve, not a cape over arm and torso)."""
        wraps = np.zeros(len(position), dtype=bool)
        trunk = ~np.isin(bone_of, [b for _, labels in self._stretches() for b in labels])
        arms = {self.skeleton.index(f"{name}_{side}") for name in ("UpperArm", "LowerArm") for side in "LR"}
        torso = self.skeleton.index("Torso")
        torso_head = self.skeleton.heads[torso]
        torso_axis = self.skeleton.tails[torso] - torso_head
        torso_axis = torso_axis / np.linalg.norm(torso_axis)
        for bone, labels in self._stretches():
            mine = np.isin(bone_of, labels)
            if not mine.any():
                continue
            both = mine[edges[:, 0]] & mine[edges[:, 1]]
            patch = _components(len(position), edges[both, 0], edges[both, 1])
            for root in np.unique(patch[mine]):
                inside = mine & (patch == root)
                # The other half of a sleeve is often labelled with the torso: the patch is
                # taken with the trunk cloth the garment joins to it nearby.
                allowed = inside | trunk
                joined = edges[allowed[edges[:, 0]] & allowed[edges[:, 1]]]
                ring = np.flatnonzero(_within(position, joined, inside, WRAP_REACH))
                along, radial, angle = self._around(bone, position[ring])
                slices = np.floor(along / WRAP_SLICE).astype(int)
                closed = []
                for k in np.unique(slices[inside[ring]]):
                    here = slices == k
                    turns = np.sort(angle[here])
                    wrapped = np.diff(np.concatenate([turns, turns[:1] + 2 * np.pi])).max() < WRAP_GAP
                    if wrapped and bone in arms:
                        wrapped = self._has_wall(bone, (k + 0.5) * WRAP_SLICE, radial[here], angle[here],
                                                 torso_head, torso_axis)
                    closed.append(wrapped)
                wraps[inside] = np.mean(closed) > 0.5
        return wraps

    def _has_wall(self, bone, along, radial, angle, torso_head, torso_axis):
        """Whether cloth around a point of an arm bone (``along`` it) lies between the arm and the torso."""
        head, tail = self.skeleton.heads[bone], self.skeleton.tails[bone]
        point = head + along * (tail - head) / np.linalg.norm(tail - head)
        on_torso = torso_head + ((point - torso_head) @ torso_axis) * torso_axis
        _, gap, towards = self._around(bone, on_torso[None])
        off = np.abs(np.angle(np.exp(1j * (angle - towards[0]))))
        return bool(((off < SLEEVE_WALL_CONE) & (radial < SLEEVE_WALL_SHARE * gap[0])).any())

    def _carried(self, position, bone_of, wraps, chain_bones):
        """How much of each vertex a limb carries (0 to 1), for the cloth labelled with its bones:
        all of the cloth that wraps it, and of the rest less the farther it is from the bone
        (the side of a skirt goes with the leg, the hem of a ball gown stays with the trunk)."""
        carried = np.zeros(len(position))
        near, far = FAR_CLOTH
        for bone in chain_bones:
            mine = np.flatnonzero(bone_of == bone)
            if len(mine):
                head, tail = self.skeleton.heads[bone], self.skeleton.tails[bone]
                along = np.clip((position[mine] - head) @ (tail - head) / ((tail - head) @ (tail - head)), 0.0, 1.0)
                distance = np.linalg.norm(position[mine] - (head + along[:, None] * (tail - head)), axis=1)
                carried[mine] = np.where(wraps[mine], 1.0, np.clip((far - distance) / (far - near), 0.0, 1.0))
        return carried

    def _cloth_weights(self, points, faces, bones, nearest):
        """(indices, weights) of a garment's vertices, smooth over the garment's own mesh.

        The cage part each cloth vertex was fitted on is a noisy label near the armpit and
        the hip: the outer half of a sleeve is bound to the arm and its inner half to the
        torso, so a swinging arm (it moves rigidly, independent of the torso) would open the
        sleeve like a ring; the seat of a pair of trousers is bound to the pelvis right next
        to cloth bound to a thigh, and the left half of a skirt to the left leg right next to
        the right half, so a raised leg would tear them. The labels are kept only where they
        are certain: limb cloth well down the limb and away from where the garment joins it
        to the opposite limb's, and trunk cloth away from the limbs. In between, each limb's
        share is the harmonic interpolation over the garment's own mesh, so the garment stays
        one piece. Trunk cloth away from the limbs keeps its weights.
        """
        bones = np.asarray(bones).copy()
        if not len(faces):
            return self.skeleton.weights(points, bones)
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
        bone_of = self._clean_labels(bone_of, edges)
        # A fitted label is trusted where the cloth wraps that limb. Cloth that only lies near
        # a limb belongs to the body part beside it, never an arm: the forearms and hands hang
        # next to the garments of the trunk, and only a sleeve follows them. The label of
        # the upper arm stays: a cap sleeve covers the shoulder without going round the arm.
        wraps = self._wrapping(position, bone_of, edges)
        nearest_of = np.zeros(count, dtype=np.int64)
        nearest_of[weld] = nearest
        limbs = np.isin(bone_of, [b for _, labels in self._stretches() for b in labels])
        upper_arm = np.isin(bone_of, [self.skeleton.index("UpperArm_" + side) for side in "LR"])
        piece = _components(count, edges[:, 0], edges[:, 1])
        small = np.bincount(piece, minlength=count)[piece] <= SMALL_PIECE  # rigid: one bone for the piece
        # A piece on the limbs alone is something worn on them (a glove, a sticker on the
        # forearm, a bracelet): it stays where it was fitted, wrapping the limb or not.
        worn_on_limbs = ~np.isin(piece, np.unique(piece[~limbs]))
        bone_of = np.where(limbs & ~wraps & ~upper_arm & ~small & ~worn_on_limbs, nearest_of, bone_of)
        bones = bone_of[weld]
        indices, weights = self.skeleton.weights(points, bones)
        dense = np.zeros((len(points), len(self.skeleton.names)))  # a weight per bone
        np.add.at(dense, (np.repeat(np.arange(len(points)), indices.shape[1]), indices.ravel()), weights.ravel())
        mirror = self._mirror()
        for limb_stem, trunk_name, blend in LIMB_BLENDS:
            trunk = self.skeleton.index(trunk_name)
            roots = [self.skeleton.index(limb_stem + side) for side in "LR"]
            chains = [np.isin(bone_of, self._subtree(root)) for root in roots]
            # Where the garment joins the cloth of the two limbs (the crotch seam of trousers,
            # the middle of a skirt), neither limb is certain.
            joined = np.zeros(count, dtype=bool)
            crossing = (chains[0][edges[:, 0]] & chains[1][edges[:, 1]]) | (chains[1][edges[:, 0]] & chains[0][edges[:, 1]])
            joined[edges[crossing].ravel()] = True
            joined = _within(position, edges, joined, 2 * blend)
            sides = []  # (root bone, how much it carries of its cloth, where that is certain, trunk cloth away from it)
            for root, chain in zip(roots, chains):
                if not chain.any():
                    continue
                head, tail = self.skeleton.heads[root], self.skeleton.tails[root]
                axis = (tail - head) / np.linalg.norm(tail - head)
                offset = position - head
                along = offset @ axis
                radial = np.linalg.norm(offset - along[:, None] * axis, axis=1)
                reach = 1.25 * np.percentile(radial[chain], 90)
                sure = chain & ((bone_of != root) | (along > blend)) & ~joined
                sides.append((root, chain * self._carried(position, bone_of, wraps, self._subtree(root)), sure,
                              (radial > reach) | (along < 0.0)))
            if not sides:
                continue
            # Everything the garment joins to the limbs' cloth takes part, whatever its label.
            limbs = np.any(chains, axis=0)
            involved = np.isin(piece, np.unique(piece[limbs])) | (bone_of == trunk)
            away = involved & ~limbs & np.all([far for _, _, _, far in sides], axis=0)
            certain = np.any([sure for _, _, sure, _ in sides], axis=0)
            free = involved & ~away & ~certain
            if not free.any():
                continue
            inside = involved[edges[:, 0]] & involved[edges[:, 1]]
            e0, e1 = edges[inside, 0], edges[inside, 1]
            links = np.bincount(np.concatenate([e0, e1]), minlength=count).astype(np.float64)
            solve = free & (links > 0)
            follows = []
            for _, carried, _, _ in sides:
                follow = carried.copy()
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
            joint = roots + [trunk]
            whole = np.flatnonzero((involved & ~free)[weld] & (dense[:, joint].sum(1) > 1 - 1e-9))
            dense[whole] = 0.0
            dense[whole, bones[whole]] = 1.0
            # Each limb's share of a vertex goes to the bones it already had down that limb
            # (its knee or elbow blend), or to the same bones of this limb when they were the
            # opposite limb's; what is left stays with the trunk.
            rows = np.flatnonzero((involved & ~away)[weld])
            share = follows[weld[rows]]
            before = dense[rows]
            after = np.zeros_like(before)
            for column, (root, _, _, _) in enumerate(sides):
                chain_bones = self._subtree(root)
                own = np.zeros_like(before)
                own[:, chain_bones] = before[:, chain_bones]
                other = np.zeros_like(before)
                other[:, chain_bones] = before[:, mirror[chain_bones]]
                own = np.where(own.sum(1, keepdims=True) > 0, own, other)
                own[own.sum(1) == 0, root] = 1.0
                after += own / own.sum(1, keepdims=True) * share[:, column, None]
            rest = before.copy()
            rest[:, [b for root, _, _, _ in sides for b in self._subtree(root)]] = 0.0
            rest[rest.sum(1) == 0, trunk] = 1.0
            after += rest / rest.sum(1, keepdims=True) * (1.0 - share.sum(1))[:, None]
            dense[rows] = after
        indices = np.argsort(-dense, axis=1)[:, :CLOTH_INFLUENCES]
        weights = np.take_along_axis(dense, indices, axis=1)
        return indices, weights / weights.sum(1, keepdims=True)

    def _key(self):
        return tuple(id(p.mesh) for p in self.model.parts)

    def sync(self) -> None:
        """Pose again, now, a model whose meshes changed since the last update (the skin cut again
        by a command handled after it): drawn before that, the new meshes would show for a frame
        in the pose they were built in."""
        if self._bound_key != self._key():
            self.update(0.0)

    def update(self, dt: float, walk_time=None) -> None:
        """Advance the walk by ``dt`` seconds (or to ``walk_time``, when the caller keeps the
        step) and pose the model. Starting and stopping ease in and out of the rest pose."""
        if self._bound_key != self._key():
            self._bind()  # the model was rebuilt (outfit, body or skin change)
        target = 1.0 if self.walking else 0.0
        self.stride += (target - self.stride) * min(dt * STRIDE_EASE, 1.0)
        if abs(self.stride - target) < 1e-3:
            self.stride = target
        custom = getattr(self.model, "customization", None)
        shape = (self._nose_style(), (getattr(custom, "ear_style", None), getattr(custom, "ear_color", ""))) + tuple(sorted((getattr(custom, "resolved_body_adjust", None) or getattr(custom, "body_adjust", None) or {}).items()))
        if shape != self._shape:
            self._reshape(shape)
        if self.arms_out != self._arms_shown:
            self._arms_shown, self._shown = self.arms_out, None  # the rest pose is another one now
        if self.stride == 0.0 and self._shown == "rest":
            return
        if walk_time is not None:
            self.walk_time = walk_time
        elif self.walking:
            self.walk_time += dt * WALK_SPEED
        self.show(self.pose(*self.walk_pose(self.walk_time, self.stride)))
        self._shown = "walk" if self.stride > 0.0 else "rest"

    def pose(self, rotations, root=(0.0, 0.0, 0.0)):
        """Skinning matrices of a pose, with the body's proportions (``body_shape``)."""
        root = (root[0], root[1] + self._lift * self._height, root[2])  # longer legs raise the body
        return self.skeleton.pose(rotations, root, scales=self._scales, height=self._height)

    def _nose_style(self):
        """(the style of nose chosen, whether it is in one plain colour: the computed shadow)."""
        custom = getattr(self.model, "customization", None)
        return getattr(custom, "nose_style", None), getattr(custom, "nose_shadow", "legado") == "calculada"

    def _styled_ears(self, adjust):
        """Vertex rows of the ears as the character has them now (model, adjustments, colour), on
        the bound head, when the model has ears of the same vertices (None otherwise: no ears, or
        none wanted)."""
        from . import ears
        named = {part.name: k for k, (part, *_) in enumerate(self._bindings)}
        if "ears" not in named or "head" not in named:
            return None
        custom = getattr(self.model, "customization", None)
        made = ears.rows_for(self._bound_rows[named["head"]], custom, adjust)
        if made is None or made[0].shape != self._bound_rows[named["ears"]].shape:
            return None
        return made[0] if not np.array_equal(made[0], self._bound_rows[named["ears"]]) else None

    def _styled_nose(self, style, adjust):
        """Vertex rows of the nose in ``style`` with the adjustments of its parts, on the bound
        head, when that is not the nose the model was built with and it has the same vertices
        (None otherwise)."""
        from . import nose as noses
        named = {part.name: k for k, (part, *_) in enumerate(self._bindings)}
        if style is None or style[0] is None or "nose" not in named or "head" not in named:
            return None
        if style == self._bound_nose_style and not noses.parametric(adjust):
            return None
        rows, _ = noses.styled_rows(self._bound_rows[named["head"]], style[0], adjust, plain=style[1])
        return rows if rows.shape == self._bound_rows[named["nose"]].shape else None

    def _reshape(self, shape) -> None:
        """Take the model's body adjustments: the scale of each bone, the height, and the
        fitting pose warped where an adjustment has no bone (chest, buttocks). Skin, cloth and
        hair are warped alike, from the vertices they were bound with."""
        nose_style, adjust = shape[0], dict(shape[2:])  # shape[1]: the ears' model and colour, read from the character
        self._shape = shape
        self._scales, self._height = body_shape.bone_scales(self.skeleton, adjust), body_shape.height(adjust)
        self._lift = body_shape.ground_lift(self.skeleton, self._scales)
        bulges, loose = body_shape.warps(adjust), body_shape.clearance(adjust)
        nose = body_shape.nose_adjusted(adjust)
        # The nose in another style of the same triangles is reshaped in place: only the old
        # block nose has a mesh of its own and asks for the model to be rebuilt.
        styled = self._styled_nose(nose_style, adjust)
        tinted = bool(body_shape.amount(adjust, "nariz_ponta_cor"))
        shaded = bool(body_shape.amount(adjust, "rosto_sombra"))
        # The edges of the clothes moved up or down (the hem of the top, the waist and the hem of the pants).
        edges = getattr(self.model, "garment_edges", lambda: {})() or {}
        moved = [(slot, edges[slot][which], body_shape.garment_shift(adjust, name), lower)
                 for name, (slot, which, lower) in body_shape.GARMENT_EDGES.items()
                 if slot in edges and body_shape.garment_shift(adjust, name)]
        # The ears in another style, or adjusted: every style has the same triangles, so they are moved in place.
        eared = self._styled_ears(adjust)
        warped = bulges or bool(loose) or nose or styled is not None or tinted or shaded or bool(moved) or eared is not None
        if warped or self._warped:
            surface = self._cage_binding[0]
            for k, (part, _, indices, weights) in enumerate(self._bindings):
                rows = self._bound_rows[k].copy()
                if styled is not None and part.name == "nose":
                    rows = styled.copy()
                if eared is not None and part.name == "ears":
                    rows = eared.copy()
                if nose and part.name == "nose":
                    rows[:, :3] = body_shape.nose_shape(rows[:, :3], adjust)
                for slot, edge, shift, lower in moved:
                    if part.name == slot:
                        # a top's sleeves stay on the arms: only what hangs on the body moves
                        keep = np.where(np.isin(indices, self._arms), weights, 0.0).sum(1) < 0.5 if slot == "top" else None
                        rows[:, :3] = body_shape.move_edge(rows[:, :3], edge, shift, lower, keep)
                if shaded and part.name == "head":
                    rows = body_shape.face_shading(rows, adjust)
                if tinted and part.name == "nose":
                    from .nose import tip_colours
                    rows[:, 8:11] = tip_colours(rows, adjust)
                if bulges:
                    rows[:, :3] = body_shape.warp(rows[:, :3], self.skeleton, adjust, surface)
                if loose and part.source_obj is not None and "hair" not in part.name:
                    # The clothes move off the body along their own surface (the same normal at
                    # the vertices of a texture seam, so the cloth does not open there).
                    if k not in self._cloth_normals:
                        self._cloth_normals[k] = body_shape.smooth_normals(self._bound_rows[k])
                    rows[:, :3] += loose * self._cloth_normals[k]
                self._bindings[k] = (part, rows, indices, weights)
                if getattr(part.mesh, "skinned", False):
                    part.mesh.update_vertices(rows)  # the bind pose the vertex shader starts from
            self._warped = warped
        self._shown = None

    def show(self, matrices) -> None:
        """Pose the model with one matrix per bone. Meshes that take bones and weights stay in
        their bind pose and the vertex shader poses them (``CharacterModel.draw`` sends the
        matrices); the others are posed here and written to their buffers."""
        self.model.bones = np.asarray(matrices, dtype=np.float32)
        for part, rows, indices, weights in self._bindings:
            if not getattr(part.mesh, "skinned", False):
                part.mesh.update_vertices(skin(rows, indices, weights, matrices))
