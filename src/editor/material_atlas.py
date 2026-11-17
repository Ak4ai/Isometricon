"""Atlas de materiais do editor: 16 tiles 16x16 em uma textura 4x4.

O terreno usa o atlas fixo de ``src.rendering.atlas``; o editor aceita uma
paleta de texturas por voxel, então tem o seu próprio atlas, montado a partir
dos mesmos PNGs de bloco.
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np
from PIL import Image

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_TEXTURES_DIR = os.path.join(PROJECT_ROOT, "assets", "textures", "blocks")

# Texturas reconhecíveis e opacas, uma por tile do atlas 4x4.
TILE_NAMES = (
    "white_concrete",
    "stone",
    "cobblestone",
    "stone_bricks",
    "oak_planks",
    "spruce_planks",
    "bricks",
    "sandstone",
    "dirt",
    "grass_block_side",
    "oak_log",
    "red_concrete",
    "blue_concrete",
    "yellow_concrete",
    "green_concrete",
    "black_concrete",
)


class MaterialAtlas:
    """Atlas 4x4 de tiles de 16x16, com consulta de UV por nome de textura."""

    TILE_SIZE = 16
    GRID_COLS = 4
    GRID_ROWS = 4

    def __init__(self, textures_dir: Optional[str] = None, create_gl: bool = False) -> None:
        self.textures_dir = textures_dir or DEFAULT_TEXTURES_DIR
        self.tile_names = list(TILE_NAMES)
        self.tile_rects: dict[str, tuple[float, float, float, float]] = {}
        self._gl_texture_id: Optional[int] = None
        self.atlas_image = self._build_image()
        if create_gl:
            self.load_gl_texture()

    def _build_image(self) -> Image.Image:
        width = self.GRID_COLS * self.TILE_SIZE
        height = self.GRID_ROWS * self.TILE_SIZE
        atlas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        for index, name in enumerate(self.tile_names):
            column, row = index % self.GRID_COLS, index // self.GRID_COLS
            path = os.path.join(self.textures_dir, f"{name}.png")
            if os.path.exists(path):
                tile = Image.open(path).convert("RGBA")
                if tile.size != (self.TILE_SIZE, self.TILE_SIZE):
                    tile = tile.resize((self.TILE_SIZE, self.TILE_SIZE), Image.Resampling.NEAREST)
            else:
                tile = self._checker()
            atlas.paste(tile, (column * self.TILE_SIZE, row * self.TILE_SIZE))
            # O OpenGL recebe a imagem invertida; a linha lógica vira a linha de V.
            gl_row = self.GRID_ROWS - 1 - row
            self.tile_rects[name] = (
                column / self.GRID_COLS,
                gl_row / self.GRID_ROWS,
                (column + 1) / self.GRID_COLS,
                (gl_row + 1) / self.GRID_ROWS,
            )
        return atlas

    def _checker(self) -> Image.Image:
        tile = Image.new("RGBA", (self.TILE_SIZE, self.TILE_SIZE), (230, 230, 230, 255))
        pixels = tile.load()
        for y in range(self.TILE_SIZE):
            for x in range(self.TILE_SIZE):
                if (x // 4 + y // 4) % 2:
                    pixels[x, y] = (200, 60, 200, 255)
        return tile

    def uv_for(self, texture: str) -> tuple[float, float, float, float]:
        """Retângulo UV (u0, v0, u1, v1) do tile, com fallback branco."""
        return self.tile_rects.get(str(texture), self.tile_rects["white_concrete"])

    def next_texture(self, current: str, step: int = 1) -> str:
        names = self.tile_names
        try:
            index = names.index(current)
        except ValueError:
            index = 0
        return names[(index + step) % len(names)]

    def load_gl_texture(self) -> int:
        if self._gl_texture_id is not None:
            return self._gl_texture_id
        import OpenGL.GL as gl

        texture = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
        image = self.atlas_image.transpose(Image.FLIP_TOP_BOTTOM)
        data = np.asarray(image, dtype=np.uint8)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, image.width, image.height, 0,
                        gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, data)
        self._gl_texture_id = texture
        return texture

    @property
    def texture_id(self) -> int:
        if self._gl_texture_id is None:
            return self.load_gl_texture()
        return self._gl_texture_id

    def delete(self) -> None:
        if self._gl_texture_id is not None:
            import OpenGL.GL as gl
            gl.glDeleteTextures(1, [self._gl_texture_id])
            self._gl_texture_id = None
