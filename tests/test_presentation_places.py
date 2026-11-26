"""Onde a apresentação põe as construções de teste e aonde leva o personagem (sem OpenGL)."""
from src.interactive.presentation_places import choose_site, find_cave_spot, find_floor_spot


def test_local_plano_e_seco():
    # morro a leste (x > 30), água ao norte (z < -10): o lugar fica no plano, fora dos dois
    height = lambda x, z: 10 + max(0, x - 30)
    wet = lambda x, z: z < -10
    x0, y, z0 = choose_site(height, wet, (0, 10, 0), (8, 6))
    assert x0 + 8 <= 31 and z0 >= -10 and y == 11


def test_local_evita_o_que_ja_foi_posto():
    flat, dry = (lambda x, z: 5), (lambda x, z: False)
    first = choose_site(flat, dry, (0, 5, 0), (10, 10))
    box = (first, (first[0] + 9, first[1] + 5, first[2] + 9))
    second = choose_site(flat, dry, (0, 5, 0), (10, 10), taken=[box])
    assert abs(second[0] - first[0]) > 12 or abs(second[2] - first[2]) > 12


def _room(cells):
    return lambda x, y, z: (x, y, z) in cells


def test_ponto_dentro_do_comodo():
    # caixa 0..6: chão em y=0, paredes, teto em y=4; um pilar no meio
    solid = set()
    for x in range(7):
        for z in range(7):
            solid.add((x, 0, z))
            solid.add((x, 4, z))
            for y in range(1, 4):
                if x in (0, 6) or z in (0, 6):
                    solid.add((x, y, z))
    solid.update({(3, 1, 3), (3, 2, 3)})
    x, y, z = find_floor_spot(_room(solid), (0, 0, 0), (6, 4, 6))
    assert y == 1.0 and (int(x), int(z)) != (3, 3) and 1 <= x < 6 and 1 <= z < 6
    assert find_floor_spot(_room({(x, 0, z) for x in range(7) for z in range(7)}), (0, 0, 0), (6, 4, 6)) is None


def test_caverna_debaixo_do_terreno():
    surface = lambda x, z: 30

    def solid(x, y, z):
        cave = 10 <= y <= 13 and 4 <= x <= 14 and -5 <= z <= 5
        return y <= 30 and not cave

    x, y, z = find_cave_spot(solid, surface, (0, 30, 0), radius=20)
    assert y == 10.0 and 4 <= x <= 15
    assert find_cave_spot(lambda x, y, z: y <= 30, surface, (0, 30, 0), radius=6) is None
