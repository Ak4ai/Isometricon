"""Place a rigid Roblox head accessory (hair, hat) on our head.

1. The accessory's Handle is placed as Roblox places it: its attachment (HairAttachment,
   HatAttachment...) meets the attachment of the same name on the R15 head. That puts
   the mesh on the Roblox reference head, in the frame of roblox_reference_cages.obj.
2. From the Roblox head to ours through the head cages, paired by UV: one affine map
   for the whole accessory plus the cage's local residual, interpolated smoothly from
   the nearest cage points, so bangs and caps follow our head's shape instead of a
   single scale calibrated on one hair.
"""
from __future__ import annotations

import numpy as np

from .rbxm import read_rbxm

# Attachments of the R15 head (studs, head-local, Roblox axes: +Y up, -Z front), head size 1.2.
HEAD_ATTACHMENTS = {
    "HairAttachment": (0.0, 0.6, 0.0),
    "HatAttachment": (0.0, 0.6, 0.0),
    "FaceFrontAttachment": (0.0, 0.0, -0.6),
    "FaceCenterAttachment": (0.0, 0.0, 0.0),
}
# Distance (m) over which a cage point's residual dominates the interpolation.
RESIDUAL_RADIUS = 0.03


def accessory_placement(rbxm_path):
    """(mesh scale, mesh offset, attachment name, rotation, position) of the accessory's Handle."""
    instances = read_rbxm(rbxm_path)
    handle = next((i for i in instances if i.name == "Handle" and i.class_name in ("Part", "MeshPart")), None)
    if handle is None:
        raise ValueError("Acessório sem Handle")
    attachment = next((c for c in handle.children if c.class_name == "Attachment" and c.name in HEAD_ATTACHMENTS), None)
    if attachment is None:
        raise ValueError(f"Handle sem attachment de cabeça: {[c.name for c in handle.children]}")
    scale, offset = np.ones(3), np.zeros(3)
    mesh = next((c for c in handle.children if c.class_name == "SpecialMesh"), None)
    if mesh is not None:
        scale = np.asarray(mesh.properties.get("Scale", scale), dtype=np.float64)
        offset = np.asarray(mesh.properties.get("Offset", offset), dtype=np.float64)
    elif handle.class_name == "MeshPart" and "InitialSize" in handle.properties:
        scale = np.asarray(handle.properties["size"], dtype=np.float64) / np.asarray(handle.properties["InitialSize"])
    rotation, position = attachment.properties["CFrame"]
    return scale, offset, attachment.name, rotation, position


def _head_points(cages):
    from .wrap_layer_fit import _unique_uv_positions
    return _unique_uv_positions({"Head": cages["Head"]})


def head_map(source_cages, body_cages):
    """Maps engine points around the Roblox reference head onto the same places around ours."""
    source_uv, source = _head_points(source_cages)
    body_uv, body = _head_points(body_cages)
    pair = np.array([np.abs(body_uv - uv).max(1).argmin() for uv in source_uv])
    target = body[pair]
    homogeneous = np.c_[source, np.ones(len(source))]
    affine, *_ = np.linalg.lstsq(homogeneous, target, rcond=None)
    residual = target - homogeneous @ affine
    anchors = homogeneous @ affine  # the cage points where each residual applies, after the affine map

    def apply(points):
        mapped = np.c_[points, np.ones(len(points))] @ affine
        distance = np.linalg.norm(mapped[:, None] - anchors[None], axis=2)
        weight = 1.0 / (distance ** 2 + RESIDUAL_RADIUS ** 2) ** 2
        return mapped + (weight @ residual) / weight.sum(1, keepdims=True)
    return apply


def fit_head_accessory(mesh_vertices, rbxm_path, source_cages, body_cages):
    """Accessory mesh vertices (studs, Handle mesh space) in engine coordinates on our head."""
    scale, offset, name, rotation, position = accessory_placement(rbxm_path)
    handle = np.asarray(mesh_vertices, dtype=np.float64) * scale + offset
    # Handle -> attachment frame -> head-local: the two attachments coincide.
    head_local = (handle - position) @ rotation + np.asarray(HEAD_ATTACHMENTS[name])
    # Roblox head-local -> reference cage engine frame, the head centred in its cage. The
    # reference cages face +depth and have the character's left at +x, so Roblox's
    # -Z front and +X right both flip (a half turn about the vertical, no mirroring).
    head = source_cages["Head"]["verts"]
    centre = (head.min(0) + head.max(0)) / 2.0
    reference = np.c_[-head_local[:, 0], -head_local[:, 2], head_local[:, 1]] + centre
    return head_map(source_cages, body_cages)(reference)
