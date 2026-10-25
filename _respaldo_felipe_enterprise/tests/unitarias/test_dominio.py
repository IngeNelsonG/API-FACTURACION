from __future__ import annotations

from datetime import date, time, timedelta, timezone
from decimal import Decimal

import pytest

from facturacion.dominio.cufe import (
    calcular_cufe,
    calcular_software_security_code,
    contenido_qr,
    formatear_hora,
)
from facturacion.dominio.factura import (
    Adquiriente,
    Emisor,
    Factura,
    LineaFactura,
    Numeracion,
    TipoDocumentoIdentidad,
)

COT = timezone(timedelta(hours=-5))
EMISOR = Emisor(
    nit="700085371",
    dv="1",
    razon_social="EMISOR",
    nombre_comercial="EMISOR",
    tipo_organizacion="1",
    responsabilidades="O-13",
    direccion="Calle 1",
    ciudad="Bogotá",
    codigo_municipio="11001",
    departamento="Bogotá",
    codigo_departamento="11",
    email="e@example.com",
    telefono="1",
)
ADQUIRIENTE = Adquiriente(
    tipo_documento=TipoDocumentoIdentidad.NIT,
    numero_documento="800199436",
    dv="1",
    nombre="ADQUIRIENTE",
    email="a@example.com",
)


def _factura(lineas: list[LineaFactura], prefijo: str = "", numero: int = 323200000129) -> Factura:
    return Factura(
        emisor=EMISOR,
        adquiriente=ADQUIRIENTE,
        lineas=lineas,
        numeracion=Numeracion(
            prefijo, numero, "18760000001", date(2019, 1, 1), date(2030, 1, 1), 1, 999999999999
        ),
        fecha_emision=date(2019, 1, 16),
        hora_emision=time(10, 53, 10, tzinfo=COT),
    )


def test_cufe_coincide_con_el_ejemplo_del_anexo_tecnico():
    # Ejemplo de cálculo del CUFE publicado en el Anexo Técnico de la DIAN.
    factura = _factura([LineaFactura("Producto", Decimal("1"), Decimal("1500000.00"))])
    cufe = calcular_cufe(factura, "693ff6f2a553c3646a063436fd4dd9ded0311471", "1")
    assert cufe == (
        "8bb918b19ba22a694f1da11c643b5e9de39adf60311cf179179e9b33381030bc"
        "d4c3c3f156c506ed5908f9276f5bd9b4"
    )


def test_totales_agrupan_iva_por_tarifa_con_redondeo_half_up():
    factura = _factura(
        [
            LineaFactura("A", Decimal("3"), Decimal("33.33"), Decimal("19")),
            LineaFactura("B", Decimal("1"), Decimal("10.05"), Decimal("5")),
            LineaFactura("C", Decimal("2"), Decimal("7.00"), Decimal("0")),
        ]
    )
    totales = factura.totales
    assert totales.subtotal == Decimal("124.04")
    # 99.99 * 19% = 18.9981 -> 19.00 ; 10.05 * 5% = 0.5025 -> 0.50
    assert totales.total_iva == Decimal("19.50")
    assert totales.total_a_pagar == Decimal("143.54")
    assert [i.porcentaje for i in totales.impuestos_iva] == [Decimal(0), Decimal(5), Decimal(19)]


@pytest.mark.parametrize(
    ("cantidad", "precio", "iva"),
    [
        (Decimal("0"), Decimal("1"), Decimal("19")),
        (Decimal("1"), Decimal("-1"), Decimal("19")),
        (Decimal("1"), Decimal("1"), Decimal("16")),
    ],
)
def test_linea_invalida(cantidad, precio, iva):
    with pytest.raises(ValueError):
        LineaFactura("X", cantidad, precio, iva)


def test_factura_sin_lineas_o_sin_zona_horaria():
    with pytest.raises(ValueError):
        _factura([])
    with pytest.raises(ValueError):
        Factura(
            EMISOR,
            ADQUIRIENTE,
            [LineaFactura("A", Decimal(1), Decimal(1))],
            _factura([LineaFactura("A", Decimal(1), Decimal(1))]).numeracion,
            date(2019, 1, 16),
            time(10, 0),
        )


def test_formato_hora_y_qr():
    factura = _factura(
        [LineaFactura("A", Decimal("1"), Decimal("100"))], prefijo="SETP", numero=990000001
    )
    factura.cufe = "f" * 96
    assert formatear_hora(factura) == "10:53:10-05:00"
    qr = contenido_qr(factura, "https://ejemplo/consulta")
    assert "NumFac=SETP990000001" in qr
    assert "ValTolFac=119.00" in qr
    assert qr.endswith("QRCode=https://ejemplo/consulta")


def test_software_security_code():
    codigo = calcular_software_security_code("id", "12345", "SETP1")
    assert len(codigo) == 96
    assert codigo != calcular_software_security_code("id", "12345", "SETP2")
