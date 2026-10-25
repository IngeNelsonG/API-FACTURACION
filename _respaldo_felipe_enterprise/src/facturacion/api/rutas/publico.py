"""Rutas sin autenticación: salud y verificación pública de una factura desde su QR."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from facturacion.api.dependencias import ContenedorDep, SesionDep
from facturacion.api.esquemas import VerificacionPublica
from facturacion.persistencia import repositorios

router = APIRouter(tags=["público"])


@router.get("/salud")
def salud() -> dict[str, str]:
    return {"estado": "ok"}


@router.get("/api/v1/verificacion/{cufe}", response_model=VerificacionPublica)
def verificar_factura(
    cufe: Annotated[str, Path(pattern=r"^[0-9a-f]{96}$")],
    sesion: SesionDep,
    contenedor: ContenedorDep,
) -> VerificacionPublica:
    """Evidencia pública de la factura a la que apunta el QR.

    El CUFE (SHA-384) no es adivinable; aun así solo se exponen datos del emisor y
    del documento, nunca del adquiriente.
    """
    registro = repositorios.obtener_factura_por_cufe(sesion, cufe)
    if registro is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Factura no encontrada")
    emisor = registro.datos["emisor"]
    return VerificacionPublica(
        numero=registro.numero,
        cufe=registro.cufe,
        fecha_emision=registro.fecha_emision,
        emisor_nit=emisor["nit"],
        emisor_razon_social=emisor["razon_social"],
        total=registro.total,
        estado=registro.estado,
    )
