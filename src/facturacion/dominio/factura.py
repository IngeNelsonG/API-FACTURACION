"""Modelo de dominio de la factura electrónica de venta.

Es código puro (sin FastAPI ni SQLAlchemy) para que pueda probarse y
reutilizarse en la generación del XML, el CUFE y la representación gráfica.
Todos los montos usan ``Decimal`` con redondeo ``ROUND_HALF_UP`` a 2 decimales,
porque el mismo valor debe aparecer idéntico en el XML y en la cadena del CUFE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

DOS_DECIMALES = Decimal("0.01")
CERO = Decimal("0.00")
TARIFAS_IVA_PERMITIDAS = (Decimal("0"), Decimal("5"), Decimal("19"))


def redondear(valor: Decimal) -> Decimal:
    return valor.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)


class TipoDocumentoIdentidad(StrEnum):
    """Lista de valores 13.2.1 del Anexo Técnico (subconjunto de uso común)."""

    REGISTRO_CIVIL = "11"
    TARJETA_IDENTIDAD = "12"
    CEDULA_CIUDADANIA = "13"
    TARJETA_EXTRANJERIA = "21"
    CEDULA_EXTRANJERIA = "22"
    NIT = "31"
    PASAPORTE = "41"
    DOCUMENTO_EXTRANJERO = "42"
    PEP = "47"
    NIT_OTRO_PAIS = "50"
    PPT = "48"


class FormaPago(StrEnum):
    CONTADO = "1"
    CREDITO = "2"


@dataclass(frozen=True, slots=True)
class Emisor:
    nit: str
    dv: str
    razon_social: str
    nombre_comercial: str
    tipo_organizacion: str
    responsabilidades: str
    direccion: str
    ciudad: str
    codigo_municipio: str
    departamento: str
    codigo_departamento: str
    email: str
    telefono: str


@dataclass(frozen=True, slots=True)
class Adquiriente:
    tipo_documento: TipoDocumentoIdentidad
    numero_documento: str
    nombre: str
    email: str
    direccion: str = ""
    ciudad: str = ""
    codigo_municipio: str = "11001"
    departamento: str = "Bogotá"
    codigo_departamento: str = "11"
    telefono: str = ""
    dv: str | None = None

    @property
    def es_persona_juridica(self) -> bool:
        return self.tipo_documento is TipoDocumentoIdentidad.NIT


@dataclass(frozen=True, slots=True)
class LineaFactura:
    descripcion: str
    cantidad: Decimal
    precio_unitario: Decimal
    porcentaje_iva: Decimal = Decimal("19")
    codigo: str = ""
    unidad_medida: str = "94"  # 94 = unidad (lista de valores UN/ECE rec 20)

    def __post_init__(self) -> None:
        if self.cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor que cero")
        if self.precio_unitario < 0:
            raise ValueError("El precio unitario no puede ser negativo")
        if self.porcentaje_iva not in TARIFAS_IVA_PERMITIDAS:
            raise ValueError(f"Tarifa de IVA no soportada: {self.porcentaje_iva}")

    @property
    def subtotal(self) -> Decimal:
        return redondear(self.cantidad * self.precio_unitario)

    @property
    def valor_iva(self) -> Decimal:
        return redondear(self.subtotal * self.porcentaje_iva / Decimal("100"))

    @property
    def total(self) -> Decimal:
        return self.subtotal + self.valor_iva


@dataclass(frozen=True, slots=True)
class ResumenImpuesto:
    porcentaje: Decimal
    base: Decimal
    valor: Decimal


@dataclass(frozen=True, slots=True)
class Totales:
    subtotal: Decimal
    total_iva: Decimal
    total_inc: Decimal
    total_ica: Decimal
    total_impuestos: Decimal
    total_a_pagar: Decimal
    impuestos_iva: tuple[ResumenImpuesto, ...]


@dataclass(frozen=True, slots=True)
class Numeracion:
    prefijo: str
    numero: int
    resolucion: str
    fecha_desde: date
    fecha_hasta: date
    rango_desde: int
    rango_hasta: int

    @property
    def numero_completo(self) -> str:
        return f"{self.prefijo}{self.numero}"


@dataclass(slots=True)
class Factura:
    emisor: Emisor
    adquiriente: Adquiriente
    lineas: list[LineaFactura]
    numeracion: Numeracion
    fecha_emision: date
    hora_emision: time  # con tzinfo -05:00
    forma_pago: FormaPago = FormaPago.CONTADO
    medio_pago: str = "10"  # 10 = efectivo (lista 13.3.4.2)
    fecha_vencimiento: date | None = None
    notas: str = ""
    moneda: str = "COP"
    cufe: str = ""
    totales: Totales = field(init=False)

    def __post_init__(self) -> None:
        if not self.lineas:
            raise ValueError("La factura debe tener al menos una línea")
        if self.hora_emision.tzinfo is None:
            raise ValueError("La hora de emisión debe incluir zona horaria (-05:00)")
        self.totales = calcular_totales(self.lineas)


def calcular_totales(lineas: list[LineaFactura]) -> Totales:
    subtotal = sum((linea.subtotal for linea in lineas), CERO)
    por_tarifa: dict[Decimal, tuple[Decimal, Decimal]] = {}
    for linea in lineas:
        base, valor = por_tarifa.get(linea.porcentaje_iva, (CERO, CERO))
        por_tarifa[linea.porcentaje_iva] = (base + linea.subtotal, valor + linea.valor_iva)

    impuestos_iva = tuple(
        ResumenImpuesto(porcentaje=tarifa, base=base, valor=valor)
        for tarifa, (base, valor) in sorted(por_tarifa.items())
    )
    total_iva = sum((impuesto.valor for impuesto in impuestos_iva), CERO)
    total_inc = CERO
    total_ica = CERO
    total_impuestos = total_iva + total_inc + total_ica
    return Totales(
        subtotal=subtotal,
        total_iva=total_iva,
        total_inc=total_inc,
        total_ica=total_ica,
        total_impuestos=total_impuestos,
        total_a_pagar=subtotal + total_impuestos,
        impuestos_iva=impuestos_iva,
    )
