"""Limitador de intentos en memoria (ventana deslizante) para frenar fuerza bruta.

Es por proceso: con varias réplicas debe sustituirse por uno respaldado en Redis
(ver ``docs/security/modelo-de-amenazas.md``).
"""

from __future__ import annotations

import threading
import time
from collections import deque


class LimitadorIntentos:
    def __init__(self, max_intentos: int, ventana_segundos: float) -> None:
        self._max = max_intentos
        self._ventana = ventana_segundos
        self._intentos: dict[str, deque[float]] = {}
        self._candado = threading.Lock()

    def _purgar(self, clave: str, ahora: float) -> int:
        """Descarta los intentos vencidos y devuelve cuántos quedan.

        Las claves sin intentos vigentes se eliminan para que la memoria no crezca con
        cada correo o IP distinta que se pruebe.
        """
        registros = self._intentos.get(clave)
        if registros is None:
            return 0
        while registros and ahora - registros[0] > self._ventana:
            registros.popleft()
        if not registros:
            del self._intentos[clave]
        return len(registros)

    def bloqueado(self, clave: str) -> bool:
        with self._candado:
            return self._purgar(clave, time.monotonic()) >= self._max

    def registrar_fallo(self, clave: str) -> None:
        with self._candado:
            ahora = time.monotonic()
            self._purgar(clave, ahora)
            self._intentos.setdefault(clave, deque()).append(ahora)

    def reiniciar(self, clave: str) -> None:
        with self._candado:
            self._intentos.pop(clave, None)
