"""Modo apresentação: os slides, a navegação, as teclas e o que cada slide pede à câmera."""
import glfw
import numpy as np
import pytest

from src.interactive.presentation import Presentation, face_stats
from src.interactive.presentation_slides import SLIDES
from src.world.block import BlockType


def _all_text():
    return "\n".join(line for s in SLIDES for b in s.blocks for line in (s.title, *b.content))


def test_treze_slides_com_titulos_acentuados():
    assert len(SLIDES) == 13
    titles = " | ".join(s.title for s in SLIDES)
    for word in ("Isometricon", "Ferramentas", "Geração procedural", "Face culling", "Câmera", "Conclusão"):
        assert word in titles
    assert "Obrigado!" in SLIDES[-1].blocks[-1].content[-1]


def test_capa_tem_autores_e_instituicao():
    text = "\n".join(line for b in SLIDES[0].blocks for line in b.content)
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
    assert p.index == 12


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
    assert p.key(glfw.KEY_END, glfw.PRESS) is True and p.index == 12
    assert p.key(glfw.KEY_HOME, glfw.PRESS) is True and p.index == 0
    assert p.key(glfw.KEY_H, glfw.PRESS) is True and p.card_visible is False
    p.key(glfw.KEY_H, glfw.PRESS)
    assert p.card_visible is True
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
    assert Presentation(start=99).index == 12
    assert Presentation(start=-3).index == 0


def _at(index, seconds):
    p = Presentation(start=index)
    p.update(seconds)
    return p.camera_targets(45.0, 10.0)


def test_alvos_camera():
    assert _at(8, 4.1).yaw_degrees == pytest.approx(45.0 + 90.0)
    assert _at(9, 7.0).ortho_size == pytest.approx(30.0)
    assert _at(9, 0.0).ortho_size == pytest.approx(10.0)
    assert _at(7, 3.5).debug_view == 1
    assert _at(7, 6.5).debug_view == 2
    assert _at(6, 1.0).wireframe is True
    calm = _at(2, 1.0)
    assert calm.debug_view == 0 and calm.perspective is False and calm.wireframe is False
    assert _at(8, 9.0).perspective is True
    assert _at(8, 1.0).perspective is False
    spin = _at(0, 2.0)
    assert spin.yaw_degrees > 45.0


def test_face_stats():
    full = np.full((16, 16, 16), int(BlockType.STONE), dtype=np.uint8)
    assert face_stats([full], [6 * 16 * 16 * 6]) == (1536, 24576)
    assert face_stats([], []) == (0, 0)
    air_and_plants = np.zeros((16, 16, 16), dtype=np.uint8)
    air_and_plants[0, 0, 0] = int(BlockType.POPPY)   # blocos com forma não contam como cubos
    assert face_stats([air_and_plants], []) == (0, 0)
