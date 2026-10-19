"""Esquemas de entrada y salida de la API (validación estricta en la frontera de confianza)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from facturacion.dominio.factura import FormaPago, TipoDocumentoIdentidad
from facturacion.persistencia.modelos import EstadoFactura, Rol

TextoCorto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
TextoOpcional = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


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
    nombre: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    email: EmailStr
    direccion: TextoOpcional = ""
    ciudad: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] = ""
    codigo_municipio: Annotated[str, StringConstraints(pattern=r"^\d{5}$")] = "11001"
    departamento: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] = (
        "Bogotá"
    )
    codigo_departamento: Annotated[str, StringConstraints(pattern=r"^\d{2}$")] = "11"
    telefono: Annotated[str, StringConstraints(pattern=r"^[0-9+() -]{0,20}$")] = ""

    @model_validator(mode="after")
    def _dv_para_nit(self) -> AdquirienteEntrada:
        if self.tipo_documento is TipoDocumentoIdentidad.NIT and self.dv is None:
            raise ValueError("El dígito de verificación (dv) es obligatorio para NIT")
        return self


class LineaEntrada(EsquemaEntrada):
    descripcion: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)
    ]
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
    notas: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] = ""

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
