"""Middleware de seguridad: cabeceras defensivas y límite de tamaño del cuerpo."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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


class _CuerpoDemasiadoGrande(Exception):
    pass


class LimiteCuerpo:
    """Corta en 413 las peticiones cuyo cuerpo supera ``TAMANO_MAXIMO_CUERPO``.

    Revisa ``Content-Length`` y además cuenta los bytes recibidos, porque una petición
    con ``Transfer-Encoding: chunked`` no declara su tamaño.
    """

    def __init__(self, app: ASGIApp, maximo: int = TAMANO_MAXIMO_CUERPO) -> None:
        self._app = app
        self._maximo = maximo

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        cabeceras = dict(scope["headers"])
        longitud = cabeceras.get(b"content-length")
        if longitud is not None and (not longitud.isdigit() or int(longitud) > self._maximo):
            await self._rechazar(scope, receive, send)
            return

        recibidos = 0
        excedido = False
        respuesta_iniciada = False

        async def recibir_limitado() -> Message:
            nonlocal recibidos, excedido
            mensaje = await receive()
            if mensaje["type"] == "http.request":
                recibidos += len(mensaje.get("body", b""))
                if recibidos > self._maximo:
                    excedido = True
                    raise _CuerpoDemasiadoGrande
            return mensaje

        async def enviar(mensaje: Message) -> None:
            nonlocal respuesta_iniciada
            if excedido:
                # FastAPI convierte cualquier error al leer el cuerpo en un 400: se
                # descarta esa respuesta y se envía el 413 en su lugar.
                if not respuesta_iniciada:
                    respuesta_iniciada = True
                    await self._rechazar(scope, receive, send)
                return
            respuesta_iniciada = respuesta_iniciada or mensaje["type"] == "http.response.start"
            await send(mensaje)

        try:
            await self._app(scope, recibir_limitado, enviar)
        except _CuerpoDemasiadoGrande:
            if not respuesta_iniciada:
                await self._rechazar(scope, receive, send)

    @staticmethod
    async def _rechazar(scope: Scope, receive: Receive, send: Send) -> None:
        respuesta = JSONResponse(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            content={"detalle": "El cuerpo de la petición es demasiado grande"},
        )
        await respuesta(scope, receive, send)


def registrar_middleware(app: FastAPI, *, hsts: bool) -> None:
    # Se registra primero para quedar por dentro: su 413 también recibe las cabeceras.
    app.add_middleware(LimiteCuerpo)

    @app.middleware("http")
    async def _seguridad(
        request: Request, siguiente: Callable[[Request], Awaitable[Response]]
    ) -> Response:
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
