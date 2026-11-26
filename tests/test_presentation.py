import os
"""Modo apresentação: os slides, a navegação, as teclas e o que cada slide pede à câmera."""
import glfw
import numpy as np
import pytest

from src.interactive.presentation import Presentation, face_stats
from src.interactive.presentation_slides import SLIDES
from src.world.block import BlockType


LAST = len(SLIDES) - 1


def _index(title):
    return next(i for i, s in enumerate(SLIDES) if s.title == title)


def _all_text():
    return "\n".join(line for s in SLIDES for p in s.panels for b in p.blocks
                     for line in (s.title, p.title, *b.content))


def test_slides_com_titulos_acentuados():
    assert 12 <= len(SLIDES) <= 22
    titles = " | ".join(s.title for s in SLIDES)
    for word in ("Isometricon", "Ferramentas", "Pipeline", "Mundo", "Câmera", "Iluminação", "Personagens",
                 "Interação", "Otimizações", "Conclusão"):
        assert word in titles
    assert "Obrigado!" in SLIDES[-1].panels[-1].blocks[-1].content[-1]


def test_cada_parte_cita_os_recursos_de_cg():
    # o pedido do professor: mostrar onde cada recurso de computação gráfica é usado
    for s in SLIDES[3:-1]:
        if s.title == "Otimizações":
            continue
        assert any(b.kind == "tags" and b.content for p in s.panels for b in p.blocks), s.title
    tags = {t for s in SLIDES for p in s.panels for b in p.blocks if b.kind == "tags" for t in b.content}
    for resource in ("Rotação", "Translação", "Escala", "Iluminação difusa", "Shadow mapping",
                     "Esqueleto e skinning", "Raycasting", "Transparência e blending", "Projeção ortográfica"):
        assert resource in tags


def test_capa_tem_autores_e_instituicao():
    text = "\n".join(line for p in SLIDES[0].panels for b in p.blocks for line in b.content)
    for name in ("Henrique de Freitas Araujo", "João Pedro Rodrigues Silva", "Pedro Augusto Gontijo Moura",
                 "CEFET-MG", "Divinópolis", "2026"):
        assert name in text


def test_formulas_preservadas():
    text = _all_text()
    for piece in ("Σ", "⊙", "P·V·M", "44 B", "4096", "35,264°", "M = T·R·S"):
        assert piece in text


def test_next_prev_limites():
    p = Presentation()
    p.prev()
    assert (p.index, p.step) == (0, 0)
    p.last()
    p.next()
    assert p.index == LAST


def test_pipeline_avanca_por_passos():
    p = Presentation(start=3)
    assert SLIDES[3].steps == 5
    for _ in range(4):
        p.next()
    assert (p.index, p.step) == (3, 4)
    p.next()
    assert (p.index, p.step) == (4, 0)
    p.prev()
    assert (p.index, p.step) == (3, 4)


def test_teclas_consumidas():
    p = Presentation()
    assert p.key(glfw.KEY_RIGHT, glfw.PRESS) is True
    assert p.index == 1
    assert p.key(glfw.KEY_SPACE, glfw.PRESS) is True
    assert p.key(glfw.KEY_PAGE_DOWN, glfw.REPEAT) is True
    assert p.index == 3
    assert p.key(glfw.KEY_RIGHT, glfw.RELEASE) is False
    assert p.index == 3
    assert p.key(glfw.KEY_W, glfw.PRESS) is False
    assert p.key(glfw.KEY_LEFT, glfw.PRESS) is True
    assert p.key(glfw.KEY_PAGE_UP, glfw.PRESS) is True
    assert p.index == 1
    assert p.key(glfw.KEY_END, glfw.PRESS) is True and p.index == LAST
    assert p.key(glfw.KEY_HOME, glfw.PRESS) is True and p.index == 0
    assert p.key(glfw.KEY_H, glfw.PRESS) is True and p.card_visible is False
    p.key(glfw.KEY_H, glfw.PRESS)
    assert p.card_visible is True
    assert p.fullscreen is True
    assert p.key(glfw.KEY_F11, glfw.PRESS) is True and p.fullscreen is False
    assert p.key(glfw.KEY_ESCAPE, glfw.PRESS) is True
    assert p.active is False
    assert p.key(glfw.KEY_RIGHT, glfw.PRESS) is False


def test_elapsed_zera_ao_trocar():
    p = Presentation()
    p.update(5.0)
    assert p.elapsed == pytest.approx(5.0)
    p.next()
    assert p.elapsed == 0.0


def test_slide_inicial_fora_do_intervalo_e_limitado():
    assert Presentation(start=99).index == LAST
    assert Presentation(start=-3).index == 0


def _at(index, seconds):
    p = Presentation(start=index)
    p.update(seconds)
    return p.camera_targets(45.0, 10.0)


def test_alvos_camera():
    camera, light = _index("Câmera e transformações"), _index("Iluminação e sombras")
    optimizations, mesh = _index("Otimizações"), _index("Mundo: malha e texturas")
    assert _at(camera, 4.1).yaw_degrees == pytest.approx(45.0 + 90.0)
    assert _at(optimizations, 7.0).ortho_size == pytest.approx(30.0)
    assert _at(optimizations, 0.0).ortho_size == pytest.approx(10.0)
    assert _at(light, 3.5).debug_view == 0
    assert _at(light, 6.5).debug_view == 1
    assert _at(light, 9.5).debug_view == 2
    assert _at(mesh, 1.0).wireframe is True
    calm = _at(2, 1.0)
    assert calm.debug_view == 0 and calm.perspective is False and calm.wireframe is False
    assert _at(camera, 9.0).perspective is True
    assert _at(camera, 1.0).perspective is False
    spin = _at(0, 2.0)
    assert spin.yaw_degrees > 45.0


def test_face_stats():
    full = np.full((16, 16, 16), int(BlockType.STONE), dtype=np.uint8)
    assert face_stats([full], [6 * 16 * 16 * 6]) == (1536, 24576)
    assert face_stats([], []) == (0, 0)
    air_and_plants = np.zeros((16, 16, 16), dtype=np.uint8)
    air_and_plants[0, 0, 0] = int(BlockType.POPPY)   # blocos com forma não contam como cubos
    assert face_stats([air_and_plants], []) == (0, 0)


def test_composicoes_variam():
    boxes = {tuple(p.box) for s in SLIDES for p in s.panels}
    assert len(boxes) >= 6                                  # colunas, faixa, cantos e centro
    assert sum(len(s.panels) > 1 for s in SLIDES) >= 4      # slides com mais de um cartão
    for s in SLIDES:
        for p in s.panels:
            x, y, w, h = p.box
            assert 0 <= x and 0 <= y and x + w <= 1.0001 and y + h <= 1.0001, (s.title, p.box)


def test_graficos_ao_vivo_tem_contador():
    for s in SLIDES:
        for p in s.panels:
            for b in p.blocks:
                if b.kind == "bars":
                    assert b.content[0] in s.scene.counters, s.title


def test_slides_abrem_as_telas_do_jogo():
    screens = {s.title: s.scene.screen for s in SLIDES}
    assert screens["Personagens e animação"] == "editor"
    assert screens["Combate por turnos"] == "combate"
    assert screens["Iluminação e sombras"] == screens["Água e névoa"] == "mestre"
    assert screens["Interação"] == ""                     # o painel de construções não entra na apresentação
    assert set(screens.values()) <= {"", "editor", "mestre", "combate"}


def test_lugares_um_por_passo():
    from src.interactive.presentation_places import CAVE, ENTRIES
    rooms = SLIDES[_index("Câmera dentro dos cômodos")]
    assert rooms.scene.places == ("sala-andar", CAVE, "house-medieval")
    assert rooms.steps == len(rooms.scene.places)
    assert SLIDES[_index("Blocos: modelos e sombras")].scene.places == ("formas",)
    for slide in SLIDES:
        for place in slide.scene.places:
            assert place == CAVE or place in ENTRIES
    for entry in ENTRIES.values():
        if entry["kind"] == "schem":
            assert os.path.isfile(os.path.join("assets", "schematics", entry["name"] + ".schem"))


def test_slides_em_outros_biomas():
    from src.interactive.presentation_slides import SceneCue
    from src.world.terrain_options import BIOMES
    assert SceneCue().biome == ""
    assert SLIDES[_index("Mundo: modelagem")].scene.biome == "deserto"
    assert SLIDES[_index("Iluminação e sombras")].scene.biome == "taiga"
    assert all(s.scene.biome in ("",) + BIOMES for s in SLIDES)
