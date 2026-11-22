"""Desenho em coordenadas lógicas com rasterização em 2x.

As HUDs são desenhadas em um canvas lógico e apresentadas pelo OpenGL. Em telas
Retina, desenhar o canvas em 1x e deixar a GPU ampliar borra a fonte. Este
adaptador mantém as coordenadas/hitboxes lógicas, mas desenha em 2x; a textura
pronta volta a ser reduzida para o tamanho lógico no ``HudQuad``.
"""

from __future__ import annotations

RENDER_SCALE = 2


class ScaledDraw:
    def __init__(self, target, scale: int = RENDER_SCALE) -> None:
        self.target = target
        self.scale = scale

    def _point(self, value):
        return tuple(round(float(v) * self.scale) for v in value)

    def text(self, xy, text, font=None, fill=None, **kwargs):
        return self.target.text(self._point(xy), text, font=font, fill=fill, **kwargs)

    def textbbox(self, xy, text, font=None, **kwargs):
        return self.target.textbbox(self._point(xy), text, font=font, **kwargs)

    def rounded_rectangle(self, xy, radius=0, fill=None, outline=None, width=1):
        return self.target.rounded_rectangle(
            self._point(xy), radius=round(radius * self.scale), fill=fill,
            outline=outline, width=max(1, round(width * self.scale)),
        )

    def rectangle(self, xy, fill=None, outline=None, width=1):
        return self.target.rectangle(
            self._point(xy), fill=fill, outline=outline,
            width=max(1, round(width * self.scale)),
        )

    def ellipse(self, xy, fill=None, outline=None, width=1):
        return self.target.ellipse(
            self._point(xy), fill=fill, outline=outline,
            width=max(1, round(width * self.scale)),
        )

    def line(self, xy, fill=None, width=1):
        return self.target.line(
            self._point(xy), fill=fill, width=max(1, round(width * self.scale)),
        )

    def polygon(self, xy, fill=None):
        return self.target.polygon(self._point(xy), fill=fill)
