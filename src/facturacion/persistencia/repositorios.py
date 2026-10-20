"""Acceso a datos. Todas las consultas usan el constructor de SQLAlchemy (parametrizadas)."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from facturacion.persistencia.modelos import Consecutivo, FacturaRegistro, Usuario


def siguiente_consecutivo(sesion: Session, clave: str, inicial: int) -> int:
    """Incrementa de forma atómica (``UPDATE ... RETURNING``) y devuelve el nuevo valor.

    El primer valor devuelto para una clave es ``inicial``. Se ejecuta dentro de la
    transacción del llamador: si esta se revierte, el número no se consume.
    """
    sentencia = (
        update(Consecutivo)
        .where(Consecutivo.clave == clave)
        .values(valor=Consecutivo.valor + 1)
        .returning(Consecutivo.valor)
    )
    valor = sesion.execute(sentencia).scalar_one_or_none()
    if valor is not None:
        return valor
    try:
        with sesion.begin_nested():
            sesion.add(Consecutivo(clave=clave, valor=inicial))
        return inicial
    except IntegrityError:
        # Otra transacción creó la fila al mismo tiempo: reintentar el incremento.
        return sesion.execute(sentencia).scalar_one()


def buscar_usuario_por_email(sesion: Session, email: str) -> Usuario | None:
    return sesion.scalar(select(Usuario).where(Usuario.email == email.lower()))


def obtener_factura(
    sesion: Session, factura_id: str, usuario: Usuario | None
) -> FacturaRegistro | None:
    """Devuelve la factura solo si pertenece al usuario (``None`` = sin filtro de dueño)."""
    consulta = select(FacturaRegistro).where(FacturaRegistro.id == factura_id)
    if usuario is not None:
        consulta = consulta.where(FacturaRegistro.usuario_id == usuario.id)
    return sesion.scalar(consulta)


def obtener_factura_por_cufe(sesion: Session, cufe: str) -> FacturaRegistro | None:
    return sesion.scalar(select(FacturaRegistro).where(FacturaRegistro.cufe == cufe))


def listar_facturas(
    sesion: Session, usuario: Usuario | None, limite: int, desplazamiento: int
) -> tuple[list[FacturaRegistro], int]:
    consulta = select(FacturaRegistro)
    conteo = select(func.count()).select_from(FacturaRegistro)
    if usuario is not None:
        consulta = consulta.where(FacturaRegistro.usuario_id == usuario.id)
        conteo = conteo.where(FacturaRegistro.usuario_id == usuario.id)
    filas = sesion.scalars(
        consulta.order_by(FacturaRegistro.creado_en.desc()).limit(limite).offset(desplazamiento)
    ).all()
    return list(filas), sesion.scalar(conteo) or 0
