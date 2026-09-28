"""Tests for asset-specific cage metadata, legacy meshes, and local frames."""
from pathlib import Path
import struct
from types import SimpleNamespace

import numpy as np

from scripts.import_roblox_clothing import decode_roblox_mesh_to_obj
from scripts.experimental_wrap_frames import affine_map
from src.clothing.wrap_layer_fit import (
    _cage_edge_stretch, _local_map, _match_outer_to_reference, _match_reference_to_body_uv,
    _signed_surface_volume, read_wrap_layer,
    retarget_garment_with_wrap_layer,
)


ROOT = Path(__file__).resolve().parents[1]


def test_reads_wrap_mesh_ids_and_asset_specific_origins():
    office = read_wrap_layer(ROOT / "assets/models/clothing/-_office_shirt__BLACK_133331049150205.rbxm")
    sweater = read_wrap_layer(ROOT / "assets/models/clothing/Oversized_Knitted_Sweater_w_Bow__White_16185652164.rbxm")

    assert office["reference_id"] == "80307990380242"
    assert office["cage_id"] == "78642992491592"
    assert sweater["reference_id"] == "16184891193"
    assert sweater["cage_id"] == "16184891237"
    np.testing.assert_allclose(office["cage_origin"][1][1], -1.0893752575, atol=1e-7)
    np.testing.assert_allclose(sweater["cage_origin"][1][1], -0.2269, atol=1e-3)


def test_filemesh_v2_decodes_positions_uvs_and_faces():
    positions = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    header = b"version 2.00\n" + struct.pack("<HBBII", 12, 40, 12, 3, 1)
    vertices = b"".join(struct.pack("<8f", *p, 0, 0, 1, p[0], p[1]) + bytes(8)
                        for p in positions)
    payload = header + vertices + struct.pack("<3I", 0, 1, 2)
    output = ROOT / "artifacts/clothing_audit/filemesh_v2_fixture.obj"
    decode_roblox_mesh_to_obj(payload, str(output))
    content = output.read_text(encoding="utf-8")
    assert "v 1.000000000 0.000000000 0.000000000" in content
    assert "vt 0.000000000 1.000000000" in content
    assert "f 1/1 2/2 3/3" in content


def test_local_frame_rotates_garment_volume_with_target_triangle():
    a, b, c = [np.asarray(p, dtype=float) for p in ((0, 0, 0), (1, 0, 0), (0, 1, 0))]
    rotation = np.asarray([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)
    transform = _local_map(a, b, c, 0.5 * rotation @ a, 0.5 * rotation @ b, 0.5 * rotation @ c)
    np.testing.assert_allclose(transform @ np.asarray([0.2, 0.1, 0.3]),
                               0.5 * rotation @ np.asarray([0.2, 0.1, 0.3]), atol=1e-8)


def test_experimental_affine_frame_is_invariant_to_cyclic_triangle_corner_order():
    """The candidate map is independent of a triangle's starting corner."""
    source = np.asarray([[0., 0., 0.], [1., 0., 0.], [.2, 1., 0.]])
    target = np.asarray([[0., 0., 0.], [1., 0., 0.], [.7, 1., 0.]])
    maps = [affine_map(*np.roll(source, i, axis=0),
                       *np.roll(target, i, axis=0)) for i in range(3)]
    for matrix in maps:
        np.testing.assert_allclose(matrix, [[1., .5, 0.], [0., 1., 0.], [0., 0., 1.]], atol=1e-8)


def test_local_frame_can_retarget_a_reflected_cage_without_inverting_shell_offset():
    source = np.asarray([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]])
    reflection = np.diag([1., -1., 1.])
    target = source @ reflection.T
    reflected = _local_map(*source, *target, normal_sign=-1)
    np.testing.assert_allclose(reflected @ np.asarray([.2, .3, .4]),
                               reflection @ np.asarray([.2, .3, .4]), atol=1e-8)


def test_signed_cage_volume_reveals_reflected_coordinate_frame():
    vertices = np.asarray([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.], [0., 0., 1.]])
    faces = np.asarray([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])
    original = _signed_surface_volume(vertices, faces)
    mirrored = _signed_surface_volume(vertices * [1, -1, 1], faces)
    assert original > 0
    np.testing.assert_allclose(mirrored, -original)


def test_entire_wrap_preserves_garment_when_target_frame_is_reflected():
    """A coordinate reflection must preserve the garment's signed shell offset."""
    from src.clothing.wear_engine import RobloxWearEngine
    directory = ROOT / "assets/models/clothing"
    rbxm = directory / "-_office_shirt__BLACK_133331049150205.rbxm"
    wrap = read_wrap_layer(rbxm)
    load = lambda path: RobloxWearEngine.load_obj(None, str(path))
    reference, faces, uv, face_uv = load(directory / "wrap_cages" / (wrap["reference_id"] + ".obj"))
    garment, _, _, _ = load(directory / "-_office_shirt__BLACK_133331049150205.obj")
    rotation, translation = wrap["reference_origin"]
    reflection = np.diag([1., -1., 1.])
    parent = reference @ rotation.T + translation
    engine = SimpleNamespace(load_obj=load, r15_female_cages={"Control": {
        "verts": parent @ reflection.T, "faces": faces, "face_uvs": uv[face_uv]}})
    result, _ = retarget_garment_with_wrap_layer(engine, garment, str(rbxm), directory / "wrap_cages")
    np.testing.assert_allclose(result, garment @ reflection.T, atol=1e-6)


def test_cage_edge_stretch_detects_a_bad_shell_transfer():
    source = np.asarray([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]])
    target = source.copy()
    target[1, 0] = 4.
    p99, count = _cage_edge_stretch(source, target, np.asarray([[0, 1, 2]]))
    assert p99 > 3
    assert count >= 1


def test_reference_uv_allows_few_unambiguous_template_edits():
    body = np.asarray([[0., 0.], [1., 0.], [0., 1.]])
    reference = np.asarray([[0.008, 0.], [1., 0.]])
    np.testing.assert_array_equal(_match_reference_to_body_uv(reference, body), [0, 1])


def test_reference_uv_rejects_colliding_template_edits():
    body = np.asarray([[0., 0.], [1., 0.]])
    reference = np.asarray([[0., 0.], [0.004, 0.]])
    import pytest
    with pytest.raises(ValueError, match="ambígua"):
        _match_reference_to_body_uv(reference, body)


def _uv_grid(size=12):
    uvs = np.array([(i / size, j / size) for j in range(size + 1) for i in range(size + 1)])
    faces = []
    for j in range(size):
        for i in range(size):
            a = j * (size + 1) + i
            faces += [(a, a + 1, a + size + 2), (a, a + size + 2, a + size + 1)]
    return uvs, np.array(faces)


def test_outer_cage_pairing_resolves_edited_uvs_by_connectivity():
    reference_uv, reference_faces = _uv_grid()
    order = np.random.default_rng(3).permutation(len(reference_uv))
    outer_uv = reference_uv[order].copy()
    inverse = np.argsort(order)
    outer_faces = inverse[reference_faces]
    # Two interior outer UVs moved so each lands nearer the other's reference UV.
    a, b = inverse[5 * 13 + 5], inverse[5 * 13 + 6]
    outer_uv[a] += (0.12, 0.0)
    outer_uv[b] -= (0.12, 0.0)

    paired = _match_outer_to_reference(reference_uv, reference_faces, outer_uv, outer_faces)

    np.testing.assert_array_equal(paired, inverse)


def test_outer_cage_pairing_leaves_points_the_author_deleted_unpaired():
    reference_uv, reference_faces = _uv_grid()
    keep = np.ones(len(reference_uv), bool)
    keep[5 * 13 + 5] = False  # the outer cage lost one interior point
    remap = np.cumsum(keep) - 1
    outer_uv = reference_uv[keep]
    outer_faces = remap[reference_faces[keep[reference_faces].all(1)]]

    paired = _match_outer_to_reference(reference_uv, reference_faces, outer_uv, outer_faces)

    assert paired[5 * 13 + 5] == -1
    np.testing.assert_array_equal(paired[keep], np.arange(keep.sum()))


def test_reference_uv_precision_noise_counts_as_the_same_body_point():
    body_uv, _ = _uv_grid()
    noise = np.random.default_rng(1).uniform(-4e-4, 4e-4, body_uv.shape)
    # The same corner stored twice with different noise, as catalog cages do.
    reference = np.vstack((body_uv + noise, body_uv[:1] - noise[:1]))
    np.testing.assert_array_equal(_match_reference_to_body_uv(reference, body_uv),
                                  list(range(len(body_uv))) + [0])


def test_reference_uv_moved_far_by_the_author_is_paired_by_connectivity():
    from src.clothing.wrap_layer_fit import _match_reference_to_body_uv
    body_uv, faces = _uv_grid()
    adjacency = [set() for _ in body_uv]
    for a, b, c in faces:
        adjacency[a].update((b, c))
        adjacency[b].update((a, c))
        adjacency[c].update((a, b))
    moved = 6 * 13 + 6
    reference = body_uv.copy()
    reference[moved] += (0.05, 0.03)  # far beyond any tolerance, closer to another point
    np.testing.assert_array_equal(_match_reference_to_body_uv(reference, body_uv, faces, adjacency),
                                  np.arange(len(body_uv)))


def test_outer_cage_missing_a_large_region_is_still_paired():
    reference_uv, reference_faces = _uv_grid()
    keep = reference_uv[:, 0] < 0.75  # the outer cage lost a quarter of the points
    remap = np.cumsum(keep) - 1
    outer_uv = reference_uv[keep]
    outer_faces = remap[reference_faces[keep[reference_faces].all(1)]]
    paired = _match_outer_to_reference(reference_uv, reference_faces, outer_uv, outer_faces)
    np.testing.assert_array_equal(paired[keep], np.arange(keep.sum()))
    assert (paired[~keep] == -1).all()
