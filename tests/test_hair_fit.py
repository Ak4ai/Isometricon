"""Head accessories: attachment placement and the fit onto each body's head."""
from pathlib import Path

import numpy as np
import pytest

from src.clothing.hair_fit import HEAD_ATTACHMENTS, accessory_placement, fit_head_accessory, head_map
from src.clothing.hsr import engine_to_body_mesh
from src.clothing.wear_engine import BODY_CAGES, load_r15_cages

ROOT = Path(__file__).resolve().parents[1]
HAIR = next((ROOT / "assets/models/clothing").glob("Wavy_Popstar_Hair_in_Brown_121967101597958.rbxm"), None)


@pytest.mark.skipif(HAIR is None, reason="asset de cabelo não baixado")
def test_hair_attachment_is_read_by_name():
    scale, offset, name, rotation, position = accessory_placement(HAIR)
    assert name == "HairAttachment" and name in HEAD_ATTACHMENTS
    np.testing.assert_allclose(scale, 1.0)
    np.testing.assert_allclose(position, [0.0, 1.201, -0.256], atol=1e-3)
    np.testing.assert_allclose(rotation @ rotation.T, np.eye(3), atol=1e-5)


@pytest.mark.skipif(HAIR is None, reason="asset de cabelo não baixado")
@pytest.mark.parametrize("body", sorted(BODY_CAGES))
def test_hair_sits_on_each_body_head(body):
    obj = HAIR.with_suffix(".obj")
    vertices = np.array([list(map(float, l.split()[1:4])) for l in open(obj) if l.startswith("v ")])
    source = load_r15_cages(str(ROOT / "assets/models/roblox_reference_cages.obj"), is_source_cage=True)
    cages = load_r15_cages(str(ROOT / "assets/models" / BODY_CAGES[body]))
    hair = engine_to_body_mesh(fit_head_accessory(vertices, HAIR, source, cages))
    head = engine_to_body_mesh(cages["Head"]["verts"])
    # Centred on the head, covering its top, and facing the same way (bangs in front).
    assert abs(np.median(hair[:, 0]) - np.median(head[:, 0])) < 0.02
    assert hair[:, 1].max() > head[:, 1].max()
    assert hair[:, 1].max() - head[:, 1].max() < 0.12  # the hair's own volume above the head
    # Long hair hangs behind the face, not in front of it.
    centre = (head.min(0) + head.max(0)) / 2
    below = hair[hair[:, 1] < head[:, 1].min()]
    assert below[:, 2].mean() < centre[2]


@pytest.mark.parametrize("body", sorted(BODY_CAGES))
def test_roblox_head_landmarks_land_on_our_head(body):
    source = load_r15_cages(str(ROOT / "assets/models/roblox_reference_cages.obj"), is_source_cage=True)
    cages = load_r15_cages(str(ROOT / "assets/models" / BODY_CAGES[body]))
    reference_head = source["Head"]["verts"]
    centre = (reference_head.min(0) + reference_head.max(0)) / 2
    # Roblox head-local top, front (-Z) and right (+X), as fit_head_accessory places them.
    local = np.array([[0.0, 0.6, 0.0], [0.0, 0.0, -0.6], [0.6, 0.0, 0.0]])
    mapped = engine_to_body_mesh(head_map(source, cages)(np.c_[-local[:, 0], -local[:, 2], local[:, 1]] + centre))
    head = engine_to_body_mesh(cages["Head"]["verts"])
    top, front, right = mapped
    assert abs(top[1] - head[:, 1].max()) < 0.015
    assert abs(front[2] - head[:, 2].max()) < 0.02
    assert abs(right[0] - head[:, 0].min()) < 0.015  # the character's right is -x in our meshes
