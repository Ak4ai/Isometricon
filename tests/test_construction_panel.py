"""O painel de construções: escondido até o /schem, colocar com o mouse, girar, selecionar, remover, nome, lista."""

from types import SimpleNamespace

import glfw
import pytest

from src.interactive.construction_panel import PANEL_HEIGHT, PANEL_WIDTH, ConstructionPanel
from src.interactive.schematic_tool import SchematicTool
from src.world import BlockType

WIDTH, HEIGHT = 1280, 720
LIBRARY = [("sala-teste", {"kind": "schem", "name": "sala-teste"}),
           ("sala-dupla", {"kind": "schem", "name": "sala-dupla"}),
           ("formas", {"kind": "formas"})]
WORLD_POINT = (WIDTH / 2, HEIGHT / 2)                       # longe do painel (canto superior direito)
PANEL_POINT = (WIDTH - PANEL_WIDTH / 2, 16 + PANEL_HEIGHT / 3)


def hit(x, y, z, normal=(0, 1, 0), block=BlockType.GRASS):
    return SimpleNamespace(block=(x, y, z), normal=normal, block_type=block)


@pytest.fixture
def panel():
    tool = SchematicTool(mesh_factory=lambda schematic: None)
    tool.changes = []
    tool.on_change = lambda: tool.changes.append(1)
    return ConstructionPanel(tool, lambda: LIBRARY, create_gl=False)


def press(panel, key, mods=0):
    return panel.handle_key(key, glfw.PRESS, mods)


def click(panel, point=WORLD_POINT, shift=False):
    return panel.handle_mouse_button(glfw.MOUSE_BUTTON_LEFT, glfw.PRESS, shift, point, WIDTH)


def test_closed_panel_takes_no_key_nor_click(panel):
    for key in (glfw.KEY_P, glfw.KEY_V, glfw.KEY_R, glfw.KEY_N, glfw.KEY_DELETE, glfw.KEY_ESCAPE, glfw.KEY_F3,
                glfw.KEY_F4):
        assert not press(panel, key)
    assert not panel.handle_char(ord("a"))
    assert not click(panel)
    assert not click(panel, PANEL_POINT)
    assert panel.tool.preview is None


def test_open_starts_placing_the_first_construction(panel):
    panel.open()
    assert panel.is_open and panel.mode == "place"
    assert panel.tool.preview.entry == LIBRARY[0][1]


def test_click_places_only_where_it_fits(panel):
    panel.open()
    panel.update_cursor(hit(10, 4, 20), None)
    assert panel.valid
    assert click(panel)
    assert len(panel.tool.layer) == 1
    assert panel.tool.preview is not None                    # já pronto para a próxima, a mesma construção
    panel.update_cursor(hit(10, 4, 20), None)                # em cima da que acabou de entrar
    assert not panel.valid
    click(panel)
    assert len(panel.tool.layer) == 1


def test_no_place_on_water_or_on_a_wall(panel):
    panel.open()
    panel.update_cursor(hit(10, 4, 20, block=BlockType.WATER), None)
    assert not panel.valid
    panel.update_cursor(hit(10, 4, 20, normal=(1, 0, 0)), None)
    assert not panel.valid
    panel.update_cursor(None, None)
    assert not panel.valid


def test_no_place_on_the_player(panel):
    panel.open()
    preview = panel.tool.preview.schematic
    panel.update_cursor(hit(10, 4, 20), ((10, 5, 20), (10, 6, 20)))
    assert not panel.valid, preview.name


def test_click_on_the_panel_does_not_place_behind_it(panel):
    panel.open()
    panel.update_cursor(hit(10, 4, 20), None)
    assert click(panel, PANEL_POINT)                         # o painel come o clique
    assert len(panel.tool.layer) == 0


def test_r_rotates_the_preview(panel):
    panel.open()
    before = panel.tool.preview.rotation
    assert press(panel, glfw.KEY_R)
    assert panel.tool.preview.rotation == (before + 1) % 4


def test_select_rotate_and_remove(panel):
    panel.open()
    panel.update_cursor(hit(10, 4, 20), None)
    click(panel)
    placed = panel.tool.layer.structures[0]
    assert press(panel, glfw.KEY_V) and panel.mode == "select"
    assert panel.tool.preview is None                         # selecionando não há holograma
    x0, y0, z0 = placed.origin
    panel.update_cursor(hit(x0, y0, z0, normal=(0, 1, 0)), None)
    if panel.tool.layer.structure_at(x0, y0, z0) is None:     # o canto pode ser ar: aponta para um bloco dela
        import numpy as np
        y, z, x = np.argwhere(placed.schematic.occupied_mask)[0]
        panel.update_cursor(hit(x0 + x, y0 + y, z0 + z), None)
    click(panel)
    assert panel.selected is placed
    assert press(panel, glfw.KEY_R)
    assert panel.selected is panel.tool.layer.structures[0] and panel.selected.rotation == 1
    assert press(panel, glfw.KEY_DELETE)
    assert len(panel.tool.layer) == 0 and panel.selected is None


def test_list_picks_the_third_entry(panel):
    panel.open()
    assert press(panel, glfw.KEY_F4) and panel.list_open
    press(panel, glfw.KEY_DOWN)
    press(panel, glfw.KEY_DOWN)
    press(panel, glfw.KEY_ENTER)
    assert not panel.list_open
    assert panel.tool.preview.entry == LIBRARY[2][1]


def test_f3_takes_the_next_entry(panel):
    panel.open()
    press(panel, glfw.KEY_F3)
    assert panel.tool.preview.entry == LIBRARY[1][1]


def test_name_the_selected_construction(panel):
    panel.open()
    panel.update_cursor(hit(10, 4, 20), None)
    click(panel)
    panel.selected = panel.tool.layer.structures[0]
    panel.mode = "select"
    before = len(panel.tool.changes)
    assert press(panel, glfw.KEY_N)
    for char in "Casa":
        assert panel.handle_char(ord(char))
    assert press(panel, glfw.KEY_ENTER)
    assert panel.tool.layer.structures[0].name == "Casa"
    assert len(panel.tool.changes) == before + 1


def test_arrows_and_wasd_are_left_to_the_game_and_the_tool(panel):
    panel.open()
    for key in (glfw.KEY_UP, glfw.KEY_LEFT, glfw.KEY_W, glfw.KEY_A, glfw.KEY_ENTER):
        assert not press(panel, key)


def test_escape_closes_and_keeps_what_was_placed(panel):
    panel.open()
    panel.update_cursor(hit(10, 4, 20), None)
    click(panel)
    assert press(panel, glfw.KEY_ESCAPE)
    assert not panel.is_open and panel.tool.preview is None and len(panel.tool.layer) == 1


def test_open_with_an_entry_and_buttons(panel):
    panel.open(LIBRARY[2][1])
    assert panel.tool.preview.entry == {"kind": "formas"}
    panel.render(WIDTH, HEIGHT)
    assert set(panel.buttons) == {"place", "select", "library", "rotate", "remove", "close"}
    x0, y0, x1, y1 = panel.buttons["close"]
    left = WIDTH - PANEL_WIDTH - 16
    assert click(panel, (left + (x0 + x1) / 2, 16 + (y0 + y1) / 2))
    assert not panel.is_open


def test_arrow_nudges_survive_until_the_mouse_points_elsewhere(panel):
    panel.open()
    panel.update_cursor(hit(10, 4, 20), None)
    start = list(panel.tool.preview.origin)
    panel.tool.move(dx=1)                                     # a seta empurra um bloco
    panel.update_cursor(hit(10, 4, 20), None)                 # o mouse continua no mesmo bloco
    assert panel.tool.preview.origin == [start[0] + 1, start[1], start[2]]
    panel.update_cursor(hit(11, 4, 20), None)                 # o mouse foi para outro bloco: volta a seguir
    assert panel.tool.preview.origin == [start[0] + 1, start[1], start[2]]
    panel.update_cursor(hit(30, 4, 20), None)
    assert panel.tool.preview.origin[0] == start[0] + 20


def test_list_filters_and_mouse_selection(panel):
    panel.open()
    panel.render(WIDTH, HEIGHT)
    assert panel.filters
    panel.select_filter("exportados")
    assert panel.library() == []              # a biblioteca de teste não tem objetos exportados
    panel.select_filter("todos")
    assert len(panel.library()) == len(LIBRARY)
    panel.render(WIDTH, HEIGHT)
    assert panel.list_rows
    index = min(2, max(panel.list_rows))
    x0, y0, x1, y1 = panel.list_rows[index]
    left = WIDTH - PANEL_WIDTH - 16
    assert click(panel, (left + (x0 + x1) / 2, 16 + (y0 + y1) / 2))
    assert not panel.list_open
    assert panel.tool.preview.entry == LIBRARY[index][1]
