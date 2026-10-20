"""Contrato del firmador de documentos XML (XAdES-EPES, Política de Firma DIAN v2)."""

from __future__ import annotations

from typing import Protocol


class ErrorFirma(Exception):
    """El certificado no se pudo cargar o el documento no se pudo firmar."""


class FirmadorXml(Protocol):
    def firmar(self, xml: bytes) -> bytes:
        """Devuelve el documento UBL con ``ds:Signature`` dentro de ``UBLExtension[2]``."""
        ...
