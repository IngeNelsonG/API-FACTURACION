"""Contrato de un proveedor tecnológico autorizado por la DIAN (p. ej. Factus).

En este modo el proveedor asigna el número, calcula el CUFE, firma con su propio
certificado y transmite a la DIAN. La API solo le entrega los datos de negocio
de la factura (ver ``docs/decisions/ADR-004-proveedor-tecnologico-factus.md``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from facturacion.dominio.factura import Factura, Numeracion


class ErrorProveedor(Exception):
    """Fallo de comunicación, autenticación o protocolo con el proveedor."""


class RechazoProveedor(Exception):
    """El proveedor o la DIAN rechazaron la factura; ``mensajes`` es seguro de mostrar."""

    def __init__(self, mensajes: list[str]) -> None:
        super().__init__("; ".join(mensajes) or "Factura rechazada por el proveedor")
        self.mensajes = mensajes


@dataclass(frozen=True, slots=True)
class ResultadoEmision:
    numeracion: Numeracion  # prefijo y número asignados por el proveedor
    cufe: str
    url_qr: str  # URL de consulta en la DIAN que va dentro del QR
    mensajes: list[str] = field(default_factory=list)
    xml: bytes | None = None  # XML validado por la DIAN, si el proveedor lo entrega
    identificador_externo: str = ""  # id o número de la factura en el proveedor


class ProveedorFacturacion(Protocol):
    nombre: str

    def emitir(self, factura: Factura, referencia: str) -> ResultadoEmision:
        """Crea y valida la factura. ``referencia`` es única por factura (idempotencia).

        ``factura.numeracion`` y ``factura.cufe`` llegan vacíos: los asigna el proveedor.
        """
        ...
