"""O baú aberto: enquanto ele está aberto a tela escurece e o personagem fica parado (sem OpenGL).

Sem a janela do inventário por enquanto: ``F`` abre o baú ao alcance, ``F`` de novo fecha e devolve o jogo. O escurecimento
entra e sai suavemente (``dim``), e ``locks_movement`` diz ao laço do jogo para ignorar o teclado de movimento.
"""

from typing import Any, Optional

DIM_MAX = 0.62          # o quanto a tela escurece com o baú aberto (0 a 1)
FADE_SECONDS = 0.18     # tempo para escurecer ou clarear por inteiro


class ChestSession:
    def __init__(self) -> None:
        self.chest: Optional[Any] = None     # ChestRef do baú aberto, ou None
        self.level = 0.0                     # 0 fechado, 1 aberto de vez (suaviza a troca)

    @property
    def is_open(self) -> bool:
        return self.chest is not None

    @property
    def locks_movement(self) -> bool:
        """O personagem não anda nem pula enquanto o baú está aberto."""
        return self.chest is not None

    @property
    def dim(self) -> float:
        """A opacidade do preto sobre a cena (0 a ``DIM_MAX``)."""
        return self.level * DIM_MAX

    def open(self, chest: Any) -> bool:
        if self.chest is not None or chest is None:
            return False
        self.chest = chest
        return True

    def close(self) -> bool:
        if self.chest is None:
            return False
        self.chest = None
        return True

    def toggle(self, chest: Any = None) -> bool:
        """F: fecha o baú aberto; senão abre ``chest`` (se há um). Devolve True se algo mudou."""
        if self.chest is not None:
            return self.close()
        return self.open(chest)

    def update(self, dt: float) -> None:
        step = max(float(dt), 0.0) / FADE_SECONDS
        target = 1.0 if self.chest is not None else 0.0
        if self.level < target:
            self.level = min(target, self.level + step)
        else:
            self.level = max(target, self.level - step)
