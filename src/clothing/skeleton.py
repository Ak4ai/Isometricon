"""Game skeleton: the 16-bone rig of each body, bone weights and linear blend skinning.

The rig (assets/models/rig_<body>.json, exported from Blender by scripts/export_rig.py) is in
the A-pose the body and the fitted garments are in, so that pose is the bind pose: a bone's
skinning matrix is simply its posed transform.

Weights: every vertex follows one bone (its body part), except near a joint, where it blends
with the other bone of the joint. The blend only depends on the vertex position and the
child bone's axis, so the two sides of a seam (a thigh and its shin, a shirt and its sleeve)
get the same weights and stay joined when the joint bends.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

import numpy as np

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                          "assets", "models")
# Half the length over which a joint blends its two bones (m).
BLEND_RADIUS = 0.035
# Body cage parts (R15) -> bones.
CAGE_PART_BONES = {
    "Head": "Head", "UpperTorso": "Torso", "LowerTorso": "Pelvis",
    "LeftUpperArm": "UpperArm_L", "LeftLowerArm": "LowerArm_L", "LeftHand": "Hand_L",
    "RightUpperArm": "UpperArm_R", "RightLowerArm": "LowerArm_R", "RightHand": "Hand_R",
    "LeftUpperLeg": "UpperLeg_L", "LeftLowerLeg": "LowerLeg_L", "LeftFoot": "Foot_L",
    "RightUpperLeg": "UpperLeg_R", "RightLowerLeg": "LowerLeg_R", "RightFoot": "Foot_R",
}


@dataclass
class Skeleton:
    names: list
    parents: np.ndarray  # index of the parent bone, -1 for the root
    heads: np.ndarray  # (B, 3) joint positions, mesh coordinates (x, y up, z front)
    tails: np.ndarray

    @classmethod
    def load(cls, body: str) -> "Skeleton":
        with open(os.path.join(MODELS_DIR, f"rig_{body}.json"), encoding="utf-8") as fp:
            bones = json.load(fp)["bones"]
        names = [b["name"] for b in bones]
        parents = np.array([names.index(b["parent"]) if b["parent"] else -1 for b in bones])
        return cls(names, parents, np.array([b["head"] for b in bones], dtype=np.float64),
                   np.array([b["tail"] for b in bones], dtype=np.float64))

    def index(self, name: str) -> int:
        return self.names.index(name)

    def weights(self, points: np.ndarray, bones: np.ndarray, blend: float = BLEND_RADIUS):
        """(indices, weights), each (N, 2): the vertex's bone and the other bone of a nearby joint.

        ``bones`` is each vertex's own bone. Near the joint between a bone and one of its
        children, the child's weight rises smoothly along the child's axis, from 0 at
        ``blend`` before the joint to 1 at ``blend`` after it.
        """
        points = np.asarray(points, dtype=np.float64)
        bones = np.asarray(bones)
        indices = np.stack([bones, bones], axis=1)
        weights = np.zeros((len(points), 2))
        weights[:, 0] = 1.0
        axes = self.tails - self.heads
        lengths = np.linalg.norm(axes, axis=1)
        axes = axes / lengths[:, None]
        for child in range(len(self.names)):
            parent = self.parents[child]
            if parent < 0:
                continue
            # Only vertices of the two bones of this joint, and only across the child's
            # section (the thigh's width, not the whole pelvis).
            mine = (bones == child) | (bones == parent)
            if not mine.any():
                continue
            offset = points - self.heads[child]
            along = offset @ axes[child]
            radial = np.linalg.norm(offset - along[:, None] * axes[child], axis=1)
            own = points[bones == child]
            if len(own):
                own_radial = np.linalg.norm((own - self.heads[child]) - ((own - self.heads[child]) @ axes[child])[:, None]
                                            * axes[child], axis=1)
                reach = 1.25 * np.percentile(own_radial, 90)
            else:
                reach = 0.1
            near = mine & (np.abs(along) < blend) & (radial < reach)
            t = np.clip((along[near] + blend) / (2 * blend), 0.0, 1.0)
            t = t * t * (3 - 2 * t)
            rows = np.flatnonzero(near)
            indices[rows] = np.stack([np.full(len(rows), child), np.full(len(rows), parent)], axis=1)
            weights[rows] = np.stack([t, 1 - t], axis=1)
        return indices, weights

    def pose(self, rotations: dict, root_offset=(0.0, 0.0, 0.0)) -> np.ndarray:
        """(B, 4, 4) skinning matrices: each bone turned about its joint by ``rotations[name]``
        (3x3, in the mesh axes), children carried by their parents."""
        matrices = np.zeros((len(self.names), 4, 4))
        for bone in range(len(self.names)):  # parents come first
            local = np.eye(4)
            rotation = rotations.get(self.names[bone])
            if rotation is not None:
                pivot = self.heads[bone]
                local[:3, :3] = rotation
                local[:3, 3] = pivot - rotation @ pivot
            parent = self.parents[bone]
            if parent < 0:
                root = np.eye(4)
                root[:3, 3] = root_offset
                matrices[bone] = root @ local
            else:
                matrices[bone] = matrices[parent] @ local
        return matrices


def rotation_x(angle: float) -> np.ndarray:
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rotation_y(angle: float) -> np.ndarray:
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rotation_z(angle: float) -> np.ndarray:
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


# Angle between each arm and the vertical in the rest pose (the bodies are exported in A-pose).
REST_ARM_ANGLE = np.radians(5.0)


def rest_rotations(skeleton: "Skeleton", arm_angle: float = REST_ARM_ANGLE) -> dict:
    """Rotations from the A-pose to the game's rest pose: arms hanging close to the body.

    Each upper arm turns about the front axis at the shoulder until it is ``arm_angle`` off
    the vertical; the forearm then straightens in line with it (the hand follows).
    """
    rotations = {}
    for side, sign in (("L", 1.0), ("R", -1.0)):
        upper, lower = skeleton.index(f"UpperArm_{side}"), skeleton.index(f"LowerArm_{side}")
        angle = lambda b: np.arctan2(sign * (skeleton.tails[b, 0] - skeleton.heads[b, 0]),
                                     skeleton.heads[b, 1] - skeleton.tails[b, 1])
        turn = arm_angle - angle(upper)
        rotations[f"UpperArm_{side}"] = rotation_z(sign * turn)
        rotations[f"LowerArm_{side}"] = rotation_z(sign * (arm_angle - angle(lower) - turn))
    return rotations


def walk_rotations(walk_time: float):
    """Bone rotations and root offset of the game's walk cycle (the one of the world token)."""
    from src.interactive.token_system import walk_pose
    pose = walk_pose(walk_time)
    rotations = {
        "UpperLeg_L": rotation_x(pose["hip_L"]), "LowerLeg_L": rotation_x(pose["knee_L"]),
        "Foot_L": rotation_x(pose["foot_L"]),
        "UpperLeg_R": rotation_x(pose["hip_R"]), "LowerLeg_R": rotation_x(pose["knee_R"]),
        "Foot_R": rotation_x(pose["foot_R"]),
        "UpperArm_L": rotation_x(pose["arm_L"]), "LowerArm_L": rotation_x(pose["forearm_L"]),
        "UpperArm_R": rotation_x(pose["arm_R"]), "LowerArm_R": rotation_x(pose["forearm_R"]),
        "Torso": rotation_y(pose["torso_yaw"]), "Head": rotation_x(pose["head_pitch"]),
    }
    return rotations, (0.0, pose["bounce"], 0.0)


def skin(rows: np.ndarray, indices: np.ndarray, weights: np.ndarray, matrices: np.ndarray) -> np.ndarray:
    """Vertex rows (x, y, z, nx, ny, nz, ...) moved by linear blend skinning."""
    blended = np.einsum("nk,nkij->nij", weights, matrices[indices])
    out = rows.copy()
    out[:, :3] = np.einsum("nij,nj->ni", blended[:, :3, :3], rows[:, :3]) + blended[:, :3, 3]
    normals = np.einsum("nij,nj->ni", blended[:, :3, :3], rows[:, 3:6])
    length = np.linalg.norm(normals, axis=1, keepdims=True)
    out[:, 3:6] = normals / np.where(length > 1e-8, length, 1.0)
    return out
