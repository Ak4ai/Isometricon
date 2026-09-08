"""
Módulo Interactive - Motor Interativo (Equipe B)

Pacote Python para os sistemas de interação do usuário no Isometricon VTT:
- Raycasting 3D (Mouse Picking)
- Sistema de destaque (Hover/Seleção)
- Grid overlay (grade do tabuleiro)
- Sistema de tokens/miniaturas
- UI overlay (fichas de RPG)

Consulte src/interactive/README.md e docs/EQUIPE_B_ARCHITECTURE.md para detalhes.
"""

from src.interactive.highlight import BlockHighlightRenderer
from src.interactive.token_system import PlayerToken, create_token_mesh

__all__ = [
    "BlockHighlightRenderer",
    "PlayerToken",
    "create_token_mesh",
]

