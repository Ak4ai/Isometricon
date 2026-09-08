"""Gerenciador dinâmico de mundo (WorldManager) para carregamento contínuo/infinito de chunks."""

import math
from typing import Callable, Dict, Optional, Set, Tuple, TYPE_CHECKING

import numpy as np

from src.math import mat4_scale, mat4_translate
from src.world.block import BlockType
from src.world.chunk import Chunk3D
from src.world.mesher import ChunkMesher
from src.world.terrain import TerrainGenerator

if TYPE_CHECKING:
    from src.rendering.mesh import TexturedMesh



class WorldManager:
    """Gerencia o ciclo de vida, streaming contínuo e renderização de chunks ao redor da câmera/jogador."""

    def __init__(
        self,
        generator: TerrainGenerator,
        render_distance: int = 2,
        create_gl_meshes: bool = True,
    ) -> None:
        self.generator = generator
        self.render_distance = render_distance
        self.create_gl_meshes = create_gl_meshes


        # Chunks carregados na memória lógica: (cx, cy, cz) -> Chunk3D
        self.chunks: Dict[Tuple[int, int, int], Chunk3D] = {}

        # Malhas OpenGL ativas na GPU: (cx, cy, cz) -> (TexturedMesh, transform_matrix)
        self.meshes: Dict[Tuple[int, int, int], Tuple[TexturedMesh, np.ndarray]] = {}

        self.mesher = ChunkMesher()
        self._last_center: Tuple[int, int] | None = None

    def neighbor_at(self, x: int, y: int, z: int) -> BlockType:
        """Consulta rápida de blocos para cálculo de Face Culling entre chunks vizinhos."""
        size = Chunk3D.SIZE
        cx = x // size
        cy = y // size
        cz = z // size
        chunk = self.chunks.get((cx, cy, cz))
        if chunk is None:
            return BlockType.AIR
        return chunk.get_block(*chunk.world_to_local(x, y, z))

    def update(self, focus_x: float, focus_z: float) -> None:
        """Atualiza a grade de chunks ativos de acordo com a posição do foco (jogador/câmera)."""
        size = Chunk3D.SIZE
        center_cx = int(math.floor(focus_x / size))
        center_cz = int(math.floor(focus_z / size))

        if self._last_center == (center_cx, center_cz):
            return

        self._last_center = (center_cx, center_cz)

        # 1. Determina as colunas ativas dentro do raio de renderização
        target_columns: Set[Tuple[int, int]] = {
            (cx, cz)
            for cx in range(center_cx - self.render_distance, center_cx + self.render_distance + 1)
            for cz in range(center_cz - self.render_distance, center_cz + self.render_distance + 1)
        }

        # 2. Descarrega chunks distantes (fora do raio)
        to_unload = [
            key for key in list(self.chunks.keys())
            if (key[0], key[2]) not in target_columns
        ]

        for key in to_unload:
            if key in self.meshes:
                mesh, _ = self.meshes.pop(key)
                mesh.delete()
            self.chunks.pop(key, None)

        # 3. Gera chunks novos necessários
        new_positions = []
        for cx, cz in target_columns:
            if (cx, 0, cz) not in self.chunks:
                new_positions.append((cx, 0, cz))

        if new_positions:
            new_chunks = self.generator.generate_region(new_positions)
            self.chunks.update(new_chunks)

            if self.create_gl_meshes:
                from src.rendering.mesh import TexturedMesh
                for key, chunk in new_chunks.items():
                    data = self.mesher.build(chunk, self.neighbor_at)
                    if data.face_count > 0:
                        mesh = TexturedMesh(data.vertices, data.indices)
                        transform = mat4_translate(*chunk.local_to_world(0, 0, 0))
                        self.meshes[key] = (mesh, transform)



    def get_height(self, world_x: float, world_z: float) -> int:
        """Retorna a altura do terreno sólido na coordenada informada."""
        return self.generator.get_height(int(math.floor(world_x)), int(math.floor(world_z)))

    def render(self, shader, base_model: np.ndarray) -> None:
        """Renderiza todas as malhas de chunks ativas na GPU."""
        for mesh, transform in self.meshes.values():
            shader.set_mat4("u_Model", base_model @ transform)
            mesh.draw()

    def delete(self) -> None:
        """Libera todas as malhas de chunks da GPU."""
        for mesh, _ in self.meshes.values():
            mesh.delete()
        self.meshes.clear()
        self.chunks.clear()
        self._last_center = None
