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


def _square(z: float, half: float = 0.5) -> np.ndarray:
    """Two triangles of cloth: a square across the z axis at this height."""
    a, b, c, d = [-half, -half, z], [half, -half, z], [half, half, z], [-half, half, z]
    return np.array([[a, b, c], [a, c, d]], dtype=np.float64)


def test_the_cloth_is_measured_in_front_of_the_skin_and_found_behind_it():
    from src.clothing.hsr import CLOTH_REACH, CLOTH_SUNK, cloth_behind, cloth_distance
    points = np.array([[0.0, 0.0, 0.0], [0.1, 0.1, 0.0], [2.0, 0.0, 0.0]])
    up = np.tile([0.0, 0.0, 1.0], (3, 1))
    ahead = cloth_distance(points, up, _square(0.03))
    assert np.allclose(ahead[:2], 0.03, atol=1e-6) and np.isinf(ahead[2])                 # 3 cm over the skin; none beside it
    assert np.allclose(cloth_distance(points, up, _square(-0.01))[:2], -0.01, atol=1e-6)  # the cloth 1 cm into the skin
    assert np.isinf(cloth_distance(points, up, _square(CLOTH_REACH + 0.05))).all()        # too far to be over it
    assert cloth_behind(points, up, _square(-0.04)).tolist() == [True, True, False]       # sunk into the body
    assert not cloth_behind(points, up, _square(-CLOTH_SUNK - 0.02)).any()
    assert not cloth_behind(points, up, _square(0.03)).any()                              # in front is not behind


def test_the_skin_is_cut_along_the_line_of_the_mask():
    from src.clothing.hsr import clip_hidden
    # A strip of two triangles along x, attributes of 11 numbers; the mask grows with x.
    rows = np.zeros((4, 11), dtype=np.float32)
    rows[:, :3] = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
    rows[:, 5] = 1.0
    rows[:, 6] = rows[:, 0]                                # u follows x
    faces = np.array([[0, 1, 2], [0, 2, 3]])
    share = np.array([0.0, 1.0, 1.0, 0.0])
    cut_rows, cut_faces = clip_hidden(rows, faces, share, 0.5)
    used = cut_rows[np.unique(cut_faces)]
    assert used[:, 0].max() == pytest.approx(0.5) and len(cut_rows) > len(rows)            # cut at the line, not at a triangle's edge
    assert np.allclose(used[:, 6], used[:, 0]) and np.allclose(np.linalg.norm(used[:, 3:6], axis=1), 1.0)   # attributes follow
    area = lambda r, f: sum(np.linalg.norm(np.cross(r[b, :3] - r[a, :3], r[c, :3] - r[a, :3])) / 2 for a, b, c in f)
    assert area(cut_rows, cut_faces) == pytest.approx(0.5)                                 # half the strip is kept
    normal = lambda r, f: np.cross(r[f[1], :3] - r[f[0], :3], r[f[2], :3] - r[f[0], :3])[2]
    assert all(normal(cut_rows, f) > 0 for f in cut_faces)                                 # facing as they did
    # Nothing to cut, and all of it cut.
    assert len(clip_hidden(rows, faces, np.zeros(4), 0.5)[1]) == 2 and len(clip_hidden(rows, faces, np.ones(4), 0.5)[1]) == 0


def test_a_triangle_is_only_cut_where_the_cloth_covers_what_it_loses():
    from src.clothing.hsr import clip_hidden
    rows = np.zeros((4, 11), dtype=np.float32)
    rows[:, :3] = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
    faces = np.array([[0, 1, 2], [0, 2, 3]])
    share = np.array([0.0, 1.0, 1.0, 0.0])
    # Vertex 1 is hidden by the mask but no cloth is over it: its triangle stays whole (it would be a hole);
    # the other, whose lost corner is covered, is cut.
    cut_rows, cut_faces = clip_hidden(rows, faces, share, 0.5, covered=np.array([True, False, True, True]))
    assert [0, 1, 2] in cut_faces.tolist()
    assert not any(set(f) == {0, 2, 3} for f in cut_faces.tolist()) and len(cut_rows) > len(rows)


def test_the_middle_of_a_fan_stays_one_point_after_the_fit():
    from src.clothing.wear_engine import FAN_COPIES, keep_together
    # A fan that closes an armhole: FAN_COPIES copies of its middle, a ring about them, and a seam of two copies.
    ring = [[np.cos(a), np.sin(a), 0.0] for a in np.linspace(0, 2 * np.pi, FAN_COPIES, endpoint=False)]
    source = np.array([[0.0, 0.0, 0.0]] * FAN_COPIES + ring + [[2.0, 0.0, 0.0]] * 2)
    fitted = source.copy()
    fitted[:FAN_COPIES] = np.array(ring) * 0.3 + [0.0, 0.0, 0.05]         # the fit sent each copy its own way
    fitted[-1] += [0.0, 0.04, 0.0]                                         # and parted the seam
    together = keep_together(source, fitted)
    middle = together[:FAN_COPIES]
    assert np.allclose(middle, middle[0]) and np.allclose(middle[0], fitted[:FAN_COPIES].mean(0))   # one point again: where they were sent, on average
    assert np.array_equal(together[FAN_COPIES:], fitted[FAN_COPIES:])      # the ring and the seam are left as the fit put them
    assert np.array_equal(keep_together(source, together), together)       # done once, nothing more to do
    assert np.array_equal(keep_together(source[:3], fitted), fitted)       # not the same mesh: left alone
