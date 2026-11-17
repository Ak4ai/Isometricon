"""O atalho do raio do sol (o mapa de alturas por quadrante) dá exatamente a mesma luz que o raio passo a passo."""

import math

import numpy as np

from src.rendering.sun_shadows import column_horizons, cone_rise, quadrant_channel

SOLID, WATER = 255, 128
WATER_TRANSMIT = 0.82


def trace(values, origin, direction, horizons=None, rise=0.0):
    """Cópia em Python de ``traceSun`` (assets/shaders/world_textured.frag). ``values`` é [x, y, z]."""
    size = np.array(values.shape)
    cell = np.floor(origin).astype(int)
    safe = np.array([d if abs(d) >= 1e-5 else 1e-5 for d in direction])
    step = np.sign(safe).astype(int)
    delta = np.abs(1.0 / safe)
    frac = origin - np.floor(origin)
    t_max = np.where(safe > 0, 1.0 - frac, frac) * delta
    channel = quadrant_channel(step[0], step[2])
    use_horizon = horizons is not None and step[1] > 0 and safe[1] >= rise * math.hypot(safe[0], safe[2])
    light = 1.0
    for _ in range(56):
        if np.any(cell < 0) or np.any(cell >= size):
            return light
        if use_horizon and cell[1] >= horizons[cell[0], cell[2], channel]:
            return light
        value = values[tuple(cell)]
        if value > 0.75 * 255:
            return 0.0
        if value > 0.25 * 255:
            light *= WATER_TRANSMIT
        if t_max[0] < t_max[1] and t_max[0] < t_max[2]:
            cell[0] += step[0]; t_max[0] += delta[0]
        elif t_max[1] < t_max[2]:
            cell[1] += step[1]; t_max[1] += delta[1]
        else:
            cell[2] += step[2]; t_max[2] += delta[2]
    return light


def random_world(rng, size=(14, 12, 13)):
    """Um terreno de colunas com morros, algumas árvores soltas no ar e poças de água."""
    sx, sy, sz = size
    values = np.zeros(size, dtype=np.uint8)
    ground = rng.integers(0, sy // 2, size=(sx, sz))
    for x in range(sx):
        for z in range(sz):
            values[x, :ground[x, z], z] = SOLID
            if rng.random() < 0.15:
                values[x, ground[x, z]:ground[x, z] + rng.integers(1, 4), z] = WATER
    for _ in range(rng.integers(0, 6)):  # blocos soltos (copas, beirais)
        values[rng.integers(sx), rng.integers(sy), rng.integers(sz)] = rng.choice([SOLID, WATER])
    return values


def test_without_rise_the_horizon_is_one_above_the_highest_filled_cell_in_the_quadrant_ahead():
    values = np.zeros((3, 5, 2), dtype=np.uint8)
    values[0, 3, 0] = SOLID
    values[2, 1, 1] = WATER
    horizons = column_horizons(values)
    assert horizons.shape == (3, 2, 4)
    plus_plus = horizons[..., quadrant_channel(1, 1)]
    minus_minus = horizons[..., quadrant_channel(-1, -1)]
    assert plus_plus[0, 0] == 4 and plus_plus[1, 0] == 2 and plus_plus[1, 1] == 2 and plus_plus[0, 1] == 2
    assert minus_minus[2, 1] == 4 and minus_minus[0, 0] == 4 and minus_minus[1, 0] == 4 and minus_minus[2, 0] == 4
    assert horizons[1, 1, quadrant_channel(-1, 1)] == 0  # x <= 1 e z >= 1: nada


def test_a_rising_ray_discounts_far_columns():
    values = np.zeros((20, 12, 1), dtype=np.uint8)
    values[19, :10, 0] = SOLID                                    # um muro de 10 no fim
    flat = column_horizons(values)[..., quadrant_channel(1, 1)][:, 0]
    rising = column_horizons(values, rise=0.5)[..., quadrant_channel(1, 1)][:, 0]
    assert (flat == 10).all()
    assert rising[19] == 10 and rising[18] == 10 and rising[17] == 10 and rising[0] <= 4  # de longe passa por cima


def test_cone_rise_is_the_lowest_ray_of_the_cone():
    sun = np.array([0.55, 0.26, 0.7])
    rise = cone_rise(sun)
    assert 0.0 < rise < 0.26 / math.hypot(0.55, 0.7)
    assert cone_rise((0.3, -0.01, 0.2)) == 0.0                    # o cone chega ao horizonte: sem desconto


def test_the_shortcut_gives_the_same_light_as_the_full_ray():
    rng = np.random.default_rng(7)
    checked = shortcuts = 0
    for _ in range(150):
        values = random_world(rng)
        rise = rng.choice([0.0, 0.1, 0.3, 1.0])
        horizons = column_horizons(values, rise)
        size = np.array(values.shape)
        for _ in range(60):
            origin = rng.random(3) * size
            # do sol baixo do jogo (16 graus) ao quase a pino, em qualquer rumo; às vezes num eixo exato
            elevation = rng.uniform(0.02, 1.5)
            heading = rng.uniform(0, 2 * math.pi) if rng.random() > 0.2 else rng.integers(4) * math.pi / 2
            direction = np.array([math.cos(heading) * math.cos(elevation), math.sin(elevation),
                                  math.sin(heading) * math.cos(elevation)])
            assert trace(values, origin, direction, horizons, rise) == trace(values, origin, direction)
            shortcuts += math.tan(elevation) >= rise
            checked += 1
    assert checked == 9000 and shortcuts > 4000
