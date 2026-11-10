"""Gerador de malha otimizada para estruturas e schematics, com face culling e UVs.

A geração dos vértices é feita só com NumPy (sem OpenGL); `build_mesh` cria o
`TexturedMesh` na hora de enviar à GPU.
"""

from typing import Callable, Tuple

import numpy as np

from src.world.block_shapes import box_face_quad, shape_for
from src.world.schematic import Schematic

# (u0, v0, u1, v1) de um bloco e face
UvLookup = Callable[[str, str], Tuple[float, float, float, float]]

# Cada face: deslocamento do vizinho, normal, grupo de textura e os 4 cantos (relativos ao centro
# do bloco, em múltiplos de 0.5) na ordem anti-horária vista de fora. As UVs de cada canto
# escolhem (0 = u0/v0, 1 = u1/v1): nas laterais e no topo (u0,v1) (u1,v1) (u1,v0) (u0,v0);
# no fundo (u0,v0) (u1,v0) (u1,v1) (u0,v1).
_SIDE_UV = ((0, 1), (1, 1), (1, 0), (0, 0))
_BOTTOM_UV = ((0, 0), (1, 0), (1, 1), (0, 1))
_FACES = (
    # vizinho,      normal,           textura,  cantos,                                                    uv
    ((0, 1, 0), (0.0, 1.0, 0.0), "top", ((-1, 1, 1), (1, 1, 1), (1, 1, -1), (-1, 1, -1)), _SIDE_UV),
    ((0, -1, 0), (0.0, -1.0, 0.0), "bottom", ((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)), _BOTTOM_UV),
    ((0, 0, 1), (0.0, 0.0, 1.0), "north", ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)), _SIDE_UV),
    ((1, 0, 0), (1.0, 0.0, 0.0), "east", ((1, -1, 1), (1, -1, -1), (1, 1, -1), (1, 1, 1)), _SIDE_UV),
    ((0, 0, -1), (0.0, 0.0, -1.0), "south", ((1, -1, -1), (-1, -1, -1), (-1, 1, -1), (1, 1, -1)), _SIDE_UV),
    ((-1, 0, 0), (-1.0, 0.0, 0.0), "west", ((-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1)), _SIDE_UV),
)

# block_shapes.FACES tem a mesma ordem de _FACES; o índice da face vale nas duas tabelas
_FACES_BY_SHAPE_ORDER = _FACES

# Layout por vértice do TexturedMesh: posição(3), normal(3), uv(2), cor(3)
FLOATS_PER_VERTEX = 11


class StructureMesher:
    """Gera malhas a partir de Schematics descartando as faces entre blocos vizinhos."""

    @staticmethod
    def build_arrays(
        schematic: Schematic,
        uv_lookup: UvLookup,
        center: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Gera (vértices float32, índices uint32) com as faces expostas ao ar.

        Args:
            schematic: Estrutura carregada.
            uv_lookup: Função (nome do bloco, face) -> (u0, v0, u1, v1) no atlas.
            center: Se True, centraliza a estrutura em torno da origem (0, 0, 0).
        """
        w, h, l = schematic.width, schematic.height, schematic.length
        # Os centros dos blocos vão de 0 a dim-1: o meio deles está em (dim-1)/2
        offset = (np.array([w, h, l], dtype=np.float32) - 1.0) / 2.0 if center else np.zeros(3, dtype=np.float32)

        # Só um cubo inteiro esconde a face do vizinho (uma laje ou uma cerca ao lado não esconde).
        # A máscara ganha uma borda de ar: tudo que está fora da estrutura é ar.
        occupied = schematic.occupied_mask
        padded = np.zeros((h + 2, l + 2, w + 2), dtype=bool)
        padded[1:-1, 1:-1, 1:-1] = schematic.full_cube_mask
        shapes = {}

        uv_cache = {}
        vertices = []
        indices = []
        vertex_offset = 0

        # argwhere devolve [y, z, x] na ordem de varredura (y, z, x)
        for y, z, x in np.argwhere(occupied):
            block = schematic.grid[y, z, x]
            block_pos = np.array([x, y, z], dtype=np.float32) - offset
            if block not in shapes:
                shapes[block] = shape_for(block)
            boxes = shapes[block]
            if boxes is not None:
                for box in boxes:
                    for face, ((dx, dy, dz), _, face_key, _, _) in enumerate(_FACES_BY_SHAPE_ORDER):
                        if box.covers_face(face) and padded[y + 1 + dy, z + 1 + dz, x + 1 + dx]:
                            continue
                        name = box.texture or block
                        key = (name, face_key)
                        if key not in uv_cache:
                            uv_cache[key] = uv_lookup(name, face_key)
                        quad = box_face_quad(box, face, block_pos - 0.5, uv_cache[key])
                        vertices.extend(quad.ravel())
                        indices.extend((
                            vertex_offset, vertex_offset + 1, vertex_offset + 2,
                            vertex_offset + 2, vertex_offset + 3, vertex_offset,
                        ))
                        vertex_offset += 4
                continue
            for (dx, dy, dz), normal, face_key, corners, uv_order in _FACES:
                if padded[y + 1 + dy, z + 1 + dz, x + 1 + dx]:
                    continue  # há bloco do lado: a face não aparece
                key = (block, face_key)
                if key not in uv_cache:
                    uv_cache[key] = uv_lookup(block, face_key)
                u0, v0, u1, v1 = uv_cache[key]
                us, vs = (u0, u1), (v0, v1)
                for corner, (cu, cv) in zip(corners, uv_order):
                    pos = block_pos + 0.5 * np.array(corner, dtype=np.float32)
                    vertices.extend((*pos, *normal, us[cu], vs[cv], 1.0, 1.0, 1.0))
                indices.extend((
                    vertex_offset, vertex_offset + 1, vertex_offset + 2,
                    vertex_offset + 2, vertex_offset + 3, vertex_offset,
                ))
                vertex_offset += 4

        return (
            np.array(vertices, dtype=np.float32),
            np.array(indices, dtype=np.uint32),
        )

    @staticmethod
    def build_mesh(schematic: Schematic, atlas, center: bool = True):
        """Gera um TexturedMesh pronto para desenhar (precisa de contexto OpenGL).

        Args:
            schematic: Estrutura carregada.
            atlas: SchematicAtlas (ou qualquer objeto com `get_uv(bloco, face)`).
            center: Se True, centraliza a estrutura em torno da origem.
        """
        from src.rendering.mesh import TexturedMesh

        vertices, indices = StructureMesher.build_arrays(schematic, atlas.get_uv, center)
        return TexturedMesh(vertices, indices)
