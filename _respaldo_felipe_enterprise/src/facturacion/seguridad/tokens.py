"""Emisión y validación de tokens JWT (HS256) de acceso."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from facturacion.configuracion import Configuracion

ALGORITMO = "HS256"
RECLAMOS_OBLIGATORIOS = ["exp", "iat", "nbf", "iss", "aud", "sub", "jti"]


class TokenInvalido(Exception):
    pass


@dataclass(frozen=True, slots=True)
class DatosToken:
    usuario_id: str
    rol: str
    jti: str
    expira: datetime


def emitir_token(usuario_id: str, rol: str, config: Configuracion) -> tuple[str, int]:
    """Devuelve el token y su vigencia en segundos."""
    ahora = datetime.now(UTC)
    vigencia = timedelta(minutes=config.jwt_minutos_expiracion)
    reclamos = {
        "sub": usuario_id,
        "rol": rol,
        "iss": config.jwt_emisor,
        "aud": config.jwt_audiencia,
        "iat": ahora,
        "nbf": ahora,
        "exp": ahora + vigencia,
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(reclamos, config.jwt_secreto.get_secret_value(), algorithm=ALGORITMO)
    return token, int(vigencia.total_seconds())


def validar_token(token: str, config: Configuracion) -> DatosToken:
    try:
        reclamos = jwt.decode(
            token,
            config.jwt_secreto.get_secret_value(),
            # Lista fija de algoritmos: evita ataques de confusión ("alg": "none", RS/HS).
            algorithms=[ALGORITMO],
            audience=config.jwt_audiencia,
            issuer=config.jwt_emisor,
            options={"require": RECLAMOS_OBLIGATORIOS},
            leeway=5,
        )
    except jwt.PyJWTError as error:
        raise TokenInvalido("Token inválido o expirado") from error
    rol = reclamos.get("rol")
    if not isinstance(rol, str):
        raise TokenInvalido("Token sin rol")
    return DatosToken(
        usuario_id=str(reclamos["sub"]),
        rol=rol,
        jti=str(reclamos["jti"]),
        expira=datetime.fromtimestamp(reclamos["exp"], UTC),
    )
