"""Esquemas de entrada y salida de la API (validación estricta en la frontera de confianza)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from facturacion.dominio.factura import FormaPago, TipoDocumentoIdentidad
from facturacion.persistencia.modelos import EstadoFactura, Rol

# Los caracteres de control no son válidos en XML 1.0: se rechazan en la frontera (422)
# en lugar de fallar al generar el UBL. Las notas admiten saltos de línea y tabulaciones.
SIN_CONTROL = r"^[^\x00-\x1f\x7f]*$"
SIN_CONTROL_MULTILINEA = r"^[^\x00-\x08\x0b\x0c\x0e-\x1f\x7f]*$"


def _texto(max_length: int, min_length: int = 0) -> object:
    return Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=min_length,
            max_length=max_length,
            pattern=SIN_CONTROL,
        ),
    ]


TextoCorto = _texto(120, min_length=1)
TextoOpcional = _texto(200)
TextoLargo = _texto(300, min_length=1)
TextoLugar = _texto(100)


class EsquemaEntrada(BaseModel):
    # Rechazar campos desconocidos evita la asignación masiva de atributos.
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------ autenticación
class TokenRespuesta(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - tipo de token OAuth2, no un secreto
    expires_in: int


class RegistroUsuario(EsquemaEntrada):
    email: EmailStr
    nombre: TextoCorto
    contrasena: Annotated[str, Field(min_length=1, max_length=128)]
    rol: Rol = Rol.FACTURADOR


class UsuarioRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    nombre: str
    rol: Rol
    activo: bool


# ---------------------------------------------------------------------- facturas
class AdquirienteEntrada(EsquemaEntrada):
    tipo_documento: TipoDocumentoIdentidad
    numero_documento: Annotated[str, StringConstraints(pattern=r"^[0-9A-Za-z-]{3,20}$")]
    dv: Annotated[str, StringConstraints(pattern=r"^\d$")] | None = None
    nombre: TextoLargo
    email: EmailStr
    direccion: TextoOpcional = ""
    ciudad: TextoLugar = ""
    codigo_municipio: Annotated[str, StringConstraints(pattern=r"^\d{5}$")] = "11001"
    departamento: TextoLugar = "Bogotá"
    codigo_departamento: Annotated[str, StringConstraints(pattern=r"^\d{2}$")] = "11"
    telefono: Annotated[str, StringConstraints(pattern=r"^[0-9+() -]{0,20}$")] = ""

    @model_validator(mode="after")
    def _dv_para_nit(self) -> AdquirienteEntrada:
        if self.tipo_documento is TipoDocumentoIdentidad.NIT and self.dv is None:
            raise ValueError("El dígito de verificación (dv) es obligatorio para NIT")
        return self


class LineaEntrada(EsquemaEntrada):
    descripcion: TextoLargo
    cantidad: Annotated[Decimal, Field(gt=0, max_digits=15, decimal_places=6)]
    precio_unitario: Annotated[Decimal, Field(ge=0, max_digits=15, decimal_places=2)]
    porcentaje_iva: Literal["0", "5", "19"] = "19"
    codigo: Annotated[str, StringConstraints(pattern=r"^[0-9A-Za-z._-]{0,50}$")] = ""


class FacturaEntrada(EsquemaEntrada):
    adquiriente: AdquirienteEntrada
    lineas: Annotated[list[LineaEntrada], Field(min_length=1, max_length=500)]
    forma_pago: FormaPago = FormaPago.CONTADO
    medio_pago: Annotated[str, StringConstraints(pattern=r"^[0-9A-Z]{1,3}$")] = "10"
    fecha_vencimiento: date | None = None
    notas: Annotated[
        str,
        StringConstraints(strip_whitespace=True, max_length=1000, pattern=SIN_CONTROL_MULTILINEA),
    ] = ""

    @model_validator(mode="after")
    def _vencimiento_para_credito(self) -> FacturaEntrada:
        if self.forma_pago is FormaPago.CREDITO and self.fecha_vencimiento is None:
            raise ValueError("La fecha de vencimiento es obligatoria para pagos a crédito")
        return self


class RespuestaDianSalida(BaseModel):
    codigo: str | None = None
    descripcion: str | None = None
    mensajes: list[str] = []


class FacturaResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    numero: str
    cufe: str
    fecha_emision: date
    adquiriente_nombre: str
    adquiriente_documento: str
    total: Decimal
    estado: EstadoFactura
    creado_en: datetime


class FacturaDetalle(FacturaResumen):
    adquiriente_email: str
    track_id: str | None
    correo_enviado_en: datetime | None
    respuesta_dian: RespuestaDianSalida
    url_verificacion: str
    enlaces: dict[str, str]


class PaginaFacturas(BaseModel):
    total: int
    limite: int
    desplazamiento: int
    elementos: list[FacturaResumen]


class CorreoEntrada(EsquemaEntrada):
    destinatario: EmailStr | None = None


class CorreoRespuesta(BaseModel):
    enviado_a: str


class VerificacionPublica(BaseModel):
    """Datos mínimos para comprobar una factura desde el QR, sin datos del adquiriente."""

    numero: str
    cufe: str
    fecha_emision: date
    emisor_nit: str
    emisor_razon_social: str
    total: Decimal
    estado: EstadoFactura


class ErrorRespuesta(BaseModel):
    detalle: str
