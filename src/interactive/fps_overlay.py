"""O contador de FPS do HUD (Configurações > Mostrar FPS): ``60 fps``, na fonte do Minecraft quando o jogo dela existe."""

from __future__ import annotations

from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from src.rendering.mc_font import default_font

INTERVAL = 0.5       # segundos entre uma leitura e outra: o número não pisca a cada quadro


class FpsOverlay:
    MARGIN = 12      # pixels da borda da janela
    SCALE = 2

    def __init__(self) -> None:
        self.font = default_font()
        self.frames = 0
        self.elapsed = 0.0
        self.fps = 0.0
        self._quad = None
        self._text: Optional[str] = None

    def update(self, dt: float) -> None:
        """Conta um quadro que durou ``dt`` segundos; a leitura se renova a cada meio segundo."""
        self.frames += 1
        self.elapsed += max(float(dt), 0.0)
        if self.elapsed >= INTERVAL:
            self.fps = self.frames / self.elapsed
            self.frames, self.elapsed = 0, 0.0

    @property
    def text(self) -> str:
        return f"{round(self.fps)} fps"

    def _image(self, text: str) -> Image.Image:
        if self.font is not None:
            return self.font.render(text, scale=self.SCALE)
        font = ImageFont.load_default()          # sem a fonte do jogo: a de reserva do PIL, branca com sombra
        image = Image.new("RGBA", (8 * len(text) + 2, 14), (0, 0, 0, 0))
        pen = ImageDraw.Draw(image)
        pen.text((1, 1), text, font=font, fill=(40, 40, 40, 255))
        pen.text((0, 0), text, font=font, fill=(255, 255, 255, 255))
        return image

    def render(self, width: int, height: int, top: float = MARGIN) -> None:
        """Desenha o contador com o canto de cima à esquerda em (``MARGIN``, ``top``)."""
        from src.rendering.hud_quad import HudQuad
        if self._quad is None:
            self._quad = HudQuad()
        text = self.text
        if text != self._text:
            self._quad.set_image(self._image(text))
            self._text = text
        self._quad.draw(self.MARGIN, top, width, height)

    def delete(self) -> None:
        if self._quad is not None:
            self._quad.delete()
            self._quad = None
