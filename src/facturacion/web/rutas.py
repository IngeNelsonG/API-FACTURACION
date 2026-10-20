"""Rutas que sirven la interfaz web estática.

La SPA vive en ``/app/`` (enrutamiento por hash) y la página pública a la que apunta
el QR en ``/verificar/{cufe}``. Ningún HTML se genera con datos: todo el contenido
dinámico se construye en el navegador con ``textContent`` y la CSP lo refuerza.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Request, Response
from fastapi import Path as ParametroRuta
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

DIRECTORIO_ESTATICO = Path(__file__).parent / "static"
PATRON_CUFE = r"^[0-9a-f]{96}$"

router = APIRouter(include_in_schema=False)
# StaticFiles resuelve rutas de forma segura (sin salir del directorio) y añade ETag.
_estaticos = StaticFiles(directory=DIRECTORIO_ESTATICO, html=True)


@router.get("/")
def raiz() -> RedirectResponse:
    return RedirectResponse("/app/", status_code=307)


@router.get("/app")
def app_sin_barra() -> RedirectResponse:
    return RedirectResponse("/app/", status_code=307)


@router.get("/app/{ruta:path}")
async def archivos_app(ruta: str, request: Request) -> Response:
    return await _estaticos.get_response(ruta, request.scope)


@router.get("/verificar/{cufe}")
def pagina_verificacion(
    cufe: Annotated[str, ParametroRuta(pattern=PATRON_CUFE)],
) -> FileResponse:
    # El CUFE se valida aquí; el HTML es estático y el navegador lo lee desde la URL.
    return FileResponse(DIRECTORIO_ESTATICO / "verificar.html", media_type="text/html")
