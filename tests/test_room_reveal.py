"""Testes da descoberta do espaço do jogador (cômodos e cavernas), sem OpenGL."""

import numpy as np
import pytest

from src.world import BlockType, Schematic
from src.world.chunk import Chunk3D
from src.world.room_reveal import (
    INTERIOR,
    SHELL,
    WINDOW,
    RoomRevealTracker,
    compute_room,
    extract_window,
    window_origin,
)
from src.world.structure_layer import StructureLayer


def world(fill):
    """Mundo de 2x2 chunks (32x16x32) em que ``fill(blocks)`` desenha sobre um piso de pedra (y < 3)."""
    chunks = {}
    big = np.zeros((32, 16, 32), dtype=np.uint8)
    big[:, :3, :] = BlockType.STONE
    fill(big)
    for cx in range(2):
        for cz in range(2):
            part = big[cx * 16:(cx + 1) * 16, :, cz * 16:(cz + 1) * 16]
            chunks[(cx, 0, cz)] = Chunk3D(cx, 0, cz, blocks=part)
    return chunks


def box(blocks, x0, z0, size=7, height=4, base=3, roof_block=BlockType.STONE, doors=()):
    """Uma sala de pedra com ar dentro (altura útil ``height``), teto e portas opcionais."""
    x1, z1 = x0 + size, z0 + size
    blocks[x0:x1, base:base + height + 1, z0:z1] = BlockType.STONE
    blocks[x0 + 1:x1 - 1, base:base + height, z0 + 1:z1 - 1] = BlockType.AIR
    blocks[x0:x1, base + height, z0:z1] = roof_block
    for (dx, dy, dz) in doors:
        blocks[x0 + dx, base + dy, z0 + dz] = BlockType.AIR


def room_at(chunks, position, structures=(), was_active=False):
    origin = window_origin(position)
    solid, roof = extract_window(origin, chunks, structures)
    return compute_room(solid, roof, origin, position, was_active)


def test_open_field_is_not_a_room():
    chunks = world(lambda b: None)
    room = room_at(chunks, (16.5, 3.0, 16.5))
    assert not room.active and room.data.max() == 0


def test_enclosed_room_is_revealed_with_a_shell():
    chunks = world(lambda b: box(b, 10, 10))
    room = room_at(chunks, (13.5, 3.0, 13.5))
    assert room.active and room.cells == 5 * 5 * 4
    assert room.exposure == 0.0
    data, (ox, oy, oz) = room.data, room.origin
    assert data[13 - ox, 3 - oy, 13 - oz] == INTERIOR
    assert data[10 - ox, 3 - oy, 13 - oz] == SHELL          # a parede
    assert data[13 - ox, 7 - oy, 13 - oz] == SHELL          # o teto
    assert data[13 - ox, 2 - oy, 13 - oz] == SHELL          # o piso
    assert data[5 - ox, 3 - oy, 5 - oz] == 0                # longe da sala, fora da máscara
    assert (data == INTERIOR).sum() == room.cells


def test_a_door_to_the_outside_does_not_leak_the_room():
    chunks = world(lambda b: box(b, 10, 10, doors=[(0, 0, 3), (0, 1, 3)]))
    room = room_at(chunks, (13.5, 3.0, 13.5))
    assert room.active
    assert room.cells == 5 * 5 * 4 + 2                     # a sala e os 2 blocos da porta; o lado de fora não entra
    ox, oy, oz = room.origin
    assert room.data[9 - ox, 3 - oy, 13 - oz] == 0          # a célula da frente da porta é céu aberto


def test_a_porch_with_only_a_roof_is_not_a_room():
    def porch(b):
        b[10:17, 7, 10:17] = BlockType.STONE               # só um teto, sem paredes
    chunks = world(porch)
    room = room_at(chunks, (13.5, 3.0, 13.5))
    assert not room.active and room.exposure > 0.4


def test_tree_leaves_do_not_make_a_room():
    def tree(b):
        b[10:17, 7, 10:17] = BlockType.LEAVES
    chunks = world(tree)
    assert not room_at(chunks, (13.5, 3.0, 13.5)).active


def test_hysteresis_keeps_a_room_a_little_longer():
    """Uma sala com abertura entre os dois limiares só é "dentro" se já estava."""
    def room_with_big_window(b):
        # duas paredes quase inteiras abertas (5 de largura x 4 de altura cada)
        box(b, 10, 10, doors=[(0, dy, z) for dy in range(4) for z in range(1, 6)]
            + [(x, dy, 0) for dy in range(4) for x in range(1, 6)])
    chunks = world(room_with_big_window)
    entering = room_at(chunks, (13.5, 3.0, 13.5), was_active=False)
    staying = room_at(chunks, (13.5, 3.0, 13.5), was_active=True)
    assert 0.20 <= entering.exposure < 0.35
    assert not entering.active and staying.active


def test_player_standing_inside_the_floor_block_is_lifted_to_the_air():
    chunks = world(lambda b: box(b, 10, 10))
    room = room_at(chunks, (13.5, 2.5, 13.5))               # os pés dentro do bloco do piso
    assert room.active


def test_outside_the_window_is_not_a_room():
    chunks = world(lambda b: box(b, 10, 10))
    origin = window_origin((13.5, 3.0, 13.5))
    solid, roof = extract_window(origin, chunks)
    room = compute_room(solid, roof, origin, (500.0, 3.0, 500.0))
    assert not room.active


def test_structures_make_rooms_too():
    """Uma casa /schem fixada no mundo também é um espaço fechado."""
    n = 7
    grid = np.full((5, n, n), "minecraft:air", dtype=object)
    grid[0, :, :] = "minecraft:stone"
    grid[4, :, :] = "minecraft:stone"
    grid[1:4, 0, :] = grid[1:4, -1, :] = "minecraft:stone"
    grid[1:4, :, 0] = grid[1:4, :, -1] = "minecraft:stone"
    house = Schematic(n, 5, n, grid, palette={}, name="casa")
    layer = StructureLayer()
    layer.add("casa", house, (10, 3, 10))
    chunks = world(lambda b: None)
    room = room_at(chunks, (13.5, 4.0, 13.5), layer.structures)
    assert room.active and room.cells == 5 * 5 * 3
    # sem a casa, o mesmo ponto é ao ar livre
    assert not room_at(chunks, (13.5, 4.0, 13.5)).active


def test_leaves_inside_a_roofed_space_still_block_the_flood():
    chunks = world(lambda b: box(b, 10, 10))
    chunks_open = world(lambda b: None)
    assert room_at(chunks, (13.5, 3.0, 13.5)).active
    assert not room_at(chunks_open, (13.5, 3.0, 13.5)).active


def test_tracker_recomputes_only_when_something_changed():
    chunks = world(lambda b: box(b, 10, 10))
    tracker = RoomRevealTracker()
    first = tracker.update(0.016, (13.5, 3.0, 13.5), chunks, 1)
    version = tracker.version
    assert tracker.update(0.016, (13.5, 3.0, 13.5), chunks, 1) is first
    assert tracker.version == version                       # nada mudou: não recalculou
    tracker.update(0.016, (13.5, 3.0, 13.5), chunks, 2)      # o mundo mudou
    assert tracker.version == version + 1
    tracker.update(1.0, (14.5, 3.0, 13.5), chunks, 2)        # o jogador andou e já passou o intervalo
    assert tracker.version == version + 2
    assert tracker.active


def test_tracker_waits_a_little_between_walking_recomputes():
    chunks = world(lambda b: box(b, 10, 10))
    tracker = RoomRevealTracker()
    tracker.update(1.0, (13.5, 3.0, 13.5), chunks, 1)
    version = tracker.version
    tracker.update(0.01, (14.5, 3.0, 13.5), chunks, 1)       # andou, mas faz pouco tempo
    assert tracker.version == version


def test_window_has_the_documented_size_and_centres_the_player():
    assert WINDOW == (48, 32, 48)
    ox, oy, oz = window_origin((100.7, 20.0, -5.2))
    assert ox == 100 - 24 and oz == -6 - 24 and oy == 20 - 10


# ---------------------------------------------------------------- renderizador (sem OpenGL)
@pytest.fixture
def renderer(monkeypatch):
    """RoomRevealRenderer com o envio à GPU trocado por um registro."""
    from src.rendering.room_reveal import RoomRevealRenderer

    r = RoomRevealRenderer(exterior=0.2)
    r.uploads = []
    monkeypatch.setattr(RoomRevealRenderer, "_upload", lambda self, mask: (r.uploads.append(mask), setattr(self, "_uploaded", mask)))
    return r


def tracker_in(position, fill):
    tracker = RoomRevealTracker()
    tracker.update(1.0, position, world(fill), 1)
    return tracker


def test_effect_fades_in_inside_a_room_and_out_again(renderer):
    inside = tracker_in((13.5, 3.0, 13.5), lambda b: box(b, 10, 10))
    outside = tracker_in((30.5, 3.0, 30.5), lambda b: box(b, 10, 10))
    assert inside.active and not outside.active
    assert renderer.level == 0.0 and not renderer.visible

    renderer.update(0.05, inside)
    assert 0.0 < renderer.level < 1.0 and renderer.visible
    for _ in range(60):
        renderer.update(0.05, inside)
    assert renderer.level == 1.0
    for _ in range(60):
        renderer.update(0.05, outside)
    assert renderer.level == 0.0 and not renderer.visible


def test_old_mask_stays_on_the_gpu_while_the_effect_fades_out(renderer):
    inside = tracker_in((13.5, 3.0, 13.5), lambda b: box(b, 10, 10))
    outside = tracker_in((30.5, 3.0, 30.5), lambda b: box(b, 10, 10))
    for _ in range(40):
        renderer.update(0.05, inside)
    shown = renderer._shown
    renderer.update(0.05, outside)                    # saiu: o efeito ainda está apagando
    assert renderer.visible and renderer._shown is shown
    assert len(renderer.uploads) == 1                 # a máscara vazia nunca foi enviada


def test_mask_is_uploaded_once_per_new_room(renderer):
    inside = tracker_in((13.5, 3.0, 13.5), lambda b: box(b, 10, 10))
    for _ in range(10):
        renderer.update(0.05, inside)
    assert len(renderer.uploads) == 1


def test_disabled_renderer_never_shows(renderer):
    inside = tracker_in((13.5, 3.0, 13.5), lambda b: box(b, 10, 10))
    renderer.enabled = False
    for _ in range(20):
        renderer.update(0.05, inside)
    assert renderer.level == 0.0 and not renderer.visible and renderer.uploads == []


class FakeShader:
    def __init__(self):
        self.values = {}

    def set_float(self, name, value):
        self.values[name] = value

    def set_int(self, name, value):
        self.values[name] = value

    def set_vec3(self, name, x, y, z):
        self.values[name] = (x, y, z)

    def set_mat4(self, name, matrix):
        self.values[name] = matrix


def test_view_direction_is_returned_to_world_space(renderer, monkeypatch):
    """O shader olha no espaço girado pelo modelo; a direção enviada volta ao mundo pela inversa."""
    import OpenGL.GL as gl
    from src.math import mat4_look_at, mat4_rotate_y, vec3

    for name in ("glActiveTexture", "glBindTexture"):
        monkeypatch.setattr(gl, name, lambda *a, **k: None)
    inside = tracker_in((13.5, 3.0, 13.5), lambda b: box(b, 10, 10))
    for _ in range(40):
        renderer.update(0.05, inside)
    eye = vec3(10.0, 10.0, 10.0)
    view = mat4_look_at(eye, vec3(0.0, 0.0, 0.0), vec3(0.0, 1.0, 0.0))
    world_dir = -eye / np.linalg.norm(eye)                    # a câmera olha da posição para a origem

    shader = FakeShader()
    renderer.apply(shader, np.identity(4, dtype=np.float32), view)
    assert np.allclose(shader.values["u_ViewDir"], world_dir, atol=1e-5)
    assert shader.values["u_RoomActive"] == 1.0 and shader.values["u_RoomExterior"] == 0.2

    # Com o tabuleiro girado 90° o modelo gira o mundo dentro do espaço desenhado e a câmera não muda:
    # o que a câmera vê em "para a frente" é, no mundo, essa direção desfeita pela inversa do modelo.
    model = mat4_rotate_y(np.pi / 2)
    shader = FakeShader()
    renderer.apply(shader, model, view)
    expected = np.linalg.inv(model)[:3, :3] @ world_dir
    assert np.allclose(shader.values["u_ViewDir"], expected, atol=1e-5)
    assert not np.allclose(shader.values["u_ViewDir"], world_dir, atol=1e-3)  # e muda de fato

    renderer.disable(shader)
    assert shader.values["u_RoomActive"] == 0.0
