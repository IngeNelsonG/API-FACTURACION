"""Contrato del servicio de correo saliente."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class ErrorCorreo(Exception):
    """El mensaje no pudo entregarse al servidor de correo."""


@dataclass(frozen=True, slots=True)
class Adjunto:
    nombre: str
    contenido: bytes
    tipo_mime: str  # p. ej. "application/pdf"


@dataclass(frozen=True, slots=True)
class MensajeCorreo:
    destinatario: str
    asunto: str
    cuerpo_texto: str
    adjuntos: list[Adjunto] = field(default_factory=list)


class ServicioCorreo(Protocol):
    def enviar(self, mensaje: MensajeCorreo) -> None: ...
