"""Atlas de texturas por nome de bloco, para desenhar schematics.

Diferente do `TextureAtlas` do mundo (12 texturas fixas, indexado por BlockType), este
empacota todas as texturas de `assets/textures/blocks` e responde por nome de bloco do
Minecraft (`minecraft:oak_stairs[facing=north]`), que é o que um .schem traz.
"""

import os
from typing import Dict, Optional, Tuple

import numpy as np
from PIL import Image

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEXTURES_DIR = os.path.abspath(
    os.path.join(CURRENT_DIR, "..", "..", "assets", "textures", "blocks")
)

FALLBACK = "__fallback__"

# Sufixos de blocos que não têm textura própria (a ordem importa: o mais longo primeiro)
_DERIVED_SUFFIXES = (
    "_wall_hanging_sign", "_hanging_sign", "_wall_sign", "_sign", "_fence_gate", "_fence",
    "_pressure_plate", "_button", "_stairs", "_slab", "_wall",
)


class SchematicAtlas:
    """Combina as texturas de bloco numa só imagem; a textura OpenGL só nasce em `upload()`."""

    def __init__(
        self,
        textures_dir: Optional[str] = None,
        tile_size: int = 16,
        atlas_size: int = 1024,
        create_gl: bool = False,
    ):
        """
        Args:
            textures_dir: Pasta com os .png dos blocos (padrão: assets/textures/blocks).
            tile_size: Lado de cada ladrilho em pixels.
            atlas_size: Lado do atlas em pixels (quadrado).
            create_gl: Se True, já envia o atlas para a GPU (precisa de contexto OpenGL).
        """
        self.textures_dir = textures_dir or DEFAULT_TEXTURES_DIR
        self.tile_size = tile_size
        self.atlas_size = atlas_size
        self.tiles_per_row = atlas_size // tile_size

        self.texture_id: int = 0
        self.uv_map: Dict[str, Tuple[float, float, float, float]] = {}
        self.atlas_image: Image.Image

        self._build_atlas()
        if create_gl:
            self.upload()

    @staticmethod
    def clean_block_name(block_name: str) -> str:
        """Tira o namespace 'minecraft:' e as propriedades '[facing=north,...]'."""
        clean = block_name.split("[")[0].strip()
        if ":" in clean:
            clean = clean.split(":", 1)[1]
        return clean.lower()

    def _build_atlas(self) -> None:
        """Lê os PNGs e monta a imagem do atlas e a tabela de UVs (sem OpenGL)."""
        if not os.path.isdir(self.textures_dir):
            raise FileNotFoundError(f"Pasta de texturas não encontrada: {self.textures_dir}")

        ts = self.tile_size
        atlas_img = Image.new("RGBA", (self.atlas_size, self.atlas_size), (0, 0, 0, 0))

        # Slot 0: textura de reserva (roxa) para o que não tem arquivo
        atlas_img.paste(Image.new("RGBA", (ts, ts), (180, 50, 220, 255)), (0, 0))
        self.uv_map[FALLBACK] = (0.0, 0.0, ts / self.atlas_size, ts / self.atlas_size)

        png_files = sorted(f for f in os.listdir(self.textures_dir) if f.lower().endswith(".png"))
        max_tiles = self.tiles_per_row * self.tiles_per_row
        slot = 1

        for filename in png_files:
            if slot >= max_tiles:
                break
            path = os.path.join(self.textures_dir, filename)
            try:
                tile = Image.open(path).convert("RGBA")
            except Exception as error:  # arquivo corrompido: pula, não derruba o atlas
                print(f"Aviso ao carregar textura {filename}: {error}")
                continue

            # Texturas animadas (água, lava, fogo) são tiras verticais: fica o primeiro quadro
            if tile.height > tile.width and tile.height % tile.width == 0:
                tile = tile.crop((0, 0, tile.width, tile.width))
            if tile.size != (ts, ts):
                tile = tile.resize((ts, ts), Image.Resampling.NEAREST)

            px = (slot % self.tiles_per_row) * ts
            py = (slot // self.tiles_per_row) * ts
            atlas_img.paste(tile, (px, py))

            self.uv_map[os.path.splitext(filename)[0].lower()] = (
                px / self.atlas_size,
                py / self.atlas_size,
                (px + ts) / self.atlas_size,
                (py + ts) / self.atlas_size,
            )
            slot += 1

        self.atlas_image = atlas_img

    def get_uv(self, block_name: str, face: str = "all") -> Tuple[float, float, float, float]:
        """Retorna (u0, v0, u1, v1) para um bloco e face ('top', 'bottom' ou lateral)."""
        clean = self.clean_block_name(block_name)

        if face in ("top", "+y"):
            candidates = [f"{clean}_top", f"{clean}_up", clean]
        elif face in ("bottom", "-y"):
            candidates = [f"{clean}_bottom", f"{clean}_down", f"{clean}_top", clean]
        else:
            candidates = [f"{clean}_side", clean]

        # Nomes de bloco que não são o nome do arquivo de textura
        if "log" in clean or "wood" in clean:
            log_base = clean.replace("_wood", "_log")
            if face in ("top", "bottom", "+y", "-y"):
                candidates.extend([f"{log_base}_top", f"stripped_{clean}_top"])
            else:
                candidates.extend([log_base, f"stripped_{clean}", f"{clean}_side"])

        # Blocos derivados (degrau, laje, cerca, placa, botão...) usam a textura do material
        base = clean
        for suffix in _DERIVED_SUFFIXES:
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break
        if base != clean:
            smooth = base.startswith("smooth_")
            base = base.removeprefix("smooth_")
            if smooth and base == "quartz":
                candidates.append("quartz_block_bottom")  # o quartzo liso usa o fundo do bloco
            if face in ("top", "+y"):
                candidates.extend([f"{base}_block_top", f"{base}_top"])
            candidates.extend([
                base, f"{base}_planks", f"{base}_block", f"{base}_block_side",
                f"{base}s", f"{base}_side",
            ])

        if "trapdoor" in clean or "door" in clean:
            candidates.extend([clean, f"{clean}_bottom", f"{clean}_top"])

        for candidate in candidates:
            if candidate in self.uv_map:
                return self.uv_map[candidate]

        # Último recurso: nome parcial (ignora o slot de reserva)
        for name, uv in self.uv_map.items():
            if name != FALLBACK and (clean in name or name in clean):
                return uv

        return self.uv_map[FALLBACK]

    def upload(self) -> None:
        """Envia o atlas para a GPU (precisa de contexto OpenGL ativo)."""
        import OpenGL.GL as gl

        if self.texture_id:
            return
        data = np.array(self.atlas_image, dtype=np.uint8)
        self.texture_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        # NEAREST mantém o pixel-art nítido
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, self.atlas_size, self.atlas_size, 0,
            gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, data,
        )
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

    def bind(self, texture_unit: int = 0) -> None:
        """Ativa a unidade de textura e vincula o atlas."""
        import OpenGL.GL as gl

        gl.glActiveTexture(gl.GL_TEXTURE0 + texture_unit)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)

    def delete(self) -> None:
        """Libera a textura da GPU."""
        import OpenGL.GL as gl

        if self.texture_id:
            gl.glDeleteTextures(1, [self.texture_id])
            self.texture_id = 0
