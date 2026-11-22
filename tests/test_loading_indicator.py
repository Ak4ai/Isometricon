"""O diamante de carregamento: aparece enquanto algo carrega, recomeça a cada vez e some esmaecendo."""

from PIL import Image

from src.interactive.loading_indicator import FADE, FPS, FRAMES_DIR, SIZE, LoadingIndicator, load_frames


def make_frames(directory, count=4):
    for i in range(count):
        Image.new("RGBA", (64, 64), (i, 0, 0, 255)).save(directory / f"loading_{i:05d}.png")


def test_the_game_frames_load_small_and_transparent():
    frames = load_frames(FRAMES_DIR)
    assert len(frames) == 108
    assert all(frame.size == (SIZE, SIZE) and frame.mode == "RGBA" for frame in frames)
    assert frames[0].getpixel((0, 0))[3] == 0                     # o fundo é transparente


def test_it_fades_in_while_busy_restarts_and_fades_out(tmp_path):
    make_frames(tmp_path)
    state = {"busy": ""}
    indicator = LoadingIndicator(lambda: state["busy"], directory=tmp_path, background=False)
    indicator.update(1.0)
    assert not indicator.visible                                   # nada carregando: nada na tela
    state["busy"] = "Ajustando roupas ao corpo..."
    indicator.update(FADE / 2)
    assert indicator.visible and 0.4 < indicator.alpha < 0.6
    indicator.update(FADE)
    assert indicator.alpha == 1.0
    indicator.update(2 / FPS)
    assert indicator.frame_index == int((FADE * 1.5 + 2 / FPS) * FPS) % 4
    state["busy"] = ""
    indicator.update(FADE * 2)
    assert indicator.alpha == 0.0 and not indicator.visible
    state["busy"] = "Importando 1..."
    indicator.update(0.0)
    assert indicator.time == 0.0 and indicator.frame_index == 0    # volta do primeiro quadro


def test_without_frames_it_never_shows(tmp_path):
    indicator = LoadingIndicator(lambda: "ocupado", directory=tmp_path / "nada", background=False)
    indicator.update(1.0)
    assert not indicator.visible
