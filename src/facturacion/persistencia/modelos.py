"""Tablas de la base de datos."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from facturacion.persistencia.base_datos import Base


def _ahora() -> datetime:
    return datetime.now(UTC)


def _nuevo_id() -> str:
    return str(uuid.uuid4())


class Rol(StrEnum):
    ADMINISTRADOR = "administrador"
    FACTURADOR = "facturador"


class EstadoFactura(StrEnum):
    ACEPTADA = "aceptada"
    RECHAZADA = "rechazada"
    EN_PROCESO = "en_proceso"  # enviada al set de pruebas, pendiente de GetStatusZip
    ERROR_ENVIO = "error_envio"  # no se pudo comunicar con la DIAN


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_nuevo_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    hash_contrasena: Mapped[str] = mapped_column(String(255))
    rol: Mapped[Rol] = mapped_column(String(20), default=Rol.FACTURADOR)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class Consecutivo(Base):
    """Contadores atómicos: número de factura por prefijo y consecutivo de envío por año."""

    __tablename__ = "consecutivos"

    clave: Mapped[str] = mapped_column(String(50), primary_key=True)
    valor: Mapped[int] = mapped_column(Integer)


class FacturaRegistro(Base):
    __tablename__ = "facturas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_nuevo_id)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), index=True)
    numero: Mapped[str] = mapped_column(String(30), unique=True)
    cufe: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    fecha_emision: Mapped[date] = mapped_column(Date)
    adquiriente_nombre: Mapped[str] = mapped_column(String(300))
    adquiriente_documento: Mapped[str] = mapped_column(String(30))
    adquiriente_email: Mapped[str] = mapped_column(String(254))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    estado: Mapped[EstadoFactura] = mapped_column(String(20))
    # Copia de los datos de entrada y de la hora exacta para reconstruir la factura.
    datos: Mapped[dict] = mapped_column(JSON)
    nombre_archivo: Mapped[str] = mapped_column(String(40))
    xml_firmado: Mapped[bytes] = mapped_column(LargeBinary)
    respuesta_dian: Mapped[dict] = mapped_column(JSON, default=dict)
    application_response: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    track_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    correo_enviado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)
