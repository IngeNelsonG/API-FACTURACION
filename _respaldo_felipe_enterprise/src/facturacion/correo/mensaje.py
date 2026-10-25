"""Construcción y validación del mensaje MIME común a todos los adaptadores de correo.

Toda la validación vive aquí para que el adaptador simulado y el SMTP rechacen
exactamente lo mismo: direcciones inválidas, saltos de línea en encabezados
(inyección de encabezados como ``Bcc:``) y adjuntos que superen el límite.
"""

from __future__ import annotations

from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formatdate, make_msgid

from email_validator import EmailNotValidError, validate_email

from facturacion.correo.puertos import ErrorCorreo, MensajeCorreo

TAMANO_MAXIMO_ADJUNTOS = 10 * 1024 * 1024  # 10 MB en total por mensaje


def _sin_saltos_de_linea(valor: str, campo: str) -> None:
    if "\r" in valor or "\n" in valor:
        raise ErrorCorreo(f"El campo {campo} no puede contener saltos de línea")


def validar_direccion(direccion: str, campo: str) -> str:
    """Devuelve la dirección normalizada o lanza ``ErrorCorreo`` si no es válida."""
    _sin_saltos_de_linea(direccion, campo)
    try:
        resultado = validate_email(direccion, check_deliverability=False)
    except EmailNotValidError as exc:
        raise ErrorCorreo(f"La dirección de correo del campo {campo} no es válida") from exc
    return resultado.normalized


def construir_mensaje(mensaje: MensajeCorreo, remitente: str) -> EmailMessage:
    """Arma el ``EmailMessage`` con encabezados, cuerpo de texto y adjuntos."""
    origen = validar_direccion(remitente, "remitente")
    destino = validar_direccion(mensaje.destinatario, "destinatario")
    _sin_saltos_de_linea(mensaje.asunto, "asunto")

    tamano_total = sum(len(adjunto.contenido) for adjunto in mensaje.adjuntos)
    if tamano_total > TAMANO_MAXIMO_ADJUNTOS:
        raise ErrorCorreo("Los adjuntos superan el tamaño máximo permitido (10 MB)")

    correo = EmailMessage(policy=SMTP)
    correo["From"] = origen
    correo["To"] = destino
    correo["Subject"] = mensaje.asunto
    correo["Date"] = formatdate(localtime=True)
    correo["Message-ID"] = make_msgid(domain=origen.rsplit("@", 1)[1])
    correo.set_content(mensaje.cuerpo_texto)

    for adjunto in mensaje.adjuntos:
        _sin_saltos_de_linea(adjunto.nombre, "nombre del adjunto")
        tipo_principal, separador, subtipo = adjunto.tipo_mime.partition("/")
        if not separador or not tipo_principal or not subtipo:
            raise ErrorCorreo(f"Tipo MIME inválido para el adjunto: {adjunto.tipo_mime!r}")
        _sin_saltos_de_linea(adjunto.tipo_mime, "tipo MIME del adjunto")
        correo.add_attachment(
            adjunto.contenido,
            maintype=tipo_principal,
            subtype=subtipo,
            filename=adjunto.nombre,
        )
    return correo
