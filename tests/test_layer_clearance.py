"""Inner garments pulled under the outer one where they overlap."""
import numpy as np

from src.clothing.layer_clearance import fitted_asset_type, layer_top_and_bottom, pull_inner_layer


def _cylinder(radius, low, high, segments=32, rows=6):
    angles = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    heights = np.linspace(low, high, rows)
    points = np.array([(radius * np.cos(a), h, radius * np.sin(a)) for h in heights for a in angles])
    faces = []
    for r in range(rows - 1):
        for s in range(segments):
            a, b = r * segments + s, r * segments + (s + 1) % segments
            faces += [(a, b, a + segments), (b, b + segments, a + segments)]
    return points, np.array(faces)


def test_a_waistband_poking_through_the_hem_is_pulled_inside():
    outer, faces = _cylinder(0.20, 0.8, 1.2)
    inner, _ = _cylinder(0.195, 0.5, 0.9)
    inner[inner[:, 1] > 0.85, 0] *= 1.04  # a bulge 2 mm outside the top, on one side
    pulled = pull_inner_layer(inner, outer, faces)
    covered = pulled[:, 1] >= 0.8
    radius = np.hypot(pulled[covered, 0], pulled[covered, 2])
    assert radius.max() <= 0.20 - 0.004 + 1e-3
    np.testing.assert_array_equal(pulled[~covered], inner[~covered])  # legs below the hem untouched


def test_a_jacket_stays_outside_even_when_the_pants_mostly_poke_through():
    top, top_faces = _cylinder(0.20, 0.8, 1.2)
    pants, pants_faces = _cylinder(0.21, 0.5, 0.9)
    new_top, new_pants = layer_top_and_bottom(top, top_faces, pants, pants_faces, top_type=67)
    np.testing.assert_array_equal(new_top, top)
    covered = new_pants[:, 1] >= 0.8
    assert np.hypot(new_pants[covered, 0], new_pants[covered, 2]).max() < 0.20


def test_a_shirt_tucked_into_the_pants_goes_under_them():
    shirt, shirt_faces = _cylinder(0.20, 0.8, 1.2)
    pants, pants_faces = _cylinder(0.21, 0.5, 0.9)  # the pants go over the shirt on purpose
    new_shirt, new_pants = layer_top_and_bottom(shirt, shirt_faces, pants, pants_faces, top_type=65)
    np.testing.assert_array_equal(new_pants, pants)
    np.testing.assert_array_equal(new_shirt, shirt)  # already inside: nothing pokes out


def test_fitted_asset_type_reads_the_header(tmp_path):
    path = tmp_path / "fitted.obj"
    path.write_text("# Isometricon Universal Fitted Clothing v24: 1\n# asset_type 67\nv 0 0 0\n")
    assert fitted_asset_type(path) == 67
    path.write_text("# old header\nv 0 0 0\n")
    assert fitted_asset_type(path) is None


def test_covered_vertices_are_those_under_the_outer_cloth():
    from src.clothing.layer_clearance import covered_vertices
    outer, faces = _cylinder(0.20, 0.8, 1.2)
    inner, _ = _cylinder(0.19, 0.5, 1.0)
    covered = covered_vertices(inner, outer, faces)
    np.testing.assert_array_equal(covered, inner[:, 1] >= 0.8)

