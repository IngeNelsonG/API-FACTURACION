"""Adaptador de correo saliente por SMTP (STARTTLS o SSL implícito).

La verificación de certificados nunca se desactiva: siempre se usa
``ssl.create_default_context()``. Los errores de red o del servidor se traducen
a ``ErrorCorreo`` con un mensaje genérico; el detalle va al log, sin la clave.
"""

from __future__ import annotations

import logging
import smtplib
import ssl

from facturacion.correo.mensaje import construir_mensaje
from facturacion.correo.puertos import ErrorCorreo, MensajeCorreo

logger = logging.getLogger(__name__)


class ServicioCorreoSmtp:
    def __init__(
        self,
        host: str,
        puerto: int,
        usuario: str,
        clave: str,
        remitente: str,
        usar_starttls: bool = True,
        usar_ssl: bool = False,
        timeout: float = 30,
    ) -> None:
        if usar_ssl and usar_starttls:
            raise ValueError("usar_ssl y usar_starttls son excluyentes")
        self._host = host
        self._puerto = puerto
        self._usuario = usuario
        self._clave = clave
        self._remitente = remitente
        self._usar_starttls = usar_starttls
        self._usar_ssl = usar_ssl
        self._timeout = timeout

    def __repr__(self) -> str:
        # Evita que la clave termine en logs o trazas por accidente.
        return f"ServicioCorreoSmtp(host={self._host!r}, puerto={self._puerto})"

    def enviar(self, mensaje: MensajeCorreo) -> None:
        correo = construir_mensaje(mensaje, self._remitente)
        contexto = ssl.create_default_context()
        try:
            if self._usar_ssl:
                conexion: smtplib.SMTP = smtplib.SMTP_SSL(
                    self._host, self._puerto, timeout=self._timeout, context=contexto
                )
            else:
                conexion = smtplib.SMTP(self._host, self._puerto, timeout=self._timeout)
            with conexion:
                if self._usar_starttls:
                    conexion.starttls(context=contexto)
                if self._usuario:
                    conexion.login(self._usuario, self._clave)
                conexion.send_message(correo)
        except (smtplib.SMTPException, OSError) as exc:
            logger.warning(
                "Fallo al enviar correo por SMTP a %s:%s (%s: %s)",
                self._host,
                self._puerto,
                type(exc).__name__,
                exc,
            )
            raise ErrorCorreo("No fue posible enviar el correo") from exc
        logger.info("Correo enviado por SMTP (Message-ID %s)", correo["Message-ID"])
