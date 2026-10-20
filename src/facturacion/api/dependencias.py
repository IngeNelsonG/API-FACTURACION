"""Inyección de dependencias de FastAPI: sesión de BD, servicios y usuario autenticado."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, sessionmaker

from facturacion.configuracion import Configuracion
from facturacion.persistencia.modelos import Rol, Usuario
from facturacion.seguridad.limitador import LimitadorIntentos
from facturacion.seguridad.tokens import TokenInvalido, validar_token
from facturacion.servicios.facturacion import ServicioFacturacion

esquema_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@dataclass(slots=True)
class Contenedor:
    config: Configuracion
    fabrica_sesiones: sessionmaker[Session]
    facturacion: ServicioFacturacion
    limitador_login: LimitadorIntentos
    # Límite por IP sin importar el correo: frena el rociado de contraseñas.
    limitador_login_ip: LimitadorIntentos


def obtener_contenedor(request: Request) -> Contenedor:
    return request.app.state.contenedor


ContenedorDep = Annotated[Contenedor, Depends(obtener_contenedor)]


def obtener_sesion(contenedor: ContenedorDep) -> Iterator[Session]:
    with contenedor.fabrica_sesiones() as sesion:
        try:
            yield sesion
        except Exception:
            sesion.rollback()
            raise


SesionDep = Annotated[Session, Depends(obtener_sesion)]

_NO_AUTENTICADO = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciales inválidas o expiradas",
    headers={"WWW-Authenticate": "Bearer"},
)


def usuario_actual(
    token: Annotated[str, Depends(esquema_oauth2)],
    contenedor: ContenedorDep,
    sesion: SesionDep,
) -> Usuario:
    try:
        datos = validar_token(token, contenedor.config)
    except TokenInvalido:
        raise _NO_AUTENTICADO from None
    usuario = sesion.get(Usuario, datos.usuario_id)
    # El rol se toma de la base de datos, no del token: así un cambio de rol o una
    # desactivación surten efecto sin esperar a que el token expire.
    if usuario is None or not usuario.activo:
        raise _NO_AUTENTICADO
    return usuario


UsuarioDep = Annotated[Usuario, Depends(usuario_actual)]


def requerir_rol(*roles: Rol) -> Callable[[Usuario], Usuario]:
    def verificar(usuario: UsuarioDep) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Permisos insuficientes")
        return usuario

    return verificar


AdministradorDep = Annotated[Usuario, Depends(requerir_rol(Rol.ADMINISTRADOR))]
