"""Objeto ASGI para el servidor: ``uvicorn facturacion.asgi:app``."""

from facturacion.main import crear_app

app = crear_app()
