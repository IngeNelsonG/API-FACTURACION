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
# La interfaz web solo carga recursos propios: sin scripts/estilos en línea ni orígenes externos.
_CSP_WEB = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; "
    "connect-src 'self'; font-src 'self'; base-uri 'none'; form-action 'self'; "
    "frame-ancestors 'none'"
)


def _es_ruta_web(ruta: str) -> bool:
    return ruta == "/app" or ruta.startswith(("/app/", "/verificar/"))


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
        ruta = request.url.path
        if _es_ruta_web(ruta):
            respuesta.headers["Content-Security-Policy"] = _CSP_WEB
            # JS/CSS/SVG pueden revalidarse (ETag); el HTML nunca se guarda en caché.
            es_html = respuesta.headers.get("content-type", "").startswith("text/html")
            es_activo = respuesta.status_code in (200, 304) and not es_html
            respuesta.headers["Cache-Control"] = "no-cache" if es_activo else "no-store"
        elif not ruta.startswith(RUTAS_DOCUMENTACION):
            # Swagger UI necesita cargar scripts; el resto de la API no sirve HTML.
            respuesta.headers["Content-Security-Policy"] = _CSP_API
            respuesta.headers["Cache-Control"] = "no-store"
        if hsts:
            respuesta.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return respuesta
