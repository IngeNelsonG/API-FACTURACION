from __future__ import annotations

import re
from pathlib import Path

import pytest

from facturacion.web.rutas import DIRECTORIO_ESTATICO

CUFE_VALIDO = "a1" * 48
SUMIDEROS_PROHIBIDOS = (
    "innerHTML",
    "outerHTML",
    "insertAdjacentHTML",
    "document.write",
    "eval(",
    "new Function",
)


def test_raiz_redirige_a_la_app(cliente):
    respuesta = cliente.get("/", follow_redirects=False)
    assert respuesta.status_code == 307
    assert respuesta.headers["location"] == "/app/"


def test_app_sirve_html_con_modulo(cliente):
    respuesta = cliente.get("/app/")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/html")
    assert "Facturación Electrónica" in respuesta.text
    assert '<script type="module" src="/app/js/app.js"></script>' in respuesta.text
    assert respuesta.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    ("ruta", "tipo"),
    [
        ("/app/js/app.js", "javascript"),
        ("/app/js/api.js", "javascript"),
        ("/app/css/estilos.css", "text/css"),
        ("/app/img/logo.svg", "image/svg+xml"),
    ],
)
def test_activos_con_tipo_correcto(cliente, ruta, tipo):
    respuesta = cliente.get(ruta)
    assert respuesta.status_code == 200
    assert tipo in respuesta.headers["content-type"]
    assert respuesta.headers["cache-control"] == "no-cache"
    assert respuesta.headers["x-content-type-options"] == "nosniff"


def test_activo_inexistente_y_salida_del_directorio(cliente):
    assert cliente.get("/app/js/no-existe.js").status_code == 404
    assert cliente.get("/app/..%2F..%2Fweb%2Frutas.py").status_code == 404


def test_csp_estricta_en_la_interfaz(cliente):
    for ruta in ("/app/", f"/verificar/{CUFE_VALIDO}"):
        csp = cliente.get(ruta).headers["content-security-policy"]
        assert "script-src 'self'" in csp
        assert "style-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "unsafe-inline" not in csp
        assert "unsafe-eval" not in csp


def test_pagina_de_verificacion(cliente):
    respuesta = cliente.get(f"/verificar/{CUFE_VALIDO}")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/html")
    assert "/app/js/verificar.js" in respuesta.text
    assert respuesta.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("cufe", ["abc", "A1" * 48, "a1" * 47, "g" * 96])
def test_verificacion_rechaza_cufe_invalido(cliente, cufe):
    respuesta = cliente.get(f"/verificar/{cufe}")
    assert 400 <= respuesta.status_code < 500


def test_api_conserva_csp_restrictiva(cliente):
    respuesta = cliente.get("/salud")
    assert (
        respuesta.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    )
    respuesta = cliente.get(f"/api/v1/verificacion/{CUFE_VALIDO}")
    assert respuesta.headers["content-security-policy"].startswith("default-src 'none'")
    assert respuesta.headers["cache-control"] == "no-store"


def _archivos(extension: str) -> list[Path]:
    archivos = sorted(DIRECTORIO_ESTATICO.rglob(f"*.{extension}"))
    assert archivos, f"no hay archivos .{extension}"
    return archivos


def test_javascript_sin_sumideros_peligrosos():
    for archivo in _archivos("js"):
        contenido = archivo.read_text(encoding="utf-8")
        for sumidero in SUMIDEROS_PROHIBIDOS:
            assert sumidero not in contenido, f"{sumidero} en {archivo.name}"


def test_html_sin_scripts_estilos_ni_manejadores_en_linea():
    for archivo in _archivos("html"):
        contenido = archivo.read_text(encoding="utf-8")
        assert not re.search(r"<script(?![^>]*\bsrc=)", contenido), archivo.name
        assert "<style" not in contenido, archivo.name
        assert not re.search(r"\sstyle\s*=", contenido), archivo.name
        assert not re.search(r"\son[a-z]+\s*=", contenido, re.IGNORECASE), archivo.name
        # Sin recursos de otros orígenes (CDN, fuentes externas).
        assert not re.search(r"(src|href)=\"(https?:)?//", contenido), archivo.name
