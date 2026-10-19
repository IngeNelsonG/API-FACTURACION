"""Generación del código QR que acompaña la representación gráfica de la factura.

El contenido lo arma ``facturacion.dominio.cufe.contenido_qr``; este módulo solo
lo codifica. Se usa corrección de errores nivel "M" y el margen de 4 módulos que
recomienda la norma ISO/IEC 18004 para que los lectores lo reconozcan impreso.
"""

from __future__ import annotations

import io

import segno

NIVEL_CORRECCION = "M"
MARGEN_MODULOS = 4


def _crear_qr(contenido: str) -> segno.QRCode:
    if not contenido:
        raise ValueError("El contenido del QR no puede estar vacío")
    return segno.make_qr(contenido, error=NIVEL_CORRECCION)


def generar_qr_png(contenido: str, escala: int = 6) -> bytes:
    """Imagen PNG del QR; ``escala`` es el tamaño en píxeles de cada módulo."""
    if escala < 1:
        raise ValueError("La escala del QR debe ser mayor o igual a 1")
    salida = io.BytesIO()
    _crear_qr(contenido).save(salida, kind="png", scale=escala, border=MARGEN_MODULOS)
    return salida.getvalue()


def generar_qr_svg(contenido: str) -> bytes:
    """Imagen SVG del QR (vectorial, útil para la interfaz web)."""
    salida = io.BytesIO()
    _crear_qr(contenido).save(salida, kind="svg", border=MARGEN_MODULOS, xmldecl=False)
    return salida.getvalue()
