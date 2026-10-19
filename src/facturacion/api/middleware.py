"""Middleware de seguridad: cabeceras defensivas y límite de tamaño del cuerpo."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse

TAMANO_MAXIMO_CUERPO = 1024 * 1024  # 1 MiB
RUTAS_DOCUMENTACION = ("/docs", "/redoc", "/openapi.json")

_CABECERAS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
_CSP_API = "default-src 'none'; frame-ancestors 'none'"


def registrar_middleware(app: FastAPI, *, hsts: bool) -> None:
    @app.middleware("http")
    async def _seguridad(
        request: Request, siguiente: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        longitud = request.headers.get("content-length")
        if longitud is not None and (
            not longitud.isdigit() or int(longitud) > TAMANO_MAXIMO_CUERPO
        ):
            return JSONResponse(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                content={"detalle": "El cuerpo de la petición es demasiado grande"},
            )
        respuesta = await siguiente(request)
        respuesta.headers.update(_CABECERAS)
        if not request.url.path.startswith(RUTAS_DOCUMENTACION):
            # Swagger UI necesita cargar scripts; el resto de la API no sirve HTML.
            respuesta.headers["Content-Security-Policy"] = _CSP_API
            respuesta.headers["Cache-Control"] = "no-store"
        if hsts:
            respuesta.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return respuesta
