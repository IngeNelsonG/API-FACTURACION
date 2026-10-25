"""Cálculo del CUFE, el SoftwareSecurityCode y el contenido del QR (Anexo Técnico v1.9)."""

from __future__ import annotations

import hashlib
from decimal import Decimal

from facturacion.dominio.factura import Factura

CODIGO_IVA = "01"
CODIGO_INC = "04"
CODIGO_ICA = "03"


def _monto(valor: Decimal) -> str:
    return f"{valor:.2f}"


def cadena_cufe(factura: Factura, clave_tecnica: str, tipo_ambiente: str) -> str:
    """Cadena concatenada sin separadores sobre la que se calcula el SHA-384."""
    totales = factura.totales
    return "".join(
        (
            factura.numeracion.numero_completo,
            factura.fecha_emision.isoformat(),
            formatear_hora(factura),
            _monto(totales.subtotal),
            CODIGO_IVA,
            _monto(totales.total_iva),
            CODIGO_INC,
            _monto(totales.total_inc),
            CODIGO_ICA,
            _monto(totales.total_ica),
            _monto(totales.total_a_pagar),
            factura.emisor.nit,
            factura.adquiriente.numero_documento,
            clave_tecnica,
            tipo_ambiente,
        )
    )


def calcular_cufe(factura: Factura, clave_tecnica: str, tipo_ambiente: str) -> str:
    """CUFE = SHA-384 en hexadecimal minúscula (96 caracteres)."""
    cadena = cadena_cufe(factura, clave_tecnica, tipo_ambiente)
    return hashlib.sha384(cadena.encode("utf-8")).hexdigest()


def calcular_software_security_code(software_id: str, pin: str, numero_documento: str) -> str:
    return hashlib.sha384(f"{software_id}{pin}{numero_documento}".encode()).hexdigest()


def contenido_qr(factura: Factura, url_consulta: str) -> str:
    """Texto del QR según el anexo: datos básicos de la factura y la URL de consulta."""
    totales = factura.totales
    return "\n".join(
        (
            f"NumFac={factura.numeracion.numero_completo}",
            f"FecFac={factura.fecha_emision.isoformat()}",
            f"HorFac={formatear_hora(factura)}",
            f"NitFac={factura.emisor.nit}",
            f"DocAdq={factura.adquiriente.numero_documento}",
            f"ValFac={_monto(totales.subtotal)}",
            f"ValIva={_monto(totales.total_iva)}",
            f"ValOtroIm={_monto(totales.total_inc + totales.total_ica)}",
            f"ValTolFac={_monto(totales.total_a_pagar)}",
            f"CUFE={factura.cufe}",
            f"QRCode={url_consulta}",
        )
    )


def formatear_hora(factura: Factura) -> str:
    """Hora en formato ``HH:MM:SS-05:00`` exigido por el anexo."""
    hora = factura.hora_emision
    desfase = hora.strftime("%z")
    return f"{hora.strftime('%H:%M:%S')}{desfase[:3]}:{desfase[3:]}"
