"""Hash de contraseñas con Argon2id (ganador de la Password Hashing Competition).

Se usan los parámetros por defecto de ``argon2-cffi`` (perfil RFC 9106
"low memory": t=3, m=64 MiB, p=4), que superan el mínimo recomendado por OWASP.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

LONGITUD_MINIMA = 12
# Límite superior para evitar DoS con entradas enormes.
LONGITUD_MAXIMA = 128

_hasher = PasswordHasher()
# Hash de una contraseña aleatoria usado cuando el usuario no existe, para que el
# tiempo de respuesta del login no revele qué correos están registrados.
_HASH_SEÑUELO = _hasher.hash("contraseña-señuelo-que-nunca-coincide")


def validar_politica(contrasena: str) -> None:
    if not LONGITUD_MINIMA <= len(contrasena) <= LONGITUD_MAXIMA:
        raise ValueError(
            f"La contraseña debe tener entre {LONGITUD_MINIMA} y {LONGITUD_MAXIMA} caracteres"
        )
    if contrasena.strip() != contrasena or len(set(contrasena)) < 4:
        raise ValueError("La contraseña es demasiado débil")


def generar_hash(contrasena: str) -> str:
    return _hasher.hash(contrasena)


def verificar(hash_guardado: str | None, contrasena: str) -> bool:
    try:
        return _hasher.verify(hash_guardado or _HASH_SEÑUELO, contrasena) and bool(hash_guardado)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def requiere_rehash(hash_guardado: str) -> bool:
    return _hasher.check_needs_rehash(hash_guardado)
