# Fundação lógica do mundo voxel, sem dependência de OpenGL.

from src.world.block import BLOCK_COLORS, BlockType, get_block_color, is_opaque
from src.world.chunk import Chunk3D
from src.world.mesher import ChunkMeshData, ChunkMesher
from src.world.terrain import TerrainGenerator

__all__ = [
    "BlockType", "BLOCK_COLORS", "get_block_color", "is_opaque", "Chunk3D",
    "ChunkMeshData", "ChunkMesher", "TerrainGenerator",
]
