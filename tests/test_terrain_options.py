"""As opções de criação do mundo: o gerador delas, a prévia e a tela "Uma nova aventura"."""
import time

import numpy as np

from src.core.game_storage import Preferences, WorldLibrary
from src.interactive.game_menus import GameMenus
from src.world.block import BlockType
from src.world.terrain import TerrainGenerator
from src.world.terrain_options import clean, defaults, generator_settings, make_generator, sea_level_for


def test_sem_opcoes_e_o_gerador_de_sempre():
    assert make_generator(777, None) == TerrainGenerator(seed=777, enable_caves=True, vegetation=True)


def test_padroes_mantem_o_relevo_de_sempre():
    generator = make_generator(777, defaults())
    legacy = TerrainGenerator(seed=777)
    assert all(generator.get_height(x, z) == legacy.get_height(x, z) for x in range(-20, 20, 3) for z in (0, 7))
    assert generator.cave_chance == 0.6 and generator.vegetation_density == 1.0


def test_cavernas_zero_desliga_e_planicie_cem_e_chao_liso():
    generator = make_generator(5, dict(defaults(), cavernas=0, planicie=100))
    assert generator.enable_caves is False
    assert len({generator.get_height(x, z) for x in range(-30, 30, 4) for z in range(-30, 30, 4)}) == 1


def test_agua_e_a_parte_do_chao_coberta():
    heights = np.arange(100)
    assert sea_level_for(heights, 0.3) == 30
    levels = [generator_settings(777, dict(defaults(), agua=a))['sea_level'] for a in (0, 25, 50, 75, 100)]
    assert levels == sorted(levels) and levels[0] < levels[-1]


def test_vegetacao_zero_nao_planta_nada():
    chunks = make_generator(777, dict(defaults(), vegetacao=0, cavernas=0)).generate_region(
        [(x, 0, z) for x in range(2) for z in range(2)])
    plants = [int(BlockType.SHORT_GRASS), int(BlockType.POPPY), int(BlockType.DANDELION)]
    assert not any(np.isin(chunk.blocks, plants).any() for chunk in chunks.values())


def test_clean_limita_e_completa():
    assert clean({'agua': 140, 'cavernas': -3, 'relevo': 'x'}) == dict(defaults(), agua=100, cavernas=0)
    assert clean(None) is None


def test_mundo_guarda_as_opcoes(tmp_path):
    world = WorldLibrary(tmp_path).create('Ilha', '12', {'agua': 70})
    assert world['terrain'] == dict(defaults(), agua=70)
    assert WorldLibrary(tmp_path).list()[0]['terrain']['agua'] == 70


def test_previa_desenha_o_recorte():
    from src.interactive.world_preview import AREA, build
    image = build(777, dict(defaults(), cavernas=0))
    assert image.width > AREA * 4 and image.getbbox() is not None


def _menus(tmp_path):
    from src.interactive import world_preview
    menus = GameMenus('t', Preferences(tmp_path / 'p.json'), WorldLibrary(tmp_path / 'w'), create_gl=False)
    menus.preview = world_preview.PreviewWorker(builder=lambda seed, options: None)
    return menus


def test_opcao_arrasta_e_anda_com_as_setas(tmp_path):
    import glfw
    menus = _menus(tmp_path)
    menus.go('create')
    menus.render(1320, 876)
    rect = next(r for r, a in menus.hits if a == 'slider:agua')
    menus.mouse_button(rect[0] + (rect[2] - rect[0]) * 0.8, (rect[1] + rect[3]) / 2, glfw.PRESS)
    assert menus.terrain['agua'] == 80
    menus.hover(rect[0], rect[1])                 # arrastando até o começo da trilha
    menus.mouse_button(rect[0], rect[1], glfw.RELEASE)
    assert menus.terrain['agua'] == 0
    menus.focus = menus.hits_order.index('slider:cavernas')
    menus.key(glfw.KEY_LEFT, glfw.PRESS)
    assert menus.terrain['cavernas'] == 55


def test_criar_usa_a_seed_e_as_opcoes_da_previa(tmp_path):
    menus = _menus(tmp_path)
    menus.go('create')
    menus.terrain['cavernas'] = 10
    shown = menus.preview_seed
    menus.fields['name'] = 'Prévia'
    menus.activate('create_world')
    assert menus.result[1]['seed'] == shown
    assert menus.result[1]['terrain']['cavernas'] == 10


def test_sair_da_criacao_volta_as_opcoes(tmp_path):
    menus = _menus(tmp_path)
    menus.go('create')
    menus.terrain['agua'] = 90
    menus.activate('back')
    menus.activate('create')
    assert menus.terrain == defaults()


def test_previa_na_thread_fica_com_o_ultimo_pedido():
    from src.interactive.world_preview import PreviewWorker
    seen = []
    worker = PreviewWorker(builder=lambda seed, options: (time.sleep(0.02), seen.append(seed))[1] or seed)
    for seed in (1, 2, 3):
        worker.request(seed, {})
    for _ in range(200):
        if not worker.pending:
            break
        time.sleep(0.01)
    assert worker.image() == 3 and seen[-1] == 3


# ---------------------------------------------------------------- biomas

def _digest(generator):
    import hashlib
    chunks = generator.generate_region([(cx, cy, 0) for cx in range(-1, 2) for cy in range(-1, 2)])
    return hashlib.sha256(b"".join(chunks[k].blocks.tobytes() for k in sorted(chunks))).hexdigest()


def test_planicie_igual_a_de_antes():
    # gravado antes dos biomas: um mundo sem bioma (ou com as opções padrão) não pode mudar um bloco
    assert _digest(make_generator(329436, None)) == "a0b063f5f3c8e4d36c8a382b8d6ef4b569e05896e11b1d79157d5c3dae7ae9dd"
    assert _digest(make_generator(329436, defaults())) == "a0b063f5f3c8e4d36c8a382b8d6ef4b569e05896e11b1d79157d5c3dae7ae9dd"


def test_bioma_nas_opcoes():
    import pytest
    from src.world.terrain_options import water_default
    assert clean({"bioma": "deserto"})["bioma"] == "deserto"
    assert clean({"bioma": "lua"})["bioma"] == "planicie"
    assert clean({})["bioma"] == "planicie"
    assert water_default("deserto") == 5 and water_default("taiga") == 20
    assert make_generator(1, {"bioma": "taiga"}).biome == "taiga"
    assert make_generator(1, None).biome == "planicie"
    with pytest.raises(ValueError):
        TerrainGenerator(biome="lua")


def test_escolher_o_bioma_na_criacao(tmp_path):
    menus = _menus(tmp_path)
    menus.go('create')
    menus.render(1320, 876)
    actions = [a for _, a in menus.hits]
    assert {'biome:planicie', 'biome:deserto', 'biome:taiga'} <= set(actions)
    menus.activate('biome:deserto')
    assert menus.terrain['bioma'] == 'deserto' and menus.terrain['agua'] == 5
    menus.activate('biome:taiga')
    assert menus.terrain['bioma'] == 'taiga' and menus.terrain['agua'] == 20
    menus.fields['name'] = 'Pinheiros'
    menus.activate('create_world')
    assert menus.result[1]['terrain']['bioma'] == 'taiga'
    menus.go('create')
    menus.activate('biome:deserto')
    menus.activate('terrain_defaults')
    assert menus.terrain['bioma'] == 'planicie'


def test_previa_do_deserto_tem_areia():
    from src.interactive.world_preview import COLORS, build
    image = build(777, dict(defaults(), bioma='deserto', cavernas=0)).convert('RGB')
    sand = COLORS[int(BlockType.SAND)]
    pixels = set(map(tuple, np.asarray(image).reshape(-1, 3).tolist()))
    assert any(max(abs(p[i] - sand[i]) for i in range(3)) < 40 for p in pixels)
