"""Parser e representação de arquivos de construções Schematic (.schem) do Minecraft."""

import gzip
import io
import os
import struct
from typing import Dict, List, Optional, Tuple
import numpy as np


class NBTTag:
    END = 0
    BYTE = 1
    SHORT = 2
    INT = 3
    LONG = 4
    FLOAT = 5
    DOUBLE = 6
    BYTE_ARRAY = 7
    STRING = 8
    LIST = 9
    COMPOUND = 10
    INT_ARRAY = 11
    LONG_ARRAY = 12


def parse_nbt_stream(stream: io.BytesIO) -> Tuple[str, dict]:
    """Decodifica uma estrutura NBT a partir de um stream de bytes."""

    def read_tag(tag_type: int):
        if tag_type == NBTTag.BYTE:
            return struct.unpack(">b", stream.read(1))[0]
        elif tag_type == NBTTag.SHORT:
            return struct.unpack(">h", stream.read(2))[0]
        elif tag_type == NBTTag.INT:
            return struct.unpack(">i", stream.read(4))[0]
        elif tag_type == NBTTag.LONG:
            return struct.unpack(">q", stream.read(8))[0]
        elif tag_type == NBTTag.FLOAT:
            return struct.unpack(">f", stream.read(4))[0]
        elif tag_type == NBTTag.DOUBLE:
            return struct.unpack(">d", stream.read(8))[0]
        elif tag_type == NBTTag.BYTE_ARRAY:
            length = struct.unpack(">i", stream.read(4))[0]
            return stream.read(length)
        elif tag_type == NBTTag.STRING:
            length = struct.unpack(">H", stream.read(2))[0]
            return stream.read(length).decode("utf-8", errors="replace")
        elif tag_type == NBTTag.LIST:
            sub_type = stream.read(1)[0]
            length = struct.unpack(">i", stream.read(4))[0]
            return [read_tag(sub_type) for _ in range(length)]
        elif tag_type == NBTTag.COMPOUND:
            res = {}
            while True:
                sub_type = stream.read(1)[0]
                if sub_type == NBTTag.END:
                    break
                name_len = struct.unpack(">H", stream.read(2))[0]
                name = stream.read(name_len).decode("utf-8", errors="replace")
                res[name] = read_tag(sub_type)
            return res
        elif tag_type == NBTTag.INT_ARRAY:
            length = struct.unpack(">i", stream.read(4))[0]
            return list(struct.unpack(f">{length}i", stream.read(4 * length)))
        elif tag_type == NBTTag.LONG_ARRAY:
            length = struct.unpack(">i", stream.read(4))[0]
            return list(struct.unpack(f">{length}q", stream.read(8 * length)))
        return None

    top_type = stream.read(1)[0]
    if top_type == NBTTag.END:
        return "", {}
    name_len = struct.unpack(">H", stream.read(2))[0]
    root_name = stream.read(name_len).decode("utf-8", errors="replace")
    return root_name, read_tag(top_type)


_AIR_NAMES = {"air", "cave_air", "void_air"}


def is_air_name(block_name: str) -> bool:
    """Diz se o nome de bloco (com ou sem namespace e propriedades) é ar."""
    clean = block_name.split("[")[0].strip()
    if ":" in clean:
        clean = clean.split(":", 1)[1]
    return clean == "" or clean.lower() in _AIR_NAMES


class Schematic:
    """Representa uma estrutura 3D de blocos importada de um arquivo .schem."""

    def __init__(
        self,
        width: int,
        height: int,
        length: int,
        grid: np.ndarray,
        palette: Dict[str, int],
        name: str = "Structure",
    ):
        """
        Args:
            width: Dimensão no eixo X.
            height: Dimensão no eixo Y (altura).
            length: Dimensão no eixo Z (profundidade).
            grid: Matriz 3D NumPy de formato (height, length, width) contendo os nomes dos blocos.
            palette: Dicionário mapeando block_state_string -> id inteiro.
            name: Nome descritivo da construção.
        """
        self.width = width
        self.height = height
        self.length = length
        self.grid = grid  # indexado como [y, z, x]
        self.palette = palette
        self.name = name
        self._solid_mask: Optional[np.ndarray] = None
        self._occupied_mask: Optional[np.ndarray] = None
        self._full_cube_mask: Optional[np.ndarray] = None
        self._detail_mask: Optional[np.ndarray] = None
        self._shadow_shape_mask: Optional[np.ndarray] = None
        self._door_mask: Optional[np.ndarray] = None

    def invalidate_masks(self) -> None:
        """Esquece as máscaras calculadas (depois de trocar blocos da grade, como abrir uma porta)."""
        self._solid_mask = self._occupied_mask = self._full_cube_mask = self._detail_mask = None
        self._shadow_shape_mask = None
        self._door_mask = None

    def get_block(self, x: int, y: int, z: int) -> str:
        """Retorna o nome do bloco na coordenada local da estrutura."""
        if 0 <= x < self.width and 0 <= y < self.height and 0 <= z < self.length:
            return self.grid[y, z, x]
        return "minecraft:air"

    def is_air(self, x: int, y: int, z: int) -> bool:
        """Verifica se a coordenada é ar ou fora dos limites."""
        return is_air_name(self.get_block(x, y, z))

    def _mask(self, test) -> np.ndarray:
        lookup = {name: bool(test(name)) for name in set(self.grid.ravel().tolist())}
        return np.vectorize(lookup.__getitem__, otypes=[bool])(self.grid)

    @property
    def door_mask(self) -> np.ndarray:
        """Máscara booleana (height, length, width): True nas células de porta (aberta ou fechada)."""
        if self._door_mask is None:
            from src.world.doors import is_door
            self._door_mask = self._mask(is_door)
        return self._door_mask

    @property
    def occupied_mask(self) -> np.ndarray:
        """Máscara booleana (height, length, width): True onde há bloco que não é ar (é desenhado)."""
        if self._occupied_mask is None:
            self._occupied_mask = self._mask(lambda name: not is_air_name(name))
        return self._occupied_mask

    @property
    def solid_mask(self) -> np.ndarray:
        """Máscara booleana: True onde o bloco barra o personagem (colisão e cômodos).

        Tochas, tapetes, placas, botões, velas e vasos são desenhados mas não barram.
        """
        if self._solid_mask is None:
            from src.world.block_shapes import collides

            self._solid_mask = self._mask(lambda name: not is_air_name(name) and collides(name))
        return self._solid_mask

    @property
    def full_cube_mask(self) -> np.ndarray:
        """Máscara booleana: True nos cubos inteiros (só eles escondem a face do vizinho)."""
        if self._full_cube_mask is None:
            from src.world.block_shapes import is_full_cube

            self._full_cube_mask = self._mask(lambda name: not is_air_name(name) and is_full_cube(name))
        return self._full_cube_mask

    @property
    def shadow_shape_mask(self) -> np.ndarray:
        """uint16 (height, length, width): o número da forma de cada bloco que não é cubo inteiro na tabela da sombra
        do sol (``shadow_shapes.TABLE``), barre ou não o personagem (a placa e a cerca também fazem sombra); 0 no
        resto."""
        if self._shadow_shape_mask is None:
            from src.world.shadow_shapes import TABLE

            lookup = {name: (0 if is_air_name(name) else TABLE.id_for(name)) for name in set(self.grid.ravel().tolist())}
            self._shadow_shape_mask = np.vectorize(lookup.__getitem__, otypes=[np.uint16])(self.grid)
        return self._shadow_shape_mask

    @property
    def detail_mask(self) -> np.ndarray:
        """Máscara booleana: True nos detalhes de dentro da casa (móveis, enfeites; ver ``is_room_detail``)."""
        if self._detail_mask is None:
            from src.world.block_shapes import is_room_detail

            self._detail_mask = self._mask(lambda name: not is_air_name(name) and is_room_detail(name))
        return self._detail_mask

    @classmethod
    def load_from_file(cls, filepath: str) -> "Schematic":
        """Carrega e decodifica um arquivo .schem (Sponge Schematic v1/v2/v3)."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Arquivo schematic não encontrado: {filepath}")

        # Descomprimir NBT compactado com Gzip
        with gzip.open(filepath, "rb") as f:
            raw_data = f.read()

        _, root = parse_nbt_stream(io.BytesIO(raw_data))

        # Suporte a nós raiz 'Schematic' ou raiz direta
        schem_tag = root.get("Schematic", root)

        width = int(schem_tag.get("Width", 0))
        height = int(schem_tag.get("Height", 0))
        length = int(schem_tag.get("Length", 0))

        if width <= 0 or height <= 0 or length <= 0:
            raise ValueError(f"Dimensões inválidas no schematic: {width}x{height}x{length}")

        total_voxels = width * height * length

        # Sponge v3 tem sub-compound 'Blocks', enquanto v1/v2 usa chaves diretas
        blocks_compound = schem_tag.get("Blocks", {})
        if isinstance(blocks_compound, dict) and "Palette" in blocks_compound:
            palette = blocks_compound.get("Palette", {})
            block_data_bytes = blocks_compound.get("Data", b"")
        else:
            palette = schem_tag.get("Palette", {})
            block_data_bytes = schem_tag.get("BlockData", b"")

        # Inverter palette: int_id -> block_name
        id_to_name = {int(v): str(k) for k, v in palette.items()}

        # Decodificar stream de VarInts do BlockData
        block_ids: List[int] = []
        i = 0
        data_len = len(block_data_bytes)

        while i < data_len and len(block_ids) < total_voxels:
            value = 0
            shift = 0
            while True:
                b = block_data_bytes[i]
                i += 1
                value |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
                shift += 7
            block_ids.append(value)

        # Matriz 3D com indexação canônica Sponge: index = (y * Length + z) * Width + x.
        # Ids fora da palette e voxels que faltam no stream viram ar.
        ids = np.full(total_voxels, -1, dtype=np.int64)
        ids[: len(block_ids)] = block_ids
        top_id = max([int(ids.max())] + list(id_to_name))
        lookup = np.full(top_id + 2, "minecraft:air", dtype=object)  # a última posição serve ao -1
        for b_id, block_name in id_to_name.items():
            lookup[b_id] = block_name
        grid = lookup[ids].reshape((height, length, width))

        structure_name = os.path.splitext(os.path.basename(filepath))[0]
        return cls(
            width=width,
            height=height,
            length=length,
            grid=grid,
            palette=palette,
            name=structure_name,
        )
