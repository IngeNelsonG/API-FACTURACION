"""Adaptador de correo simulado: guarda cada mensaje como archivo ``.eml``.

Sirve para desarrollo y pruebas: aplica la misma validación que el adaptador
SMTP pero no sale a la red. El nombre del archivo nunca se deriva de datos del
usuario (marca de tiempo + UUID4) para evitar recorridos de ruta.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

from facturacion.correo.mensaje import construir_mensaje
from facturacion.correo.puertos import ErrorCorreo, MensajeCorreo

logger = logging.getLogger(__name__)


class ServicioCorreoSimulado:
    def __init__(self, directorio: Path, remitente: str) -> None:
        self.directorio = Path(directorio)
        self.remitente = remitente
        self.enviados: list[EmailMessage] = []

    def enviar(self, mensaje: MensajeCorreo) -> None:
        correo = construir_mensaje(mensaje, self.remitente)
        marca = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        ruta = self.directorio / f"{marca}-{uuid.uuid4()}.eml"
        try:
            self.directorio.mkdir(parents=True, exist_ok=True)
            ruta.write_bytes(correo.as_bytes())
        except OSError as exc:
            logger.warning("No se pudo guardar el correo simulado en %s: %s", ruta, exc)
            raise ErrorCorreo("No fue posible enviar el correo") from exc
        self.enviados.append(correo)
        logger.info("Correo simulado guardado en %s", ruta)
