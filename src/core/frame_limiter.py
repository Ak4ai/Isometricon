"""Limite de FPS: espera o fim do período de cada quadro (dorme a maior parte e fecha o último milissegundo
girando, porque o sono do sistema erra por ~1 ms)."""

import time


class FrameLimiter:
    SPIN = 0.0015  # segundos finais esperados sem dormir

    def __init__(self, clock=time.perf_counter, sleep=time.sleep) -> None:
        self._clock = clock
        self._sleep = sleep
        self._deadline = None

    def wait(self, fps: float) -> None:
        """Segura o quadro até completar 1/fps desde o anterior; fps 0 (ou menor) não limita."""
        if not fps or fps <= 0:
            self._deadline = None
            return
        period = 1.0 / float(fps)
        now = self._clock()
        if self._deadline is None or now - self._deadline > period:
            self._deadline = now  # atrasou mais que um quadro (um travamento): recomeça a contagem dali
        self._deadline += period
        remaining = self._deadline - self._clock()
        if remaining > self.SPIN:
            self._sleep(remaining - self.SPIN)
        while self._clock() < self._deadline:
            pass
