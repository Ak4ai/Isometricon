"""Inner garments pulled under the outer one where they overlap."""
import numpy as np

from src.clothing.layer_clearance import tuck_inner_layer


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
    tucked = tuck_inner_layer(inner, outer, faces)
    covered = tucked[:, 1] >= 0.8
    radius = np.hypot(tucked[covered, 0], tucked[covered, 2])
    assert radius.max() <= 0.20 - 0.004 + 1e-3
    np.testing.assert_array_equal(tucked[~covered], inner[~covered])  # legs below the hem untouched


def test_a_top_tucked_into_the_pants_is_left_alone():
    outer, faces = _cylinder(0.20, 0.8, 1.2)
    inner, _ = _cylinder(0.205, 0.5, 0.9)  # the pants go over the shirt on purpose
    np.testing.assert_array_equal(tuck_inner_layer(inner, outer, faces), inner)
