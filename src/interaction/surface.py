"""Semântica compartilhada das células táticas de superfície."""

from __future__ import annotations

from src.world import BlockType


# A célula tática é suportada por um voxel opaco sobre o qual um token pode
# repousar. Água e folhas são renderizáveis, mas não são terreno caminhável.
TACTICAL_SURFACE_BLOCKS = frozenset({
    BlockType.DIRT,
    BlockType.GRASS,
    BlockType.STONE,
    BlockType.WOOD,
})

# Água cobre uma célula em vez de servir como seu suporte. A regra evita que a
# grade do leito apareça através do material de água atual.
TACTICAL_SURFACE_BLOCKERS = frozenset({BlockType.WATER})


def is_tactical_surface(block_type: BlockType | int) -> bool:
    """Retorna se ``block_type`` pode sustentar uma célula tática.

    Esta é a política única para grid e futuros sistemas de posicionamento.
    ``WATER`` e ``LEAVES`` não criam células, e ``AIR`` nunca é uma superfície.
    """

    return BlockType(block_type) in TACTICAL_SURFACE_BLOCKS


def is_tactical_column(
    support_block: BlockType | int,
    topmost_block: BlockType | int,
) -> bool:
    """Retorna se uma coluna pode expor uma célula tática.

    O suporte deve ser tático e nenhum material bloqueador pode estar acima
    dele. Folhas não criam uma célula, mas também não removem o chão abaixo.
    """

    return (
        is_tactical_surface(support_block)
        and BlockType(topmost_block) not in TACTICAL_SURFACE_BLOCKERS
    )
