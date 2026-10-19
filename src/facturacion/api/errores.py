"""Manejadores de errores: respuestas uniformes y sin detalles internos (OWASP A05/A09)."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from facturacion.correo.puertos import ErrorCorreo
from facturacion.firma.puertos import ErrorFirma
from facturacion.servicios.facturacion import ErrorNegocio, EstadoNoPermitido

registro_log = logging.getLogger(__name__)


def _respuesta(codigo: int, detalle: object) -> JSONResponse:
    return JSONResponse(status_code=codigo, content={"detalle": detalle})


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validacion(_: Request, error: RequestValidationError) -> JSONResponse:
        # No se devuelve el valor recibido ("input") para no reflejar datos sensibles.
        errores = [
            {"campo": ".".join(str(parte) for parte in e["loc"]), "mensaje": e["msg"]}
            for e in error.errors()
        ]
        return _respuesta(status.HTTP_422_UNPROCESSABLE_CONTENT, errores)

    @app.exception_handler(EstadoNoPermitido)
    async def _estado(_: Request, error: EstadoNoPermitido) -> JSONResponse:
        return _respuesta(status.HTTP_409_CONFLICT, str(error))

    @app.exception_handler(ErrorNegocio)
    async def _negocio(_: Request, error: ErrorNegocio) -> JSONResponse:
        return _respuesta(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error))

    @app.exception_handler(ErrorCorreo)
    async def _correo(_: Request, error: ErrorCorreo) -> JSONResponse:
        registro_log.warning("correo_fallido: %s", error)
        return _respuesta(status.HTTP_502_BAD_GATEWAY, "No fue posible enviar el correo")

    @app.exception_handler(ErrorFirma)
    async def _firma(_: Request, error: ErrorFirma) -> JSONResponse:
        registro_log.error("firma_fallida: %s", error)
        return _respuesta(status.HTTP_500_INTERNAL_SERVER_ERROR, "Error interno")

    @app.exception_handler(Exception)
    async def _inesperado(_: Request, error: Exception) -> JSONResponse:
        registro_log.exception("error_inesperado", exc_info=error)
        return _respuesta(status.HTTP_500_INTERNAL_SERVER_ERROR, "Error interno")
