"""Pruebas del QR y de la representación gráfica (PDF) de la factura."""

from __future__ import annotations

import re
from datetime import date, time, timedelta, timezone
from decimal import Decimal

import pytest

from facturacion.dominio.factura import (
    Adquiriente,
    Emisor,
    Factura,
    FormaPago,
    LineaFactura,
    Numeracion,
    TipoDocumentoIdentidad,
)
from facturacion.representacion.pdf import (
    LEYENDA_AMBIENTE,
    SELLO_SIN_VALIDEZ,
    formatear_moneda,
    generar_pdf,
)
from facturacion.representacion.qr import generar_qr_png, generar_qr_svg

COLOMBIA = timezone(timedelta(hours=-5))
CUFE = "ab12" * 24
CONTENIDO_QR = "NumFac=SETP990000001\nCUFE=" + CUFE


def _factura(lineas: list[LineaFactura] | None = None, notas: str = "") -> Factura:
    factura = Factura(
        emisor=Emisor(
            nit="900373115",
            dv="7",
            razon_social="EMPRESA DE PRUEBAS S.A.S.",
            nombre_comercial="EMPRESA DE PRUEBAS",
            tipo_organizacion="1",
            responsabilidades="R-99-PN",
            direccion="CALLE 1 # 1-1",
            ciudad="Bogotá, D.C.",
            codigo_municipio="11001",
            departamento="Bogotá",
            codigo_departamento="11",
            email="facturacion@example.com",
            telefono="6010000000",
        ),
        adquiriente=Adquiriente(
            tipo_documento=TipoDocumentoIdentidad.CEDULA_CIUDADANIA,
            numero_documento="1020304050",
            nombre="Cliente de Pruebas",
            email="cliente@example.com",
            direccion="Carrera 7 # 10-20",
            ciudad="Bogotá, D.C.",
        ),
        lineas=lineas
        or [
            LineaFactura("Servicio de consultoría", Decimal("2"), Decimal("1500000.50")),
            LineaFactura("Libro", Decimal("1"), Decimal("50000"), Decimal("0"), codigo="L-1"),
        ],
        numeracion=Numeracion(
            prefijo="SETP",
            numero=990000001,
            resolucion="18760000001",
            fecha_desde=date(2019, 1, 19),
            fecha_hasta=date(2030, 1, 19),
            rango_desde=990000000,
            rango_hasta=995000000,
        ),
        fecha_emision=date(2026, 10, 19),
        hora_emision=time(10, 30, 0, tzinfo=COLOMBIA),
        forma_pago=FormaPago.CREDITO,
        fecha_vencimiento=date(2026, 11, 18),
        notas=notas,
    )
    factura.cufe = CUFE
    return factura


_CADENA_TJ = re.compile(rb"\(((?:\\.|[^\\)])*)\) Tj")
_ESCAPE_PDF = re.compile(rb"\\([0-7]{1,3}|.)")


def _texto(pdf: bytes) -> str:
    """Extrae y une el texto de los operadores ``Tj`` de un PDF sin comprimir."""

    def _desescapar(coincidencia: re.Match[bytes]) -> bytes:
        valor = coincidencia.group(1)
        if valor[:1].isdigit():
            return bytes([int(valor, 8)])
        return {b"n": b"\n", b"r": b"\r", b"t": b"\t"}.get(valor, valor)

    return "".join(
        _ESCAPE_PDF.sub(_desescapar, cadena).decode("latin-1") for cadena in _CADENA_TJ.findall(pdf)
    )


def _paginas(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf))


def test_qr_png_tiene_firma_png() -> None:
    assert generar_qr_png(CONTENIDO_QR).startswith(b"\x89PNG\r\n\x1a\n")


def test_qr_svg_contiene_svg() -> None:
    assert b"<svg" in generar_qr_svg(CONTENIDO_QR)


@pytest.mark.parametrize("generador", [generar_qr_png, generar_qr_svg])
def test_qr_rechaza_contenido_vacio(generador) -> None:
    with pytest.raises(ValueError):
        generador("")


def test_formatear_moneda_estilo_colombiano() -> None:
    assert formatear_moneda(Decimal("1234567.89")) == "$ 1.234.567,89"
    assert formatear_moneda(Decimal("0")) == "$ 0,00"


def test_pdf_basico_contiene_numero_cufe_y_leyendas() -> None:
    pdf = generar_pdf(_factura(), CONTENIDO_QR, "aceptada", comprimir=False)
    assert pdf.startswith(b"%PDF")
    texto = _texto(pdf)
    assert "SETP990000001" in texto
    assert "FACTURA ELECTRÓNICA DE" in texto
    assert CUFE[:48] in texto
    assert CUFE[48:] in texto
    assert "$ 3.050.001,00" in texto  # subtotal
    assert "$ 3.620.001,19" in texto  # total a pagar
    assert "Resolución DIAN No. 18760000001 del 2019-01-19" in texto
    assert "10:30:00-05:00" in texto
    assert "2026-11-18" in texto  # vencimiento
    assert "Estado DIAN: aceptada" in texto
    assert b"/Subtype /Image" in pdf
    # La franja de ambiente de pruebas siempre aparece; el sello solo si no fue aceptada.
    assert LEYENDA_AMBIENTE in texto
    assert SELLO_SIN_VALIDEZ not in texto


def test_pdf_no_aceptado_lleva_sello() -> None:
    pdf = generar_pdf(_factura(), CONTENIDO_QR, "rechazada", comprimir=False)
    assert SELLO_SIN_VALIDEZ in _texto(pdf)


def test_pdf_comprimido_es_valido() -> None:
    pdf = generar_pdf(_factura(), CONTENIDO_QR, "aceptada")
    assert pdf.startswith(b"%PDF")
    assert b"Cliente de Pruebas" not in pdf


def test_pdf_multipagina_con_qr_y_pie_en_cada_pagina() -> None:
    lineas = [
        LineaFactura(
            f"Producto número {i} con una descripción larga " * 2,
            Decimal("1"),
            Decimal("1000"),
            codigo=f"P{i}",
        )
        for i in range(80)
    ]
    pdf = generar_pdf(_factura(lineas), CONTENIDO_QR, "aceptada", comprimir=False)
    paginas = _paginas(pdf)
    texto = _texto(pdf)
    assert paginas >= 2
    for numero in range(1, paginas + 1):
        assert f"Página {numero}" in texto
    # Una sola imagen embebida, dibujada (Do) en cada página.
    assert len(re.findall(rb" Do\b", pdf)) == paginas


def test_pdf_escapa_marcado_del_usuario() -> None:
    marcado = "<b>x</b> & <font>"
    lineas = [LineaFactura(marcado, Decimal("1"), Decimal("1000"))]
    pdf = generar_pdf(
        _factura(lineas, notas="<para>nota</para>"), CONTENIDO_QR, "aceptada", comprimir=False
    )
    texto = _texto(pdf)
    assert marcado in texto
    assert "<para>nota</para>" in texto
