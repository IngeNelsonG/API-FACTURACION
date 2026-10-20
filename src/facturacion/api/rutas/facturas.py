"""Rutas de facturas: emitir, consultar, descargar (PDF/XML/QR) y enviar por correo."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from facturacion.api.dependencias import ContenedorDep, SesionDep, UsuarioDep
from facturacion.api.esquemas import (
    CorreoEntrada,
    CorreoRespuesta,
    FacturaDetalle,
    FacturaEntrada,
    FacturaResumen,
    PaginaFacturas,
    RespuestaDianSalida,
)
from facturacion.dominio.factura import Adquiriente, LineaFactura
from facturacion.persistencia import repositorios
from facturacion.persistencia.modelos import FacturaRegistro, Rol, Usuario
from facturacion.servicios.facturacion import ServicioFacturacion, SolicitudFactura

router = APIRouter(prefix="/api/v1/facturas", tags=["facturas"])
PREFIJO = router.prefix


def _cargar(sesion: SesionDep, factura_id: str, usuario: Usuario) -> FacturaRegistro:
    # Un administrador ve todas las facturas; un facturador solo las suyas (evita IDOR).
    dueno = None if usuario.rol == Rol.ADMINISTRADOR else usuario
    registro = repositorios.obtener_factura(sesion, factura_id, dueno)
    if registro is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Factura no encontrada")
    return registro


def _detalle(registro: FacturaRegistro, servicio: ServicioFacturacion) -> FacturaDetalle:
    base = f"{PREFIJO}/{registro.id}"
    return FacturaDetalle(
        **FacturaResumen.model_validate(registro).model_dump(),
        adquiriente_email=registro.adquiriente_email,
        track_id=registro.track_id,
        correo_enviado_en=registro.correo_enviado_en,
        respuesta_dian=RespuestaDianSalida.model_validate(registro.respuesta_dian or {}),
        url_verificacion=servicio.url_registro(registro),
        enlaces={
            "pdf": f"{base}/pdf",
            "xml": f"{base}/xml",
            "qr": f"{base}/qr",
            "correo": f"{base}/correo",
        },
    )


def _descarga(contenido: bytes, tipo: str, nombre: str) -> Response:
    return Response(
        content=contenido,
        media_type=tipo,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.post("", response_model=FacturaDetalle, status_code=status.HTTP_201_CREATED)
def emitir_factura(
    datos: FacturaEntrada, usuario: UsuarioDep, sesion: SesionDep, contenedor: ContenedorDep
) -> FacturaDetalle:
    solicitud = SolicitudFactura(
        adquiriente=Adquiriente(**datos.adquiriente.model_dump()),
        lineas=[
            LineaFactura(
                descripcion=linea.descripcion,
                cantidad=linea.cantidad,
                precio_unitario=linea.precio_unitario,
                porcentaje_iva=Decimal(linea.porcentaje_iva),
                codigo=linea.codigo,
            )
            for linea in datos.lineas
        ],
        forma_pago=datos.forma_pago,
        medio_pago=datos.medio_pago,
        fecha_vencimiento=datos.fecha_vencimiento,
        notas=datos.notas,
    )
    registro = contenedor.facturacion.emitir(sesion, usuario, solicitud)
    return _detalle(registro, contenedor.facturacion)


@router.get("", response_model=PaginaFacturas)
def listar_facturas(
    usuario: UsuarioDep,
    sesion: SesionDep,
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
) -> PaginaFacturas:
    dueno = None if usuario.rol == Rol.ADMINISTRADOR else usuario
    filas, total = repositorios.listar_facturas(sesion, dueno, limite, desplazamiento)
    return PaginaFacturas(
        total=total,
        limite=limite,
        desplazamiento=desplazamiento,
        elementos=[FacturaResumen.model_validate(fila) for fila in filas],
    )


@router.get("/{factura_id}", response_model=FacturaDetalle)
def obtener_factura(
    factura_id: str, usuario: UsuarioDep, sesion: SesionDep, contenedor: ContenedorDep
) -> FacturaDetalle:
    return _detalle(_cargar(sesion, factura_id, usuario), contenedor.facturacion)


@router.get(
    "/{factura_id}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def descargar_pdf(
    factura_id: str, usuario: UsuarioDep, sesion: SesionDep, contenedor: ContenedorDep
) -> Response:
    registro = _cargar(sesion, factura_id, usuario)
    return _descarga(
        contenedor.facturacion.pdf(registro), "application/pdf", f"{registro.numero}.pdf"
    )


@router.get(
    "/{factura_id}/xml",
    response_class=Response,
    responses={200: {"content": {"application/xml": {}}}},
)
def descargar_xml(factura_id: str, usuario: UsuarioDep, sesion: SesionDep) -> Response:
    registro = _cargar(sesion, factura_id, usuario)
    if not registro.xml_firmado:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El XML de esta factura no está disponible")
    return _descarga(registro.xml_firmado, "application/xml", f"{registro.nombre_archivo}.xml")


@router.get(
    "/{factura_id}/qr", response_class=Response, responses={200: {"content": {"image/png": {}}}}
)
def descargar_qr(
    factura_id: str, usuario: UsuarioDep, sesion: SesionDep, contenedor: ContenedorDep
) -> Response:
    registro = _cargar(sesion, factura_id, usuario)
    return Response(content=contenedor.facturacion.qr_png(registro), media_type="image/png")


@router.post("/{factura_id}/correo", response_model=CorreoRespuesta)
def enviar_por_correo(
    factura_id: str,
    usuario: UsuarioDep,
    sesion: SesionDep,
    contenedor: ContenedorDep,
    datos: CorreoEntrada | None = None,
) -> CorreoRespuesta:
    registro = _cargar(sesion, factura_id, usuario)
    destinatario = datos.destinatario if datos else None
    enviado_a = contenedor.facturacion.enviar_correo(sesion, registro, destinatario)
    return CorreoRespuesta(enviado_a=enviado_a)


@router.post("/{factura_id}/reintentar-envio", response_model=FacturaDetalle)
def reintentar_envio(
    factura_id: str, usuario: UsuarioDep, sesion: SesionDep, contenedor: ContenedorDep
) -> FacturaDetalle:
    registro = _cargar(sesion, factura_id, usuario)
    return _detalle(
        contenedor.facturacion.reintentar_envio(sesion, registro), contenedor.facturacion
    )


@router.post("/{factura_id}/consultar-estado", response_model=FacturaDetalle)
def consultar_estado(
    factura_id: str, usuario: UsuarioDep, sesion: SesionDep, contenedor: ContenedorDep
) -> FacturaDetalle:
    registro = _cargar(sesion, factura_id, usuario)
    return _detalle(
        contenedor.facturacion.actualizar_estado(sesion, registro), contenedor.facturacion
    )
