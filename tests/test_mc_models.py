"""Testes das caixas lidas dos modelos do Minecraft (pulam sem a cópia local de ``assets/minecraft_models``)."""

import itertools

import numpy as np
import pytest

from src.rendering.mc_models import LOCAL_MODELS, MinecraftModels, has_local_models, _rotate_box
from src.world import block_shapes as bs

pytestmark = pytest.mark.skipif(not has_local_models(), reason="sem assets/minecraft_models")


@pytest.fixture(scope="module")
def models():
    return MinecraftModels(LOCAL_MODELS)


def voxels(boxes):
    cells = np.zeros((32, 32, 32), dtype=bool)
    for lo, hi in boxes:
        a, b = [int(round(v * 2)) for v in lo], [int(round(v * 2)) for v in hi]
        cells[a[0]:b[0], a[1]:b[1], a[2]:b[2]] = True
    return cells


def own(name):
    return [(b.lo, b.hi) for b in (bs.shape_for(name) or ()) if isinstance(b, bs.Box)]


def test_rotate_box_follows_the_blockstate_turns():
    assert _rotate_box((0, 0, 0), (16, 8, 16), 2, 0) == ((0.0, 8.0, 0.0), (16.0, 16.0, 16.0))       # x180: de cabeça para baixo
    assert _rotate_box((8, 8, 0), (16, 16, 16), 0, 1) == ((0.0, 8.0, 8.0), (16.0, 16.0, 16.0))       # y90: leste -> sul


def test_cubes_and_blocks_without_box_models_have_no_boxes(models):
    assert models.boxes("minecraft:stone") == []             # cubo inteiro
    assert models.boxes("minecraft:oak_leaves[distance=1]") == []
    assert models.boxes("minecraft:not_a_block") is None


def test_the_hand_made_shapes_match_the_game_for_every_state():
    """Degraus, lajes, alçapões, cercas e muros: as caixas daqui são idênticas às do modelo do jogo."""
    models = MinecraftModels(LOCAL_MODELS)
    names = []
    for facing, half, shape in itertools.product(("north", "east", "south", "west"), ("bottom", "top"),
                                                 ("straight", "inner_left", "inner_right", "outer_left", "outer_right")):
        names.append(f"minecraft:oak_stairs[facing={facing},half={half},shape={shape}]")
    names += [f"minecraft:oak_slab[type={t}]" for t in ("bottom", "top")]
    names += [f"minecraft:oak_trapdoor[facing={f},half={h},open={o}]"
              for f, h, o in itertools.product(("north", "east", "south", "west"), ("bottom", "top"), ("true", "false"))]
    names += [f"minecraft:oak_fence[east={e},north={n},south={s},west={w}]"
              for e, n, s, w in itertools.product(("true", "false"), repeat=4)]
    names += [f"minecraft:cobblestone_wall[east={e},north={n},south={s},west={w},up=true]"
              for e, n, s, w in itertools.product(("none", "low", "tall"), repeat=4)]
    for name in names:
        game = models.boxes(name)
        if game:
            assert np.array_equal(voxels(game), voxels(own(name))), name
    models.close()


def test_blocks_without_a_rule_get_their_shape_from_the_models():
    boxes = own("minecraft:hopper[facing=down]")
    assert len(boxes) == 7 and bs.shape_for("minecraft:hopper[facing=down]") is not None
    assert bs.shape_for("minecraft:cauldron") is not None and not bs.is_full_cube("minecraft:cauldron")
    assert bs.is_full_cube("minecraft:stone")
