"""Roblox HSR mask decoding and skin culling."""
from pathlib import Path

import numpy as np
import pytest

from src.clothing.hsr import (HEADER_BYTES, cull_hidden_triangles, hidden_reference_vertices,
                              hsr_asset_id, load_hsr_data, subdivide)

ROOT = Path(__file__).resolve().parents[1]
CLOTHING = ROOT / "assets/models/clothing"


def test_mask_bits_are_least_significant_first_and_zero_means_hidden():
    header = bytes([0x12]) + bytes(HEADER_BYTES - 1)
    # Vertices 0..9: bits 1,0,1,1,1,1,1,1 | 0,1 -> hidden vertices 1 and 8.
    data = header + bytes([0b11111101, 0b00000010])
    hidden = hidden_reference_vertices(data, 10)
    np.testing.assert_array_equal(np.flatnonzero(hidden), [1, 8])


def test_triangle_is_culled_only_when_all_its_vertices_are_hidden_by_default():
    cage_points = np.array([[0, 0, 0], [10, 0, 0]], float)
    hidden_cage = np.array([True, False])
    positions = np.array([[0.1, 0, 0], [0.2, 0, 0], [0.3, 0, 0], [9.8, 0, 0]])
    faces = np.array([[0, 1, 2], [1, 2, 3]])
    np.testing.assert_array_equal(cull_hidden_triangles(positions, faces, cage_points, hidden_cage), [[1, 2, 3]])
    assert len(cull_hidden_triangles(positions, faces, cage_points, hidden_cage, min_hidden=2)) == 0


def test_subdivision_splits_each_triangle_in_four_and_keeps_attributes():
    vertices = np.array([[0, 0, 0, 0, 0, 1, 0, 0], [2, 0, 0, 0, 0, 1, 1, 0], [0, 2, 0, 0, 0, 1, 0, 1]], np.float32)
    rows, faces = subdivide(vertices, np.array([[0, 1, 2]]), levels=1)
    assert faces.shape == (4, 3) and len(rows) == 6
    np.testing.assert_allclose(rows[3], [1, 0, 0, 0, 0, 1, 0.5, 0])  # midpoint of the first edge, UV interpolated


def test_cached_tank_top_mask_hides_only_the_torso_region():
    rbxm = next(CLOTHING.glob("*_137915688957785.rbxm"))
    hsr_id = hsr_asset_id(rbxm)
    if not (CLOTHING / "hsr" / f"{hsr_id}.bin").exists():
        return  # needs the downloaded HSR asset
    hidden = hidden_reference_vertices(load_hsr_data(hsr_id, CLOTHING / "hsr"), 4881)
    assert 200 < hidden.sum() < 400


def test_older_hsr_layouts_are_rejected_instead_of_misread():
    import pytest
    with pytest.raises(ValueError):
        hidden_reference_vertices(bytes([0x11]) + bytes(HEADER_BYTES - 1) + bytes(2), 10)


def test_geometric_mask_covers_cage_points_with_garment_just_outside():
    from src.clothing.hsr import geometric_hidden_mask
    # A unit octahedron "body cage"; the garment is a patch just outside the +x tip.
    cage = np.array([(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)], float)
    faces = np.array([(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)])
    garment = np.array([(1.05, 0.0, 0.0), (1.05, 0.02, 0.0)])
    hidden = geometric_hidden_mask(cage, faces, garment)
    np.testing.assert_array_equal(np.flatnonzero(hidden), [0])


def test_ray_mask_sees_skin_through_a_slit_between_garment_pieces():
    from src.clothing.hsr import ray_hidden_mask
    cage = np.array([(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)], float)
    faces = np.array([(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)])
    # Two garment panels in front of the +y tip with a slit where its outward ray passes,
    # and one panel covering the +x tip.
    left = [(-0.4, 1.05, -0.3), (-0.05, 1.05, -0.3), (-0.05, 1.05, 0.3), (-0.4, 1.05, 0.3)]
    right = [(0.05, 1.05, -0.3), (0.4, 1.05, -0.3), (0.4, 1.05, 0.3), (0.05, 1.05, 0.3)]
    front = [(1.05, -0.3, -0.3), (1.05, 0.3, -0.3), (1.05, 0.3, 0.3), (1.05, -0.3, 0.3)]
    garment = np.array(left + right + front, float)
    quads = [(0, 1, 2), (0, 2, 3)]
    garment_faces = np.array([(a + o, b + o, c + o) for o in (0, 4, 8) for a, b, c in quads])
    hidden = ray_hidden_mask(cage, faces, garment, garment_faces)
    assert hidden[0] and not hidden[2]


def test_ray_mask_hides_a_lone_point_seen_through_a_tiny_gap():
    from src.clothing.hsr import _hide_isolated_visible
    # A 5x5 grid of cage points: one lone visible point, and a visible column (a zip slit).
    xs, ys = np.meshgrid(np.arange(5.0), np.arange(5.0))
    points = np.column_stack((xs.ravel(), ys.ravel(), np.zeros(25)))
    faces = [(r * 5 + c, r * 5 + c + 1, r * 5 + c + 5) for r in range(4) for c in range(4)]
    faces += [(r * 5 + c + 1, r * 5 + c + 6, r * 5 + c + 5) for r in range(4) for c in range(4)]
    hidden = np.ones(25, dtype=bool)
    hidden[[2, 7, 12, 17, 22]] = False  # the slit column x=2
    hidden[5 + 0] = False  # a lone point at the left edge
    hidden = _hide_isolated_visible(hidden, points, np.array(faces))
    np.testing.assert_array_equal(np.flatnonzero(~hidden), [2, 7, 12, 17, 22])


def test_wrapped_limbs_cover_the_armpit_only_under_sleeves():
    """A sweater closes the open armpit border of the arm cage; a sleeveless jersey does not."""
    import os
    from src.clothing.character_model import MODELS_DIR
    from src.clothing.hsr import close_wrapped_limbs, sidecar_path
    from src.clothing.wear_engine import BODY_CAGES, load_r15_cages
    from src.clothing.wrap_layer_fit import _unique_uv_positions, body_uv_parts

    cases = {"9240757332": True, "97346273111638": False}  # sweater, basketball jersey
    paths = {top: os.path.join(MODELS_DIR, f"character_native_{top}_male.obj") for top in cases}
    if not all(os.path.exists(sidecar_path(p)) for p in paths.values()):
        pytest.skip("roupas encaixadas não geradas")
    parts = np.array(body_uv_parts(load_r15_cages(os.path.join(MODELS_DIR, BODY_CAGES["male"]))))
    arms = np.isin(parts, ["LeftUpperArm", "RightUpperArm"])
    for top, sleeved in cases.items():
        hidden = np.load(sidecar_path(paths[top]))["hidden"].astype(bool)
        closed = close_wrapped_limbs(hidden, "male", paths[top])
        assert (closed | ~hidden).all()  # only ever adds cover
        assert ((closed & ~hidden & arms).any()) == sleeved
