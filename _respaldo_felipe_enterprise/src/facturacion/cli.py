"""Comandos de administración: ``python -m facturacion.cli crear-admin --email ... --nombre ...``.

La contraseña se pide por consola (sin eco) o se lee de ``ADMIN_CONTRASENA``;
nunca se pasa como argumento, para que no quede en el historial del shell.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from facturacion.arranque import construir_contenedor
from facturacion.configuracion import obtener_configuracion
from facturacion.persistencia import repositorios
from facturacion.persistencia.modelos import Rol, Usuario
from facturacion.seguridad import contrasenas


def crear_admin(email: str, nombre: str) -> int:
    contrasena = os.environ.get("ADMIN_CONTRASENA") or getpass.getpass("Contraseña: ")
    try:
        contrasenas.validar_politica(contrasena)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    contenedor = construir_contenedor(obtener_configuracion())
    with contenedor.fabrica_sesiones() as sesion:
        if repositorios.buscar_usuario_por_email(sesion, email):
            print("El correo ya está registrado", file=sys.stderr)
            return 1
        sesion.add(
            Usuario(
                email=email.lower(),
                nombre=nombre,
                hash_contrasena=contrasenas.generar_hash(contrasena),
                rol=Rol.ADMINISTRADOR,
            )
        )
        sesion.commit()
    print(f"Administrador {email.lower()} creado")
    return 0


def main(argumentos: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(prog="facturacion")
    subcomandos = analizador.add_subparsers(dest="comando", required=True)
    admin = subcomandos.add_parser("crear-admin", help="Crea un usuario administrador")
    admin.add_argument("--email", required=True)
    admin.add_argument("--nombre", required=True)
    opciones = analizador.parse_args(argumentos)
    return crear_admin(opciones.email, opciones.nombre)


if __name__ == "__main__":
    raise SystemExit(main())
