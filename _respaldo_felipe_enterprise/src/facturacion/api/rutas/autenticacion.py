"""Rutas de autenticación: login (OAuth2 password flow + JWT), registro y perfil."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError

from facturacion.api.dependencias import ContenedorDep, SesionDep, UsuarioDep
from facturacion.api.esquemas import RegistroUsuario, TokenRespuesta, UsuarioRespuesta
from facturacion.persistencia import repositorios
from facturacion.persistencia.modelos import Rol, Usuario
from facturacion.seguridad import contrasenas
from facturacion.seguridad.tokens import TokenInvalido, emitir_token, validar_token

router = APIRouter(prefix="/api/v1/auth", tags=["autenticación"])
registro_log = logging.getLogger(__name__)
_token_opcional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def _ip_cliente(request: Request) -> str:
    return request.client.host if request.client else "desconocida"


@router.post("/login", response_model=TokenRespuesta)
def iniciar_sesion(
    request: Request,
    formulario: Annotated[OAuth2PasswordRequestForm, Depends()],
    contenedor: ContenedorDep,
    sesion: SesionDep,
) -> TokenRespuesta:
    email = formulario.username.strip().lower()[:254]
    ip = _ip_cliente(request)
    clave_limite = f"{ip}|{email}"
    limitador = contenedor.limitador_login
    limitador_ip = contenedor.limitador_login_ip
    if limitador.bloqueado(clave_limite) or limitador_ip.bloqueado(ip):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Demasiados intentos fallidos. Intente más tarde.",
            headers={"Retry-After": str(contenedor.config.login_ventana_segundos)},
        )

    usuario = repositorios.buscar_usuario_por_email(sesion, email)
    contrasena = formulario.password[: contrasenas.LONGITUD_MAXIMA + 1]
    valido = contrasenas.verificar(usuario.hash_contrasena if usuario else None, contrasena)
    if not valido or usuario is None or not usuario.activo:
        limitador.registrar_fallo(clave_limite)
        limitador_ip.registrar_fallo(ip)
        registro_log.warning("login_fallido", extra={"ip": ip})
        # Mensaje único: no revelar si el correo existe.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    limitador.reiniciar(clave_limite)
    if contrasenas.requiere_rehash(usuario.hash_contrasena):
        usuario.hash_contrasena = contrasenas.generar_hash(contrasena)
        sesion.commit()
    token, expira_en = emitir_token(usuario.id, usuario.rol, contenedor.config)
    registro_log.info("login_exitoso", extra={"usuario_id": usuario.id})
    return TokenRespuesta(access_token=token, expires_in=expira_en)


@router.post("/registro", response_model=UsuarioRespuesta, status_code=status.HTTP_201_CREATED)
def registrar_usuario(
    datos: RegistroUsuario,
    contenedor: ContenedorDep,
    sesion: SesionDep,
    token: Annotated[str | None, Depends(_token_opcional)],
) -> Usuario:
    """Crea usuarios. Solo un administrador puede crear administradores.

    Si ``REGISTRO_PUBLICO`` está desactivado (por defecto), requiere un administrador.
    """
    solicitante: Usuario | None = None
    if token:
        try:
            solicitante = sesion.get(Usuario, validar_token(token, contenedor.config).usuario_id)
        except TokenInvalido:
            solicitante = None
    es_admin = (
        solicitante is not None and solicitante.activo and (solicitante.rol == Rol.ADMINISTRADOR)
    )
    if not es_admin and (not contenedor.config.registro_publico or datos.rol != Rol.FACTURADOR):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Permisos insuficientes")

    try:
        contrasenas.validar_politica(datos.contrasena)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None

    usuario = Usuario(
        email=datos.email.lower(),
        nombre=datos.nombre,
        hash_contrasena=contrasenas.generar_hash(datos.contrasena),
        rol=datos.rol,
    )
    sesion.add(usuario)
    try:
        sesion.commit()
    except IntegrityError:
        sesion.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "El correo ya está registrado") from None
    return usuario


@router.get("/yo", response_model=UsuarioRespuesta)
def perfil(usuario: UsuarioDep) -> Usuario:
    return usuario
