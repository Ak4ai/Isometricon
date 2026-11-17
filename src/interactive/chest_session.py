"""O baú aberto: enquanto ele está aberto a tela escurece e o personagem fica parado (sem OpenGL).

Sem a janela do inventário por enquanto: ``F`` abre o baú ao alcance, ``F`` de novo fecha e devolve o jogo. O escurecimento
entra e sai suavemente (``dim``), e ``locks_movement`` diz ao laço do jogo para ignorar o teclado de movimento.

A tampa também anima: ``lid`` vai de 0 a 1 ao abrir e volta ao fechar; ``take_lid_update`` entrega ao laço do jogo, uma vez
por mudança, qual baú e quanto a tampa abriu, para a malha dele ser refeita.
"""

from typing import Any, Optional, Tuple

DIM_MAX = 0.62          # o quanto a tela escurece com o baú aberto (0 a 1)
FADE_SECONDS = 0.18     # tempo para escurecer ou clarear por inteiro
LID_SECONDS = 0.40      # tempo da tampa para abrir (ou fechar) por inteiro


class ChestSession:
    def __init__(self) -> None:
        self.chest: Optional[Any] = None     # ChestRef do baú aberto, ou None
        self.level = 0.0                     # 0 fechado, 1 aberto de vez (suaviza a troca)
        self.lid = 0.0                       # a tampa: 0 fechada, 1 toda aberta
        self.lid_chest: Optional[Any] = None  # o baú cuja tampa se mexe (fica até ela fechar de vez, mesmo já "fechado")
        self._lid_sent: Optional[float] = None

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

    @property
    def lid_eased(self) -> float:
        """A abertura da tampa com início e fim suaves (0 a 1)."""
        return self.lid * self.lid * (3.0 - 2.0 * self.lid)

    def take_lid_update(self) -> Optional[Tuple[Any, float]]:
        """(baú, abertura) se a tampa mudou desde a última vez que isto foi chamado; senão ``None``.

        Ao fechar por inteiro entrega a abertura 0 uma última vez e solta o baú."""
        if self.lid_chest is None:
            return None
        amount = self.lid_eased
        if amount == self._lid_sent:
            return None
        chest = self.lid_chest
        self._lid_sent = amount
        if amount == 0.0 and self.chest is None:
            self.lid_chest, self._lid_sent = None, None
        return chest, amount

    def open(self, chest: Any) -> bool:
        if self.chest is not None or chest is None:
            return False
        if self.lid_chest is not None and self.lid_chest != chest and self.lid > 0.0:
            return False        # a tampa de outro baú ainda está fechando: espera ela terminar
        self.chest = self.lid_chest = chest
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
        lid_step = max(float(dt), 0.0) / LID_SECONDS
        if self.lid < target:
            self.lid = min(target, self.lid + lid_step)
        else:
            self.lid = max(target, self.lid - lid_step)
