"""Conversión entre la factura de dominio y la instantánea JSON guardada en la base de datos.

La instantánea incluye al emisor y la numeración vigentes al momento de emitir,
para que el PDF y el QR se puedan regenerar aunque la configuración cambie.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from facturacion.dominio.factura import (
    Adquiriente,
    Emisor,
    Factura,
    FormaPago,
    LineaFactura,
    Numeracion,
    TipoDocumentoIdentidad,
)


def _a_json(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, dict):
        return {clave: _a_json(v) for clave, v in valor.items()}
    if isinstance(valor, list | tuple):
        return [_a_json(v) for v in valor]
    return valor


def factura_a_json(factura: Factura) -> dict[str, Any]:
    emision = datetime.combine(factura.fecha_emision, factura.hora_emision)
    return {
        "version": 1,
        "emisor": _a_json(asdict(factura.emisor)),
        "adquiriente": _a_json(asdict(factura.adquiriente)),
        "lineas": [_a_json(asdict(linea)) for linea in factura.lineas],
        "numeracion": _a_json(asdict(factura.numeracion)),
        "emision": emision.isoformat(),
        "forma_pago": factura.forma_pago.value,
        "medio_pago": factura.medio_pago,
        "fecha_vencimiento": _a_json(factura.fecha_vencimiento),
        "notas": factura.notas,
        "moneda": factura.moneda,
        "cufe": factura.cufe,
    }


def factura_desde_json(datos: dict[str, Any]) -> Factura:
    adquiriente = dict(datos["adquiriente"])
    adquiriente["tipo_documento"] = TipoDocumentoIdentidad(adquiriente["tipo_documento"])
    numeracion = dict(datos["numeracion"])
    numeracion["fecha_desde"] = date.fromisoformat(numeracion["fecha_desde"])
    numeracion["fecha_hasta"] = date.fromisoformat(numeracion["fecha_hasta"])
    lineas = [
        LineaFactura(
            descripcion=linea["descripcion"],
            cantidad=Decimal(linea["cantidad"]),
            precio_unitario=Decimal(linea["precio_unitario"]),
            porcentaje_iva=Decimal(linea["porcentaje_iva"]),
            codigo=linea["codigo"],
            unidad_medida=linea["unidad_medida"],
        )
        for linea in datos["lineas"]
    ]
    emision = datetime.fromisoformat(datos["emision"])
    vencimiento = datos.get("fecha_vencimiento")
    factura = Factura(
        emisor=Emisor(**datos["emisor"]),
        adquiriente=Adquiriente(**adquiriente),
        lineas=lineas,
        numeracion=Numeracion(**numeracion),
        fecha_emision=emision.date(),
        hora_emision=emision.timetz(),
        forma_pago=FormaPago(datos["forma_pago"]),
        medio_pago=datos["medio_pago"],
        fecha_vencimiento=date.fromisoformat(vencimiento) if vencimiento else None,
        notas=datos["notas"],
        moneda=datos["moneda"],
    )
    factura.cufe = datos["cufe"]
    return factura
