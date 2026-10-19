"""Motor y sesiones de SQLAlchemy."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def crear_motor(database_url: str) -> Engine:
    argumentos: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        # FastAPI atiende peticiones en un pool de hilos; SQLite serializa las escrituras.
        argumentos["connect_args"] = {"check_same_thread": False}
    return create_engine(database_url, pool_pre_ping=True, **argumentos)


def crear_fabrica_sesiones(motor: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=motor, expire_on_commit=False, autoflush=False)


def iterar_sesion(fabrica: sessionmaker[Session]) -> Iterator[Session]:
    with fabrica() as sesion:
        yield sesion
