"""Fábrica de la aplicación FastAPI. El objeto ASGI está en ``facturacion.asgi``."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from facturacion import __version__
from facturacion.api.errores import registrar_manejadores
from facturacion.api.middleware import registrar_middleware
from facturacion.api.rutas import autenticacion, facturas, publico
from facturacion.arranque import construir_contenedor
from facturacion.configuracion import Configuracion, Entorno, obtener_configuracion


def crear_app(config: Configuracion | None = None) -> FastAPI:
    config = config or obtener_configuracion()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    es_produccion = config.entorno is Entorno.PRODUCCION
    app = FastAPI(
        title="API de Facturación Electrónica DIAN",
        version=__version__,
        description="Emisión de facturas electrónicas de venta (ambiente de habilitación DIAN).",
        docs_url=None if es_produccion else "/docs",
        redoc_url=None if es_produccion else "/redoc",
        openapi_url=None if es_produccion else "/openapi.json",
    )
    app.state.contenedor = construir_contenedor(config)
    registrar_manejadores(app)
    registrar_middleware(app, hsts=es_produccion)
    if config.cors_origenes:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_origenes,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
        )
    app.include_router(publico.router)
    app.include_router(autenticacion.router)
    app.include_router(facturas.router)
    return app
