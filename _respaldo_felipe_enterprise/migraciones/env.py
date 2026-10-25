"""Entorno de Alembic: usa la misma configuración y metadatos que la aplicación."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from facturacion.configuracion import obtener_configuracion
from facturacion.persistencia import modelos  # noqa: F401 - registra las tablas
from facturacion.persistencia.base_datos import Base, crear_motor

if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)

URL = obtener_configuracion().database_url


def ejecutar_offline() -> None:
    context.configure(url=URL, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def ejecutar_online() -> None:
    with crear_motor(URL).connect() as conexion:
        context.configure(connection=conexion, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    ejecutar_offline()
else:
    ejecutar_online()
