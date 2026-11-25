"""Texture Atlas procedural para blocos de voxel no Isometricon.

Costura as texturas individuais de assets/textures/blocks em um atlas único 2D,
gerando tabelas pré-computadas de coordenadas UV e cores de modulação (tint)
por (BlockType, face) em arrays NumPy ultrarrápidos para o ChunkMesher.
"""

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from src.world.block import SHAPED_BLOCK_NAMES, BlockType, get_block_color

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEXTURES_DIR = os.path.abspath(
    os.path.join(CURRENT_DIR, "..", "..", "assets", "textures", "blocks")
)

# UVs canônicas das faces do mesher
_UVS = np.array([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)], dtype=np.float32)
_TOP_UVS = np.array([(0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)], dtype=np.float32)

# Lista ordenada de texturas empacotadas no atlas
ATLAS_TILES: List[str] = [
    "grass_block_top",      # 0
    "grass_block_side",     # 1
    "dirt",                 # 2
    "stone",                # 3
    "oak_log",              # 4
    "oak_log_top",          # 5
    "oak_leaves",           # 6
    "water_still",          # 7
    "bedrock",              # 8
    "cobblestone",          # 9
    "sand",                 # 10
    "white_concrete",       # 11
    # Os blocos com forma (plantas em cruz, tocha, escada de mão, fogo)
    "short_grass",          # 12
    "poppy",                # 13
    "dandelion",            # 14
    "red_mushroom",         # 15
    "brown_mushroom",       # 16
    "torch",                # 17
    "ladder",               # 18
    "fire_0",               # 19
    # Deserto e taiga
    "sandstone",            # 20
    "sandstone_top",        # 21
    "sandstone_bottom",     # 22
    "cactus_side",          # 23
    "cactus_top",           # 24
    "cactus_bottom",        # 25
    "dead_bush",            # 26
    "spruce_log",           # 27
    "spruce_log_top",       # 28
    "spruce_leaves",        # 29
    "podzol_top",           # 30
    "podzol_side",          # 31
    "fern",                 # 32
    "large_fern_bottom",    # 33
    "large_fern_top",       # 34
    "sweet_berry_bush_stage3",  # 35
]


def shaped_texture(block: BlockType) -> str:
    """A textura do bloco com forma (a do primeiro plano ou caixa da forma)."""
    from src.world.block_shapes import parse_block, shape_for
    parts = shape_for(SHAPED_BLOCK_NAMES[block]) or ()
    base, _ = parse_block(SHAPED_BLOCK_NAMES[block])
    return next((p.texture for p in parts if p.texture), base)


class TextureAtlas:
    """Atlas de texturas consolidado em um único mapa 2D para renderização de blocos."""

    TILE_SIZE = 16
    GRID_COLS = 8
    GRID_ROWS = 8

    def __init__(
        self,
        textures_dir: Optional[str] = None,
        create_gl: bool = False,
    ) -> None:
        self.textures_dir = textures_dir or DEFAULT_TEXTURES_DIR
        self._gl_texture_id: Optional[int] = None

        self._build_atlas_image()
        self._build_tables()

        if create_gl:
            self.load_gl_texture()

    def _build_atlas_image(self) -> None:
        """Carrega e costura os PNGs em uma única imagem PIL RGBA."""
        atlas_width = self.GRID_COLS * self.TILE_SIZE
        atlas_height = self.GRID_ROWS * self.TILE_SIZE
        self.atlas_image = Image.new("RGBA", (atlas_width, atlas_height), (0, 0, 0, 0))

        self.tile_rects: Dict[str, Tuple[float, float, float, float]] = {}

        for idx, tile_name in enumerate(ATLAS_TILES):
            col = idx % self.GRID_COLS
            row = idx // self.GRID_COLS

            tile_path = os.path.join(self.textures_dir, f"{tile_name}.png")
            if os.path.exists(tile_path):
                img = Image.open(tile_path).convert("RGBA")
                if img.height > img.width and img.height % img.width == 0:
                    img = img.crop((0, 0, img.width, img.width))  # tira animada (fogo): fica o primeiro quadro
                if img.size != (self.TILE_SIZE, self.TILE_SIZE):
                    img = img.resize((self.TILE_SIZE, self.TILE_SIZE), Image.Resampling.NEAREST)
            else:
                img = Image.new("RGBA", (self.TILE_SIZE, self.TILE_SIZE), (220, 220, 220, 255))

            self.atlas_image.paste(img, (col * self.TILE_SIZE, row * self.TILE_SIZE))

            # No OpenGL com FLIP_TOP_BOTTOM, row=0 vai para o topo da coordenada V
            gl_row = self.GRID_ROWS - 1 - row
            u_min = col / self.GRID_COLS
            u_max = (col + 1) / self.GRID_COLS
            v_min = gl_row / self.GRID_ROWS
            v_max = (gl_row + 1) / self.GRID_ROWS

            self.tile_rects[tile_name] = (u_min, v_min, u_max, v_max)

        self.atlas_gl = self.atlas_image.transpose(Image.FLIP_TOP_BOTTOM)

    def _build_tables(self) -> None:
        """Pré-calcula arrays NumPy para consulta O(1) de UVs e tint por (BlockType, Face)."""
        max_id = max(int(b) for b in BlockType) + 1
        num_faces = 6

        # shape: (max_id, 6, 4, 2)
        self.uv_table = np.zeros((max_id, num_faces, 4, 2), dtype=np.float32)
        # shape: (max_id, 6, 3)
        self.color_table = np.ones((max_id, num_faces, 3), dtype=np.float32)

        for block in BlockType:
            b_id = int(block)
            for face in range(num_faces):
                tile_name, tint = self._resolve_tile_and_tint(block, face)
                u_min, v_min, u_max, v_max = self.tile_rects.get(
                    tile_name, self.tile_rects["white_concrete"]
                )

                base_uv = _TOP_UVS if face == 2 else _UVS
                du = u_max - u_min
                dv = v_max - v_min

                self.uv_table[b_id, face, :, 0] = u_min + base_uv[:, 0] * du
                self.uv_table[b_id, face, :, 1] = v_min + base_uv[:, 1] * dv
                self.color_table[b_id, face, :] = tint

    def _resolve_tile_and_tint(
        self,
        block: BlockType,
        face: int,
    ) -> Tuple[str, Tuple[float, float, float]]:
        """Mapeia (BlockType, Face) para o nome da textura e cor de tint multiplicadora."""
        if block == BlockType.GRASS:
            if face == 2:  # +Y Top
                return "grass_block_top", (0.38, 0.76, 0.24)
            elif face == 3:  # -Y Bottom
                return "dirt", (1.0, 1.0, 1.0)
            else:  # Lados
                return "grass_block_side", (1.0, 1.0, 1.0)

        elif block == BlockType.DIRT:
            return "dirt", (1.0, 1.0, 1.0)

        elif block == BlockType.STONE:
            return "stone", (1.0, 1.0, 1.0)

        elif block == BlockType.WOOD:
            if face in (2, 3):  # Top / Bottom
                return "oak_log_top", (1.0, 1.0, 1.0)
            else:
                return "oak_log", (1.0, 1.0, 1.0)

        elif block == BlockType.LEAVES:
            return "oak_leaves", (0.28, 0.65, 0.20)

        elif block == BlockType.TAIGA_GRASS:   # a grama fria da taiga: o mesmo desenho, outra tinta
            if face == 2:
                return "grass_block_top", (0.34, 0.56, 0.30)
            elif face == 3:
                return "dirt", (1.0, 1.0, 1.0)
            return "grass_block_side", (1.0, 1.0, 1.0)

        elif block == BlockType.SAND:
            return "sand", (1.0, 1.0, 1.0)

        elif block == BlockType.SANDSTONE:
            return ("sandstone_top" if face == 2 else "sandstone_bottom" if face == 3 else "sandstone"), (1.0, 1.0, 1.0)

        elif block == BlockType.PODZOL:
            return ("podzol_top" if face == 2 else "dirt" if face == 3 else "podzol_side"), (1.0, 1.0, 1.0)

        elif block == BlockType.SPRUCE_LOG:
            return ("spruce_log_top" if face in (2, 3) else "spruce_log"), (1.0, 1.0, 1.0)

        elif block == BlockType.SPRUCE_LEAVES:
            return "spruce_leaves", (0.38, 0.60, 0.38)

        elif block == BlockType.WATER:
            return "water_still", (0.32, 0.62, 0.95)

        elif block in SHAPED_BLOCK_NAMES:
            # a forma é desenhada pelo malhador com a textura do nome; a tabela só guarda a mesma textura
            return shaped_texture(block), (1.0, 1.0, 1.0)

        # Fallback para blocos desconhecidos / genéricos
        return "white_concrete", get_block_color(block)

    def flipped_rect(self, tile_name: str) -> Tuple[float, float, float, float]:
        """(u0, v0, u1, v1) do ladrilho com v0 no alto da textura, como ``block_shapes`` espera (o atlas do
        terreno vai para a GPU de cabeça para baixo)."""
        u_min, v_min, u_max, v_max = self.tile_rects.get(tile_name, self.tile_rects["white_concrete"])
        return u_min, v_max, u_max, v_min

    def load_gl_texture(self) -> int:
        """Cria e envia o Texture Atlas para a GPU com filtragem NEAREST pixel art."""
        if self._gl_texture_id is not None:
            return self._gl_texture_id

        import OpenGL.GL as gl

        tex_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)

        img_data = self.atlas_gl.tobytes()
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D,
            0,
            gl.GL_RGBA,
            self.atlas_gl.width,
            self.atlas_gl.height,
            0,
            gl.GL_RGBA,
            gl.GL_UNSIGNED_BYTE,
            img_data,
        )

        self._gl_texture_id = tex_id
        return self._gl_texture_id

    @property
    def texture_id(self) -> int:
        """Retorna o ID da textura OpenGL alocada."""
        if self._gl_texture_id is None:
            return self.load_gl_texture()
        return self._gl_texture_id

    def delete(self) -> None:
        """Libera o buffer de textura da GPU."""
        if self._gl_texture_id is not None:
            import OpenGL.GL as gl

            gl.glDeleteTextures(1, [self._gl_texture_id])
            self._gl_texture_id = None
