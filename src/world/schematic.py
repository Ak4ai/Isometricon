"""Parser e representação de arquivos de construções Schematic (.schem) do Minecraft."""

import gzip
import io
import os
import zlib
import struct
from typing import Dict, Optional, Tuple
import numpy as np


MAX_SCHEM_FILE_BYTES = 32 * 1024 * 1024
MAX_SCHEM_NBT_BYTES = 64 * 1024 * 1024
MAX_SCHEM_VOXELS = 1024 * 1024
MAX_SCHEM_MESH_QUADS = 150_000
MAX_NBT_DEPTH = 64
MAX_NBT_VALUES = 500_000


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
    """Lê NBT com limites para o tamanho, a profundidade e o número de valores."""
    remaining = MAX_NBT_VALUES
    start = stream.tell()
    end = stream.seek(0, io.SEEK_END)
    stream.seek(start)

    def read(size: int) -> bytes:
        if not 0 <= size <= end - stream.tell():
            raise ValueError("Dados NBT truncados ou com tamanho inválido.")
        return stream.read(size)

    def string() -> str:
        return read(struct.unpack(">H", read(2))[0]).decode("utf-8", errors="replace")

    numbers = {
        NBTTag.BYTE: ">b", NBTTag.SHORT: ">h", NBTTag.INT: ">i", NBTTag.LONG: ">q",
        NBTTag.FLOAT: ">f", NBTTag.DOUBLE: ">d",
    }

    def size_of_collection(length: int) -> None:
        if length < 0 or length > remaining:
            raise ValueError("Coleção NBT excede o limite de elementos.")

    def tag(kind: int, depth: int):
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or depth > MAX_NBT_DEPTH:
            raise ValueError("Dados NBT excedem o limite de elementos ou profundidade.")
        if kind in numbers:
            fmt = numbers[kind]
            return struct.unpack(fmt, read(struct.calcsize(fmt)))[0]
        if kind == NBTTag.BYTE_ARRAY:
            return read(struct.unpack(">i", read(4))[0])
        if kind == NBTTag.STRING:
            return string()
        if kind == NBTTag.LIST:
            child, length = struct.unpack(">Bi", read(5))
            if length <= 0:  # NBT permite lista vazia com qualquer tipo quando o tamanho não é positivo
                return []
            size_of_collection(length)
            return [tag(child, depth + 1) for _ in range(length)]
        if kind == NBTTag.COMPOUND:
            compound = {}
            while (child := read(1)[0]) != NBTTag.END:
                name = string()
                compound[name] = tag(child, depth + 1)
            return compound
        if kind in (NBTTag.INT_ARRAY, NBTTag.LONG_ARRAY):
            length = struct.unpack(">i", read(4))[0]
            size_of_collection(length)
            remaining -= length
            fmt, width = ("i", 4) if kind == NBTTag.INT_ARRAY else ("q", 8)
            return list(struct.unpack(f">{length}{fmt}", read(length * width)))
        raise ValueError("Tipo de etiqueta NBT desconhecido.")

    if read(1)[0] != NBTTag.COMPOUND:
        raise ValueError("A raiz NBT deve ser um compound.")
    root_name = string()
    return root_name, tag(NBTTag.COMPOUND, 0)


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
        *,
        max_mesh_quads: Optional[int] = None,
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
        self.max_mesh_quads = max_mesh_quads
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
        """Carrega um arquivo Sponge Schematic v1/v2/v3."""
        with open(filepath, "rb") as handle:
            data = handle.read(MAX_SCHEM_FILE_BYTES + 1)
        name = os.path.splitext(os.path.basename(filepath))[0]
        return cls.load_from_bytes(data, name)

    @classmethod
    def load_from_bytes(cls, data: bytes, name: str) -> "Schematic":
        """Valida o conteúdo comprimido, inclusive quando será guardado como cópia persistente."""
        if len(data) > MAX_SCHEM_FILE_BYTES:
            raise ValueError("Arquivo schematic comprimido excede o limite.")
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(data), mode="rb") as handle:
                raw_data = handle.read(MAX_SCHEM_NBT_BYTES + 1)
        except (OSError, EOFError, zlib.error) as error:
            raise ValueError("Arquivo schematic Gzip inválido.") from error
        if len(raw_data) > MAX_SCHEM_NBT_BYTES:
            raise ValueError("Arquivo schematic descompactado excede o limite.")
        _, root = parse_nbt_stream(io.BytesIO(raw_data))

        schem_tag = root.get("Schematic", root)
        if not isinstance(schem_tag, dict):
            raise ValueError("Cabeçalho Schematic inválido.")
        width, height, length = (schem_tag.get(key, 0) for key in ("Width", "Height", "Length"))
        if any(type(n) is not int or n <= 0 for n in (width, height, length)):
            raise ValueError(f"Dimensões inválidas no schematic: {width}x{height}x{length}")
        total_voxels = width * height * length
        if total_voxels > MAX_SCHEM_VOXELS:
            raise ValueError(f"Schematic excede o limite de {MAX_SCHEM_VOXELS} voxels.")

        blocks = schem_tag.get("Blocks", {})
        if isinstance(blocks, dict) and "Palette" in blocks:
            palette, block_data = blocks.get("Palette"), blocks.get("Data")
        else:
            palette, block_data = schem_tag.get("Palette"), schem_tag.get("BlockData")
        if not isinstance(palette, dict) or not isinstance(block_data, bytes):
            raise ValueError("Paleta ou dados de blocos inválidos no schematic.")
        if any(type(value) is not int or not 0 <= value <= 0x7fff_ffff for value in palette.values()):
            raise ValueError("Identificador de paleta inválido no schematic.")

        # Indexação Sponge: (y * Length + z) * Width + x. IDs fora da paleta e
        # células ausentes continuam sendo ar, sem alocar uma tabela pelo maior ID.
        id_to_name = {value: key for key, value in palette.items()}
        air = "minecraft:air"
        grid = np.full(total_voxels, air, dtype=object)
        cell, value, shift = 0, 0, 0
        for byte in block_data:
            if cell >= total_voxels or (shift == 28 and byte > 7):
                raise ValueError("Dados de blocos excedem o tamanho ou o VarInt permitido.")
            value |= (byte & 0x7f) << shift
            if byte & 0x80:
                shift += 7
                continue
            grid[cell] = id_to_name.get(value, air)
            cell += 1
            value = shift = 0
        if shift:
            raise ValueError("Identificador de bloco VarInt truncado.")

        return cls(width, height, length, grid.reshape((height, length, width)), palette, name,
                   max_mesh_quads=MAX_SCHEM_MESH_QUADS)
