"""Limitador de intentos en memoria (ventana deslizante) para frenar fuerza bruta.

Es por proceso: con varias réplicas debe sustituirse por uno respaldado en Redis
(ver ``docs/security/modelo-de-amenazas.md``).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class LimitadorIntentos:
    def __init__(self, max_intentos: int, ventana_segundos: float) -> None:
        self._max = max_intentos
        self._ventana = ventana_segundos
        self._intentos: dict[str, deque[float]] = defaultdict(deque)
        self._candado = threading.Lock()

    def _purgar(self, clave: str, ahora: float) -> deque[float]:
        registros = self._intentos[clave]
        while registros and ahora - registros[0] > self._ventana:
            registros.popleft()
        return registros

    def bloqueado(self, clave: str) -> bool:
        with self._candado:
            return len(self._purgar(clave, time.monotonic())) >= self._max

    def registrar_fallo(self, clave: str) -> None:
        with self._candado:
            ahora = time.monotonic()
            self._purgar(clave, ahora).append(ahora)

    def reiniciar(self, clave: str) -> None:
        with self._candado:
            self._intentos.pop(clave, None)
