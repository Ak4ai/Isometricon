"""Testes do /schem: prévia, teclas, fixação, colisão e comandos do chat (sem OpenGL)."""

import glfw
import numpy as np
import pytest

from src.interactive.schematic_tool import SchematicTool, snap_axis
from src.interactive.skin_commands import COMMAND_TREE, SkinCommandHandler
from src.physics.voxel_collision import VoxelCollisionController
from src.integration.voxel_grid import VoxelGridProvider
from src.world import BlockType, Schematic
from src.world.structure_layer import StructureLayer


class FakeMesh:
    """Malha de mentira: só conta se foi apagada."""

    def __init__(self):
        self.deleted = False

    def delete(self):
        self.deleted = True


def make_schematic(blocks, width, height, length, name="casa"):
    grid = np.full((height, length, width), "minecraft:air", dtype=object)
    for (x, y, z), block in blocks.items():
        grid[y, z, x] = block
    return Schematic(width, height, length, grid, palette={}, name=name)


@pytest.fixture
def folder(tmp_path):
    return str(tmp_path)


@pytest.fixture
def tool(monkeypatch):
    """Ferramenta com o carregamento trocado por uma casa de 3x2x3 e malhas falsas."""
    house = make_schematic({(x, 0, z): "minecraft:stone" for x in range(3) for z in range(3)}, 3, 2, 3)
    monkeypatch.setattr(Schematic, "load_from_file", classmethod(lambda cls, path: house))
    t = SchematicTool(
        ground_height=lambda x, z: 4,
        player_position=lambda: (10.5, 5.0, 20.5),
        view_axes=lambda: (np.array([0.0, 0.0, -1.0]), np.array([1.0, 0.0, 0.0])),
        mesh_factory=lambda schematic: FakeMesh(),
    )
    monkeypatch.setattr(t, "resolve", lambda text: "casa.schem" if text.strip().strip("\"'") == "casa" else None)
    t.messages = []
    t.notify = t.messages.append
    return t


def key(tool, k, mods=0, action=glfw.PRESS):
    return tool.handle_key(k, action, mods)


def test_snap_axis_picks_the_dominant_axis():
    assert snap_axis([0.0, 0.0, -1.0]) == (0, -1)
    assert snap_axis([0.9, 0.0, 0.1]) == (1, 0)
    assert snap_axis([-0.7, 0.0, 0.69]) == (-1, 0)


def test_load_opens_a_preview_in_front_of_the_player_on_the_ground(tool):
    ok, message = tool.load("casa")
    assert ok and tool.active and "3x2x3" in message
    x, y, z = tool.preview.origin
    assert y == 5  # no chão: o topo do terreno (4) mais um
    # o jogador olha para -Z: a construção fica atrás dele no eixo Z (menor z) e centrada em X
    assert z + 3 <= 20 and z > 20 - 3 - 3 - 2
    assert x == int(np.floor(10.5 - 1.5))


def test_load_with_explicit_origin(tool):
    ok, _ = tool.load("casa", origin=(1, 2, 3))
    assert ok and tool.preview.origin == [1, 2, 3]


def test_load_unknown_name_reports_and_keeps_state(tool):
    ok, message = tool.load("nao_existe")
    assert not ok and "não encontrada" in message and not tool.active


def test_arrows_move_horizontally_and_shift_arrows_change_height(tool):
    tool.load("casa", origin=(0, 0, 0))
    assert key(tool, glfw.KEY_UP)          # para frente = -Z
    assert tool.preview.origin == [0, 0, -1]
    assert key(tool, glfw.KEY_RIGHT)       # direita = +X
    assert tool.preview.origin == [1, 0, -1]
    assert key(tool, glfw.KEY_DOWN)
    assert key(tool, glfw.KEY_LEFT)
    assert tool.preview.origin == [0, 0, 0]
    assert key(tool, glfw.KEY_UP, glfw.MOD_SHIFT)
    assert tool.preview.origin == [0, 1, 0]
    assert key(tool, glfw.KEY_DOWN, glfw.MOD_SHIFT)
    assert key(tool, glfw.KEY_DOWN, glfw.MOD_SHIFT)
    assert tool.preview.origin == [0, -1, 0]


def test_arrows_follow_the_camera_rotation(tool):
    tool.view_axes = lambda: (np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0, 1.0]))
    tool.load("casa", origin=(0, 0, 0))
    key(tool, glfw.KEY_UP)
    assert tool.preview.origin == [1, 0, 0]
    key(tool, glfw.KEY_RIGHT)
    assert tool.preview.origin == [1, 0, 1]


def test_up_and_right_never_share_an_axis_on_the_isometric_diagonal(tool):
    """Com a câmera a 45°, 'para frente' é uma diagonal; as quatro setas ainda têm direções diferentes."""
    tool.view_axes = lambda: (np.array([-0.7071, 0.0, -0.7071]), np.array([0.7071, 0.0, -0.7071]))
    moves = set()
    for k in (glfw.KEY_UP, glfw.KEY_DOWN, glfw.KEY_LEFT, glfw.KEY_RIGHT):
        tool.load("casa", origin=(0, 0, 0))
        key(tool, k)
        moves.add(tuple(tool.preview.origin))
    assert len(moves) == 4


def test_held_arrow_repeats_and_release_does_nothing(tool):
    tool.load("casa", origin=(0, 0, 0))
    key(tool, glfw.KEY_RIGHT, action=glfw.REPEAT)
    key(tool, glfw.KEY_RIGHT, action=glfw.REPEAT)
    assert tool.preview.origin == [2, 0, 0]
    assert key(tool, glfw.KEY_RIGHT, action=glfw.RELEASE)  # consumida, mas sem mover
    assert tool.preview.origin == [2, 0, 0]


def test_keys_are_not_consumed_without_a_preview(tool):
    assert not key(tool, glfw.KEY_UP)
    assert not key(tool, glfw.KEY_ESCAPE)
    assert not key(tool, glfw.KEY_ENTER)


def test_unrelated_keys_pass_through_during_the_preview(tool):
    tool.load("casa")
    assert not key(tool, glfw.KEY_W)
    assert not key(tool, glfw.KEY_Q)


def test_enter_confirms_and_the_structure_gets_collision(tool):
    tool.load("casa", origin=(5, 5, 5))
    assert key(tool, glfw.KEY_ENTER)
    assert not tool.active and len(tool.layer) == 1
    assert "fixada em x=5 y=5 z=5" in tool.messages[-1]
    base = lambda x, y, z: BlockType.AIR
    assert tool.lookup(base, 6, 5, 6) == BlockType.STONE      # dentro da base de pedra
    assert tool.lookup(base, 6, 6, 6) == BlockType.AIR        # acima da base: ar na construção
    assert tool.lookup(base, 20, 5, 6) == BlockType.AIR       # fora da caixa


def test_escape_cancels_and_frees_the_mesh(tool):
    tool.load("casa")
    mesh = tool.preview.mesh
    assert key(tool, glfw.KEY_ESCAPE)
    assert not tool.active and mesh.deleted and len(tool.layer) == 0
    assert "cancelada" in tool.messages[-1]


def test_loading_again_replaces_the_preview(tool):
    tool.load("casa")
    first = tool.preview.mesh
    tool.load("casa")
    assert first.deleted and tool.preview.mesh is not first


def test_remove_last_and_clear(tool):
    for origin in [(0, 0, 0), (10, 0, 0)]:
        tool.load("casa", origin=origin)
        tool.confirm()
    meshes = [s.mesh for s in tool.layer.structures]
    assert tool.remove_last()[0] and meshes[1].deleted and len(tool.layer) == 1
    tool.load("casa")
    assert tool.clear()[0]
    assert len(tool.layer) == 0 and not tool.active and all(m.deleted for m in meshes)
    assert not tool.remove_last()[0]


def test_player_cannot_walk_through_a_fixed_structure(tool):
    """A colisão do personagem enxerga a construção como terreno: uma parede de 2 blocos o barra."""
    wall = make_schematic({(0, y, z): "minecraft:stone" for y in range(2) for z in range(3)}, 1, 2, 3)
    tool.layer.add("parede", wall, (5, 1, 0))
    ground = lambda x, y, z: BlockType.STONE if y < 1 else BlockType.AIR  # chão sólido até y = 0
    provider = VoxelGridProvider(block_lookup=lambda x, y, z: tool.lookup(ground, x, y, z))
    controller = VoxelCollisionController(provider)

    position = np.array([2.5, 1.0, 1.5], dtype=np.float64)  # em pé no chão, a 2,5 blocos da parede
    velocity = 0.0
    for _ in range(60):
        result = controller.move(position, np.array([0.1, 0.0, 0.0]), 1 / 60, velocity)
        position, velocity = result.position, result.vertical_velocity
    assert position[0] < 5.0, position            # parou antes da parede (x = 5)
    assert result.collided_x

    # sem a construção o mesmo passeio atravessa o ponto
    free = VoxelCollisionController(VoxelGridProvider(block_lookup=ground))
    position, velocity = np.array([2.5, 1.0, 1.5]), 0.0
    for _ in range(60):
        result = free.move(position, np.array([0.1, 0.0, 0.0]), 1 / 60, velocity)
        position, velocity = result.position, result.vertical_velocity
    assert position[0] > 6.0


# ---------------------------------------------------------------- StructureLayer
def test_layer_lookup_only_solid_cells_and_order():
    layer = StructureLayer()
    layer.add("a", make_schematic({(0, 0, 0): "minecraft:stone"}, 2, 1, 1), (3, 3, 3))
    base = lambda x, y, z: BlockType.WATER
    look = layer.wrap_lookup(base)
    assert look(3, 3, 3) == BlockType.STONE
    assert look(4, 3, 3) == BlockType.WATER  # ar dentro da caixa: vale o terreno
    assert layer.remove_last().name == "a" and look(3, 3, 3) == BlockType.WATER


# ---------------------------------------------------------------- comandos do chat
def test_schem_command_without_a_terrain_tool():
    ok, message, _ = SkinCommandHandler(character_model=None).execute("/schem list", run_async=False)
    assert not ok and "terreno" in message


def test_schem_command_flow(tool):
    handler = SkinCommandHandler(character_model=None)
    handler.schematic_tool = tool
    run = lambda line: handler.execute(line, run_async=False)

    assert run("/schem")[0]                                  # só mostra o uso
    ok, message, _ = run('/schem load "casa"')
    assert ok and tool.active and "prévia" in message
    assert run("/schem place")[0] and len(tool.layer) == 1
    assert run("/schematic carregar casa 7 8 9")[0] and tool.preview.origin == [7, 8, 9]
    assert run("/schem cancel")[0] and not tool.active
    assert run("/schem info")[0] and "1. casa" in run("/schem info")[1]
    assert run("/schem remove")[0] and run("/schem clear")[0]
    assert not run("/schem place")[0]                        # nada em prévia
    assert not run("/schem load")[0]                         # falta o nome
    assert not run("/schem load nao_existe")[0]


def test_schem_list_shows_the_project_schematics():
    handler = SkinCommandHandler(character_model=None)
    handler.schematic_tool = SchematicTool()
    ok, message, _ = handler.execute("/schem list", run_async=False)
    assert ok and "31422" in message and "29455" in message


def test_schem_autocomplete_lists_subcommands_and_names():
    assert {"load", "list", "place", "cancel", "remove", "clear", "info"} <= set(COMMAND_TREE["schem"])
    assert "31422" in COMMAND_TREE["schem"]["load"]()


def test_resolve_accepts_names_and_paths(folder):
    path = f"{folder}/minha casa.schem"
    open(path, "wb").close()
    t = SchematicTool(schematics_dir=folder)
    assert t.names() == ["minha casa"]
    assert t.resolve("minha casa") == f"{folder}{__import__('os').sep}minha casa.schem"
    assert t.resolve(f'"{path}"') == path
    assert t.resolve("outra") is None and t.resolve("") is None
