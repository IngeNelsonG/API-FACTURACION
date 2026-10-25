"""Nombres de archivo y empaquetado ZIP exigidos por la DIAN."""

from __future__ import annotations

import io
import zipfile

CODIGO_SOFTWARE_PROPIO = "000"
MAX_CONSECUTIVO_ENVIO = 0xFFFFFFFF


def nombre_base(nit: str, anio: int, consecutivo_envio: int, prefijo: str = "fv") -> str:
    """``fv`` + NIT (10 dígitos) + código PT + año (2 dígitos) + consecutivo hexadecimal (8).

    El consecutivo de envío es independiente del número de la factura y no debe
    repetirse dentro del mismo año para el mismo NIT.
    """
    if not nit.isdigit() or len(nit) > 10:
        raise ValueError("El NIT debe tener entre 1 y 10 dígitos")
    if not 0 < consecutivo_envio <= MAX_CONSECUTIVO_ENVIO:
        raise ValueError("Consecutivo de envío fuera de rango")
    return (
        f"{prefijo}{nit.zfill(10)}{CODIGO_SOFTWARE_PROPIO}{anio % 100:02d}{consecutivo_envio:08x}"
    )


def empaquetar_zip(nombre_xml: str, xml: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archivo:
        archivo.writestr(nombre_xml, xml)
    return buffer.getvalue()
