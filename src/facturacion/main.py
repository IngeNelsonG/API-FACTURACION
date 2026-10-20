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
from facturacion.web import rutas as web

# Atributos que todo LogRecord trae; lo demás proviene de ``extra={...}``.
_ATRIBUTOS_ESTANDAR = frozenset(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


class FormatoConContexto(logging.Formatter):
    """Agrega al final los campos de ``extra`` (``factura_id``, ``ip``...) como clave=valor."""

    def format(self, registro: logging.LogRecord) -> str:
        texto = super().format(registro)
        contexto = {
            clave: valor
            for clave, valor in vars(registro).items()
            if clave not in _ATRIBUTOS_ESTANDAR
        }
        if contexto:
            texto += " " + " ".join(f"{clave}={valor!r}" for clave, valor in contexto.items())
        return texto


def _configurar_logs() -> None:
    raiz = logging.getLogger()
    if any(isinstance(manejador.formatter, FormatoConContexto) for manejador in raiz.handlers):
        return
    manejador = logging.StreamHandler()
    manejador.setFormatter(FormatoConContexto("%(asctime)s %(levelname)s %(name)s %(message)s"))
    raiz.addHandler(manejador)
    raiz.setLevel(logging.INFO)


def crear_app(config: Configuracion | None = None) -> FastAPI:
    config = config or obtener_configuracion()
    _configurar_logs()
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
    app.include_router(web.router)
    return app
