"""O diamante animado do canto superior direito enquanto algo carrega em segundo plano (roupa, importação).

Os quadros são os PNGs transparentes de ``assets/loading/frames`` (a animação feita no effectcraft), reduzidos
uma vez, numa thread, para o tamanho do HUD. Aparece e some com um esmaecimento curto e recomeça do primeiro
quadro cada vez que volta a aparecer.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, List, Optional

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
FRAMES_DIR = ROOT / "assets" / "loading" / "frames"
FPS = 30            # o ritmo em que a animação foi feita
SIZE = 44           # pixels na tela
FADE = 0.2          # segundos para aparecer ou sumir
MARGIN = 12         # da borda da janela, como as coordenadas
# os quadros têm 512x512 mas o boneco pronto ocupa só o meio (x 144..368, y 70..446): recorta o quadrado em volta
# dele para ele encher o ícone; as peças que entram de fora do recorte só aparecem ao chegar perto
CROP = (68, 70, 444, 446)


def load_frames(directory: Path = FRAMES_DIR, size: int = SIZE) -> List[Image.Image]:
    """Os quadros da animação, em ordem, já no tamanho do HUD (vazio se a pasta não existe)."""
    frames = []
    for path in sorted(Path(directory).glob("loading_*.png")):
        image = Image.open(path).convert("RGBA")
        if image.size == (512, 512):
            image = image.crop(CROP)
        frames.append(image.resize((size, size), Image.LANCZOS))
    return frames


class LoadingIndicator:
    """``busy()`` diz se há algo carregando; ``update`` anima e ``render`` desenha no canto."""

    def __init__(self, busy: Callable[[], object], directory: Path = FRAMES_DIR, size: int = SIZE,
                 background: bool = True) -> None:
        self._busy = busy
        self.size = size
        self.frames: List[Image.Image] = []
        self.time = 0.0
        self.alpha = 0.0
        self._quad = None
        self._shown: Optional[int] = None
        if background:
            threading.Thread(target=self._load, args=(directory,), daemon=True, name="loading-frames").start()
        else:
            self._load(directory)

    def _load(self, directory: Path) -> None:
        try:
            self.frames = load_frames(directory, self.size)
        except Exception as exc:   # sem os quadros o jogo segue, só sem o indicador
            print(f"[LoadingIndicator] Não deu para ler os quadros: {exc}")

    @property
    def visible(self) -> bool:
        return self.alpha > 0.0 and bool(self.frames)

    @property
    def frame_index(self) -> int:
        return int(self.time * FPS) % len(self.frames) if self.frames else 0

    def update(self, dt: float) -> None:
        dt = max(float(dt), 0.0)
        target = 1.0 if self._busy() else 0.0
        if self.alpha <= 0.0 and target > 0.0:
            self.time = 0.0                      # cada carregamento começa a animação do início
        step = dt / FADE
        self.alpha = min(target, self.alpha + step) if target > self.alpha else max(target, self.alpha - step)
        if self.alpha > 0.0:
            self.time += dt

    def render(self, width: int, height: int) -> None:
        """Desenha no canto de cima à direita da janela."""
        if not self.visible:
            return
        from src.rendering.hud_quad import HudQuad
        if self._quad is None:
            self._quad = HudQuad()
        index = self.frame_index
        if index != self._shown:
            self._quad.set_image(self.frames[index])
            self._shown = index
        self._quad.draw(width - MARGIN - self.size, MARGIN, width, height, opacity=self.alpha)

    def delete(self) -> None:
        if self._quad is not None:
            self._quad.delete()
            self._quad = None
