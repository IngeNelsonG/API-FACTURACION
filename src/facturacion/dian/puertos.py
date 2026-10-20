"""Contrato (puerto) del cliente de servicios web de la DIAN.

La aplicación depende solo de este protocolo; hay dos adaptadores:
``ClienteDianSimulado`` (sin red, para desarrollo y tests) y
``ClienteDianSoap`` (SOAP 1.2 + WS-Security contra el ambiente de habilitación).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

CODIGO_VALIDACION_EXITOSA = "00"


class ErrorDian(Exception):
    """Fallo de comunicación o de protocolo con la DIAN (no un rechazo de validación)."""


@dataclass(frozen=True, slots=True)
class RespuestaDian:
    aceptado: bool
    codigo_estado: str
    descripcion: str
    mensajes: list[str] = field(default_factory=list)
    track_id: str | None = None
    # ApplicationResponse firmado por la DIAN (XML ya decodificado de Base64), si viene.
    application_response: bytes | None = None


class ClienteDian(Protocol):
    def enviar_set_pruebas(self, nombre_zip: str, contenido_zip: bytes) -> RespuestaDian:
        """``SendTestSetAsync``: envío dentro del set de pruebas; devuelve ``track_id``."""
        ...

    def enviar_factura(self, nombre_zip: str, contenido_zip: bytes) -> RespuestaDian:
        """``SendBillSync``: envío con validación inmediata."""
        ...

    def consultar_estado_zip(self, track_id: str) -> RespuestaDian:
        """``GetStatusZip``: resultado de un envío asíncrono."""
        ...
