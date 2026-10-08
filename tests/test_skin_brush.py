"""A pele escondida sob a roupa, corrigida: espelhada automaticamente ou pintada com o pincel."""
from types import SimpleNamespace

import numpy as np

from src.clothing import character_save
from src.clothing.customization import AvatarCustomization
from src.clothing.hsr import adjusted_hidden, mirror_index
from src.interactive import skin_brush
from src.interactive.character_editor import BRUSH_SIZES, FINE_SECTION, PANEL_WIDTH, CharacterEditor
from src.interactive.skin_commands import SkinCommandHandler

SIZE = (1280, 720)
LEFT, RIGHT, PRESS, RELEASE = 0, 1, 1, 0
# A cage of six points: two pairs that mirror each other, one in the middle, one with no mirror.
CAGE = np.array([[0.2, 1.0, 0.1], [-0.2, 1.0, 0.1], [0.3, 1.2, 0.0], [-0.3, 1.2, 0.0], [0.0, 1.5, 0.1], [0.4, 0.5, 0.0]])


def test_mirroring_hides_the_point_across_the_body_and_painting_wins():
    assert mirror_index(CAGE).tolist() == [1, 0, 3, 2, 4, -1]
    hidden = np.array([True, False, False, False, False, True])
    assert adjusted_hidden(hidden, CAGE).tolist() == hidden.tolist()                       # nothing asked: as it was
    assert adjusted_hidden(hidden, CAGE, mirror=True).tolist() == [True, True, False, False, False, True]
    painted = adjusted_hidden(hidden, CAGE, mirror=True, hide=(2, 99), show=(1,))
    assert painted.tolist() == [True, False, True, False, False, True]                     # by hand, over the mirror; 99 is no point
    assert hidden.tolist() == [True, False, False, False, False, True]                     # the mask given is not changed


def make_model(**fields):
    calls = []
    model = SimpleNamespace(customization=AvatarCustomization(**fields), body="female", reload=lambda: calls.append("reload"),
                            refresh_skin=lambda: calls.append("skin") or True)
    return model, calls


def test_the_command_mirrors_paints_and_clears():
    model, calls = make_model()
    handler, custom = SkinCommandHandler(character_model=model), model.customization
    assert handler.execute("/skin hsr espelhar sim")[0] and custom.hsr_mirror is True and calls == ["skin"]   # only the skin is cut again
    assert handler.execute("/skin hsr esconder 4,2,9")[0] and custom.hsr_hide == (2, 4, 9)
    assert handler.execute("/skin hsr mostrar 9, 11")[0] and custom.hsr_hide == (2, 4) and custom.hsr_show == (9, 11)
    assert handler.execute("/skin hsr apagar 2,11")[0] and custom.hsr_hide == (4,) and custom.hsr_show == (9,)
    assert not handler.execute("/skin hsr esconder x")[0] and not handler.execute("/skin hsr esconder -1")[0]
    assert not handler.execute("/skin hsr pintar 3")[0] and custom.hsr_hide == (4,)
    assert handler.execute("/skin hsr limpar")[0] and custom.hsr_hide == () and custom.hsr_show == () and custom.hsr_mirror is True
    model.refresh_skin = lambda: False                                                      # no mask to cut by: rebuilt
    assert handler.execute("/skin hsr espelhar nao")[0] and custom.hsr_mirror is False and calls[-1] == "reload"


def test_the_corrections_are_saved_with_the_character(tmp_path):
    model = SimpleNamespace(customization=AvatarCustomization(hsr_mirror=True, hsr_hide=(3, 7), hsr_show=(12,)))
    path = str(tmp_path / "personagem.json")
    character_save.save(model, path)
    loaded = character_save.customization_from(character_save.load(path))
    assert loaded.hsr_mirror is True and tuple(loaded.hsr_hide) == (3, 7) and tuple(loaded.hsr_show) == (12,)


def view(rect=(400, 0, 1200, 800), pose=None):
    """The cage seen from the front, one metre a hundred pixels: x to the right, y up, the camera at +z."""
    look = np.identity(4)
    look[2, 3] = -5.0
    projection = np.diag([1 / 4.0, 1 / 4.0, -0.1, 1.0])  # an orthographic 8 m by 8 m
    faces = np.array([[0, 2, 4], [1, 4, 3], [0, 4, 1]])
    return skin_brush.BrushView(CAGE, faces, np.identity(4), look, projection, rect, pose=pose)


def test_the_brush_takes_the_points_under_it_on_the_near_side():
    seen = view()
    np.testing.assert_allclose(seen.xy[0], [400 + 400 + 20, 400 - 100])                    # x = 0.2, y = 1.0
    seen.facing = np.array([True, True, True, True, True, False])
    assert seen.pick(820, 300, 6) == [0]
    assert seen.pick(820, 300, 6, mirror=True) == [0, 1]                                    # and the one across the body
    assert seen.pick(800, 300, 30) == [0, 1]                                                # a larger brush
    assert seen.pick(100, 100, 6) == []                                                     # nothing under it
    assert seen.pick(840, 350, 6) == []                                                     # the point there is on the far side
    seen.depth = np.array([-5.0, -5.5, -5.0, -5.0, -5.0, -5.0])
    assert seen.pick(800, 300, 30) == [0]                                                   # half a metre behind: not painted through
    moved = view(pose=lambda points, normals: (np.asarray(points) + [1.0, 0.0, 0.0], normals))
    np.testing.assert_allclose(moved.xy[:, 0], seen.xy[:, 0] + 100)                         # the cage as the body is posed


def test_each_point_is_shown_as_what_it_is():
    kinds = skin_brush.states([True, False, False, True, False, False], (2, 77), (3,))
    assert kinds.tolist() == [skin_brush.HIDDEN, skin_brush.SHOWN, skin_brush.PAINTED_HIDDEN, skin_brush.PAINTED_SHOWN,
                              skin_brush.SHOWN, skin_brush.SHOWN]
    seen = view()
    facing = np.array([True, True, True, True, True, False])
    image = np.array(skin_brush.overlay((800, 800), (400, 0), seen.xy, facing, kinds, stroke=(1,)))
    at = lambda index: tuple(image[int(round(seen.xy[index, 1])), int(round(seen.xy[index, 0] - 400))])
    assert at(0) == skin_brush.COLOURS[skin_brush.HIDDEN] and at(2) == skin_brush.COLOURS[skin_brush.PAINTED_HIDDEN]
    assert at(3) == skin_brush.COLOURS[skin_brush.PAINTED_SHOWN] and at(1) == skin_brush.STROKE
    assert at(5)[3] == 0                                                                    # the far side is not drawn
    assert image[0, 0, 3] == 0 and skin_brush.ring(22).size == (50, 50)


def make_editor():
    sent = []
    model = SimpleNamespace(body="female", customization=AvatarCustomization(), hsr_cage=(CAGE, None, None))
    handler = SimpleNamespace(character_model=model, busy_status="",
                              execute=lambda command: (sent.append(command), (True, "feito", (0, 0, 0)))[1])
    editor = CharacterEditor(handler, {"active": True, "yaw": 0.0, "pitch": 20.0}, create_gl=False)
    editor.open()
    editor.select_section([s.title for s in editor.sections].index(FINE_SECTION))
    editor.layout(*SIZE)
    return editor, sent


def option(editor, label):
    return next(o for group in editor.groups() for o in group.options if o.label == label)


def test_the_brush_paints_by_dragging_and_the_right_button_turns():
    editor, sent = make_editor()
    assert max(rect[3] for rect, kind, _ in editor.layout(*SIZE) if kind == "tab") <= SIZE[1]   # every tab fits the window
    assert not editor.brushing and not editor.handle_mouse_button(700, 300, RIGHT, PRESS)    # out of the edit mode the right button is the game's
    editor.choose(option(editor, "Espelhar os lados"))
    assert sent == ["/skin hsr espelhar sim"]
    assert option(editor, "Editar pele").check
    editor.choose(option(editor, "Editar pele"))
    assert editor.brushing and editor.brush == "esconder" and editor.model.hsr_edit is True
    assert editor.turntable["active"] is False and sent == ["/skin hsr espelhar sim"]         # no command for that
    editor.choose(option(editor, "Grande"))
    editor.choose(option(editor, "Os dois lados"))
    assert editor.brush_size == BRUSH_SIZES[2][1] and editor.brush_mirror
    asked = []
    under = {(700, 300): [5, 2], (720, 310): [2, 8]}
    editor.picker = lambda x, y, radius, mirror: (asked.append((radius, mirror)), under.get((x, y), []))[1]
    x = PANEL_WIDTH + 292
    assert x == 700
    assert editor.handle_mouse_button(700, 300, LEFT, PRESS)
    editor.handle_cursor(720, 310)
    editor.handle_cursor(900, 500)                                                          # over nothing
    yaw = editor.turntable["yaw"]
    assert editor.handle_mouse_button(900, 500, LEFT, RELEASE)
    assert sent[-1] == "/skin hsr esconder 2,5,8" and editor.turntable["yaw"] == yaw         # one command for the stroke; nothing turned
    assert asked[0] == (BRUSH_SIZES[2][1], True)
    assert editor.handle_mouse_button(900, 500, LEFT, PRESS) and editor.handle_mouse_button(900, 500, LEFT, RELEASE)
    assert sent[-1] == "/skin hsr esconder 2,5,8"                                            # an empty stroke sends nothing
    assert editor.handle_mouse_button(700, 300, RIGHT, PRESS)                                # the right button turns the character
    editor.handle_cursor(760, 300)
    assert editor.turntable["yaw"] != yaw and editor.handle_mouse_button(760, 300, RIGHT, RELEASE)
    editor.choose(option(editor, "Mostrar pele"))
    editor.handle_mouse_button(700, 300, LEFT, PRESS)
    editor.handle_mouse_button(700, 300, LEFT, RELEASE)
    assert sent[-1] == "/skin hsr mostrar 2,5"
    editor.ctrl = True                                                                       # Ctrl: the opposite of the brush
    editor.handle_mouse_button(700, 300, LEFT, PRESS)
    editor.ctrl = False
    editor.handle_mouse_button(700, 300, LEFT, RELEASE)
    assert sent[-1] == "/skin hsr esconder 2,5"
    sent.append("/skin hsr mostrar 2,5")
    editor.choose(option(editor, "Editar pele"))
    assert editor.model.hsr_edit is False
    assert not editor.brushing and editor.handle_mouse_button(700, 300, LEFT, PRESS)         # the drag turns again
    editor.handle_cursor(760, 300)
    editor.handle_mouse_button(760, 300, LEFT, RELEASE)
    assert sent[-1] == "/skin hsr mostrar 2,5"
    assert not editor.handle_mouse_button(700, 300, RIGHT, PRESS)                            # and the right button is the game's


def test_the_brush_only_works_in_its_own_section():
    editor, sent = make_editor()
    editor.choose(option(editor, "Editar pele"))
    assert editor.model.hsr_edit is True
    editor.select_section(0)
    assert not editor.brushing and editor.model.hsr_edit is False                            # the character as it is, elsewhere
    editor.select_section([s.title for s in editor.sections].index(FINE_SECTION))
    assert editor.model.hsr_edit is True
    editor.close()
    assert editor.model.hsr_edit is False                                                    # and in the game
    editor.open()
    editor.select_section(0)
    editor.picker = lambda *args: [1]
    editor.handle_mouse_button(700, 300, LEFT, PRESS)
    editor.handle_mouse_button(700, 300, LEFT, RELEASE)
    assert sent == []


def test_an_edge_of_a_garment_moves_and_the_cloth_near_it_follows():
    from src.clothing import body_shape
    points = np.array([[0.0, 1.00, 0.0], [0.1, 1.05, 0.0], [0.0, 1.20, 0.0], [0.0, 1.40, 0.0], [0.3, 1.00, 0.0]])
    keep = np.array([True, True, True, True, False])                                        # the last one is a sleeve
    up = body_shape.move_edge(points, 1.00, 0.08, lower=True, keep=keep)
    assert abs(up[0, 1] - 1.08) < 1e-9 and up[4, 1] == 1.00                                 # the hem goes whole; the sleeve stays
    assert 1.05 < up[1, 1] < 1.13 and up[2, 1] == 1.20 and up[3, 1] == 1.40                 # less and less, nothing past the reach
    assert (np.diff(up[:4, 1]) > 0).all() and (up[:, [0, 2]] == points[:, [0, 2]]).all()    # no fold; only the height changes
    down = body_shape.move_edge(points, 1.40, -0.08, lower=False)
    assert abs(down[3, 1] - 1.32) < 1e-9 and down[0, 1] == 1.00 and down[2, 1] == 1.20
    assert body_shape.garment_shift({"blusa_barra": -0.5}, "blusa_barra") == -0.04
    assert set(body_shape.GARMENTS) == set(body_shape.GARMENT_EDGES) <= set(body_shape.ADJUSTMENTS)


def test_the_skin_follows_a_moved_edge():
    from src.clothing.hsr import EDGE_HIDDEN, EDGE_SHOWN, move_mask_edge
    y = np.array([0.90, 0.97, 1.00, 1.05, 1.20, 1.05])
    cage = np.column_stack((np.zeros(6), y, np.zeros(6)))
    parts = np.array(["LowerTorso"] * 5 + ["LeftUpperArm"])
    top = np.array([False, False, True, True, True, True])                                  # a top whose hem is at 1.00
    assert move_mask_edge(top, cage, parts, 1.00, 0.0).tolist() == top.tolist()
    raised = move_mask_edge(top, cage, parts, 1.00, 0.08)                                   # hem at 1.08: the skin below it shows
    assert raised.tolist() == [False, False, False, False, True, True]                      # the arm keeps its sleeve
    lowered = move_mask_edge(top, cage, parts, 1.00, -0.08)                                 # hem at 0.92: the band it covers is hidden
    assert lowered.tolist() == [False, True, True, True, True, True] and 0.92 + EDGE_HIDDEN < 0.97
    pants = np.array([True, True, True, False, False, False])                               # pants whose waist is at 1.00
    assert move_mask_edge(pants, cage, parts, 1.00, -0.08, lower=False).tolist() == [True, False, False, False, False, False]
    assert move_mask_edge(pants, cage, parts, 1.00, 0.08, lower=False).tolist() == [True, True, True, True, False, False]
    assert top.tolist() == [False, False, True, True, True, True] and EDGE_SHOWN > 0


def test_moving_an_edge_cuts_the_skin_again():
    model, calls = make_model()
    handler = SkinCommandHandler(character_model=model)
    assert handler.execute("/skin ajuste blusa_barra 50")[0] and calls == ["skin"]
    assert model.customization.body_adjust["blusa_barra"] == 0.5
    assert handler.execute("/skin ajuste blusa_barra 50")[0] and calls == ["skin"]           # the same value: nothing to do
    assert handler.execute("/skin ajuste peito 30")[0] and calls == ["skin"]                 # the body's own adjustments do not
    assert handler.execute("/skin ajuste reset")[0] and calls == ["skin", "skin"]
    editor, _ = make_editor()
    labels = [o.label for group in editor.groups() for o in group.options]
    assert {"Barra da blusa (altura)", "Cintura da calça (altura)", "Barra da calça (altura)"} <= set(labels)


def test_the_edited_skin_is_painted_by_what_each_point_is():
    from src.clothing.hsr import EDIT_HIDDEN, EDIT_PAINTED_HIDDEN, EDIT_PAINTED_SHOWN, EDIT_SHOWN, edit_colours
    faces = np.array([[0, 1, 2], [2, 3, 4]])
    hidden = np.array([True, True, True, False, False])
    nearest = (np.array([0, 1, 1, 1]), np.array([[1 / 3, 1 / 3, 1 / 3], [0.0, 0.5, 0.5], [0.0, 0.0, 1.0], [0.0, 1.0, 0.0]]))
    colours = edit_colours(nearest, faces, hidden)
    np.testing.assert_allclose(colours[0], EDIT_HIDDEN)                                     # all of it hidden
    np.testing.assert_allclose(colours[1], EDIT_SHOWN)                                      # between two points that show
    painted = edit_colours(nearest, faces, hidden, painted_hidden=(4, 99), painted_shown=(3,))
    np.testing.assert_allclose(painted[2], EDIT_PAINTED_HIDDEN)
    np.testing.assert_allclose(painted[3], EDIT_PAINTED_SHOWN)
    assert not np.allclose(painted[1], colours[1]) and np.allclose(painted[0], colours[0])  # blended between the two; untouched elsewhere


def test_the_brush_has_its_own_check_and_comes_on_with_the_edit_mode():
    editor, _ = make_editor()
    assert option(editor, "Ativar pincel").check and not editor.brush_on
    editor.choose(option(editor, "Ativar pincel"))                                          # the brush alone: the mode comes with it
    assert editor.hsr_edit and editor.brush_on and editor.brushing
    editor.choose(option(editor, "Ativar pincel"))                                          # off: the mode stays, the drag turns
    assert editor.hsr_edit and not editor.brushing and editor.model.hsr_edit is True
    yaw = editor.turntable["yaw"]
    editor.handle_mouse_button(700, 300, LEFT, PRESS)
    editor.handle_cursor(760, 300)
    editor.handle_mouse_button(760, 300, LEFT, RELEASE)
    assert editor.turntable["yaw"] != yaw
    editor.choose(option(editor, "Editar pele"))
    assert not editor.hsr_edit and not editor.brush_on
    editor.choose(option(editor, "Editar pele"))
    assert editor.brushing                                                                  # the mode brings the brush


def test_changes_of_the_skin_are_undone_and_redone():
    model, _ = make_model()
    handler, custom = SkinCommandHandler(character_model=model), model.customization
    state = lambda: (custom.hsr_mirror, custom.hsr_hide, custom.hsr_show)
    assert not handler.execute("/skin hsr desfazer")[0] and not handler.execute("/skin hsr refazer")[0]
    handler.execute("/skin hsr esconder 1,2")
    handler.execute("/skin hsr mostrar 2,7")
    handler.execute("/skin hsr espelhar sim")
    assert state() == (True, (1,), (2, 7))
    handler.execute("/skin hsr espelhar sim")                                               # nothing changed: nothing to undo
    assert [len(stack) for stack in handler.hsr_history] == [3, 0]
    assert handler.execute("/skin hsr desfazer")[0] and state() == (False, (1,), (2, 7))
    assert handler.execute("/skin hsr desfazer")[0] and state() == (False, (1, 2), ())
    assert handler.execute("/skin hsr refazer")[0] and state() == (False, (1,), (2, 7))
    handler.execute("/skin hsr limpar")                                                     # a new change: nothing left to redo
    assert state() == (False, (), ()) and not handler.execute("/skin hsr refazer")[0]
    assert handler.execute("/skin hsr desfazer")[0] and state() == (False, (1,), (2, 7))


def test_undo_and_redo_by_keys_and_by_the_arrows_at_the_top_right():
    editor, sent = make_editor()
    CTRL, SHIFT, Z = 2, 1, 90
    assert editor.history_rects(*SIZE) == {} and not editor.handle_key(Z, PRESS, CTRL)       # only in the edit mode
    editor.choose(option(editor, "Editar pele"))
    assert editor.handle_key(Z, PRESS, CTRL) and sent[-1] == "/skin hsr desfazer"
    assert editor.handle_key(Z, PRESS, CTRL | SHIFT) and sent[-1] == "/skin hsr refazer"
    assert not editor.handle_key(Z, PRESS, 0)
    rects = editor.history_rects(*SIZE)
    undo, redo = rects["desfazer"], rects["refazer"]
    assert redo[2] <= SIZE[0] and redo[2] > SIZE[0] - 20 and undo[1] < 20 and undo[2] <= redo[0]   # the top right corner, undo on the left
    count = len(sent)
    assert editor.handle_mouse_button(undo[0] + 5, undo[1] + 5, LEFT, PRESS) and sent[-1] == "/skin hsr desfazer"
    assert editor.handle_mouse_button(undo[0] + 5, undo[1] + 5, LEFT, RELEASE) and len(sent) == count + 1   # one for the click; no stroke
    assert editor.handle_mouse_button(redo[0] + 5, redo[1] + 5, LEFT, PRESS) and sent[-1] == "/skin hsr refazer"
    editor.handler.hsr_history = ([1, 2], [])
    image = np.array(editor.history_image(*SIZE))
    lit = lambda rect: int(image[:, rect[0] - undo[0]:rect[2] - undo[0], :3].max())
    assert lit(undo) > lit(redo)                                                             # the arrow with nothing to do is dim
    legend = np.array(editor.legend_image())
    colours = {tuple(p) for p in legend.reshape(-1, 4)[:, :3].tolist()}
    assert all(tuple(colour) in colours for colour, _ in skin_brush.LEGEND) and len(skin_brush.LEGEND) == 5


def test_transparency_and_the_arms_at_ninety_degrees_are_checks_of_their_own():
    editor, _ = make_editor()
    assert option(editor, "Transparência").check and option(editor, "Braços a 90°").check
    editor.choose(option(editor, "Editar pele"))
    assert editor.model.hsr_edit is True and editor.brushing                                 # painted skin, clear clothes
    editor.choose(option(editor, "Transparência"))
    assert editor.model.hsr_edit is False and editor.hsr_editing and editor.brushing        # as in the game, still painting
    editor.choose(option(editor, "Transparência"))
    assert editor.model.hsr_edit is True
    assert not editor.arms_raised
    editor.choose(option(editor, "Braços a 90°"))
    assert editor.arms_raised                                                                # with or without the edit mode
    editor.select_section(0)
    assert not editor.arms_raised                                                            # only in this section


def test_the_animator_stands_with_the_arms_out_when_asked():
    from src.clothing.character_animation import CharacterAnimator
    from src.clothing.skeleton import Skeleton, rest_rotations
    animator = CharacterAnimator.__new__(CharacterAnimator)
    animator.skeleton, animator.arms_out, animator.arm_swing = Skeleton.load("female"), False, 1.0
    animator.rest = rest_rotations(animator.skeleton)
    down, _ = animator.walk_pose(0.0, 0.0)
    animator.arms_out = True
    out, _ = animator.walk_pose(0.0, 0.0)
    assert not np.allclose(out["UpperArm_L"], down["UpperArm_L"])
    skeleton = animator.skeleton
    arm = skeleton.index("UpperArm_L")
    along = out["UpperArm_L"] @ (skeleton.tails[arm] - skeleton.heads[arm])
    assert abs(along[1]) < 0.02 * np.linalg.norm(along) + 1e-3                                # level: straight out to the side


def test_the_brush_reaches_a_point_out_of_sight_through_the_skin_under_it():
    look = np.identity(4)
    look[2, 3] = -5.0
    projection = np.diag([1 / 4.0, 1 / 4.0, -0.1, 1.0])
    # Skin at x = 0.25, y = 1.1, decided by the cage points 0, 2 and 5; the last is on the far side of the cage.
    skin = (np.array([[0.25, 1.1, 0.1], [0.25, 1.1, -0.6]]), np.array([[0, 2, 5], [1, 3, 4]]),
            np.array([[0.3, 0.3, 0.4], [0.4, 0.3, 0.3]]))
    seen = skin_brush.BrushView(CAGE, None, np.identity(4), look, projection, (400, 0, 1200, 800), skin=skin)
    seen.facing = np.array([True, True, True, True, True, False])
    assert seen.pick(825, 290, 4) == [0, 2, 5]                                              # through the skin: 5 too
    assert seen.pick(825, 290, 4, mirror=True) == [0, 1, 2, 3, 5]
    assert seen.pick(100, 100, 4) == []
    weak = (skin[0], skin[1], np.array([[0.45, 0.45, 0.1], [0.4, 0.3, 0.3]]))               # a point that barely decides it is left
    assert skin_brush.BrushView(CAGE, None, np.identity(4), look, projection, (400, 0, 1200, 800), skin=weak).pick(825, 290, 4) == [0, 2]


def tube(low, high, radius=0.25, sides=12):
    """A tube of cloth around the vertical axis, from the height ``low`` to ``high``."""
    turn = np.linspace(0.0, 2 * np.pi, sides, endpoint=False)
    ring = lambda y: np.column_stack((radius * np.cos(turn), np.full(sides, y), radius * np.sin(turn)))
    heights = np.linspace(low, high, 7)
    vertices = np.concatenate([ring(y) for y in heights])
    faces = []
    for level in range(len(heights) - 1):
        for k in range(sides):
            a, b = level * sides + k, level * sides + (k + 1) % sides
            faces += [[a, b, a + sides], [b, b + sides, a + sides]]
    return vertices, np.array(faces)


def test_the_mask_of_a_moved_edge_is_computed_again_from_the_garment():
    from src.clothing.hsr import recut_mask_edges
    cage, cage_faces = tube(0.6, 1.6, radius=0.15, sides=10)                               # a body: a narrower tube inside
    parts = np.array(["UpperTorso"] * len(cage))
    cloth, faces = tube(1.0, 1.5, radius=0.20)                                              # a top from 1.0 (its hem) to 1.5
    y = cage[:, 1]
    hidden = (y >= 1.0) & (y <= 1.5)
    same = recut_mask_edges(hidden, cage, cage_faces, parts, cloth, faces, [(1.0, 0.0, True)])
    assert same.tolist() == hidden.tolist()                                                 # nothing moved: the mask given
    raised = recut_mask_edges(hidden, cage, cage_faces, parts, cloth, faces, [(1.0, 0.15, True)])
    assert hidden[np.isclose(y, 1.1)].all() and not raised[np.isclose(y, 1.1)].any()        # the skin the hem left shows
    assert raised[(y > 1.2) & (y < 1.45)].all()
    lowered = recut_mask_edges(hidden, cage, cage_faces, parts, cloth, faces, [(1.0, -0.08, True)])
    assert lowered.sum() >= hidden.sum() and lowered[(y > 1.0) & (y < 1.45)].all()          # none lost; more of it covered
    assert not lowered[y < 0.85].any()                                                      # and nothing below where the hem now is
    arms = np.array(["LeftUpperArm"] * len(cage))
    assert recut_mask_edges(hidden, cage, cage_faces, arms, cloth, faces, [(1.0, 0.15, True)]).tolist() == hidden.tolist()
    assert hidden.sum() == ((y >= 1.0) & (y <= 1.5)).sum()                                  # the mask given is not changed


def test_a_garment_slider_moves_the_cloth_while_dragged_and_cuts_the_skin_on_release():
    editor, sent = make_editor()
    calls = []
    editor.handler.recut_skin = lambda: calls.append("recut")
    deferred = []
    execute = editor.handler.execute
    editor.handler.execute = lambda command: (deferred.append(getattr(editor.handler, "defer_skin", False)), execute(command))[1]
    rect = next(r for r, kind, payload in editor.layout(*SIZE) if kind == "option" and payload.slider == "blusa_barra")
    y = (rect[1] + rect[3]) / 2
    assert editor.handle_mouse_button(rect[0] + 140, y, LEFT, PRESS)
    editor.handle_cursor(rect[0] + 170, y)
    editor.handle_cursor(rect[0] + 200, y)
    assert deferred and all(deferred) and calls == []                                       # dragged: cloth only
    assert editor.handle_mouse_button(rect[0] + 200, y, LEFT, RELEASE)
    assert deferred[-1] is False and calls == ["recut"] and editor.handler.defer_skin is False   # let go: the skin, once
    assert sent[-1].startswith("/skin ajuste blusa_barra ")
