"""Caso de uso principal: emitir una factura electrónica y sus derivados (PDF, QR, correo).

Orquesta el dominio y los adaptadores (firma, DIAN, correo) sin depender de
FastAPI, para poder probarse de forma aislada.
"""

from __future__ import annotations

import io
import logging
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from facturacion.configuracion import URL_CATALOGO_HABILITACION, Configuracion, ModoUrlQr
from facturacion.correo.puertos import Adjunto, MensajeCorreo, ServicioCorreo
from facturacion.dian.puertos import ClienteDian, ErrorDian, RespuestaDian
from facturacion.dominio.cufe import calcular_cufe, calcular_software_security_code, contenido_qr
from facturacion.dominio.factura import (
    Adquiriente,
    Emisor,
    Factura,
    FormaPago,
    LineaFactura,
    Numeracion,
)
from facturacion.firma.puertos import FirmadorXml
from facturacion.persistencia import repositorios
from facturacion.persistencia.modelos import EstadoFactura, FacturaRegistro, Usuario
from facturacion.representacion.pdf import generar_pdf
from facturacion.representacion.qr import generar_qr_png
from facturacion.servicios.serializacion import factura_a_json, factura_desde_json
from facturacion.ubl.empaquetado import empaquetar_zip, nombre_base
from facturacion.ubl.generador import DatosSoftware, generar_xml_factura

registro_log = logging.getLogger(__name__)

# Colombia no tiene horario de verano: el desfase es fijo.
ZONA_COLOMBIA = timezone(timedelta(hours=-5), "COT")


class ErrorNegocio(Exception):
    """Regla de negocio incumplida; el mensaje es seguro para mostrar al cliente."""


class EstadoNoPermitido(ErrorNegocio):
    pass


@dataclass(frozen=True, slots=True)
class SolicitudFactura:
    adquiriente: Adquiriente
    lineas: list[LineaFactura]
    forma_pago: FormaPago = FormaPago.CONTADO
    medio_pago: str = "10"
    fecha_vencimiento: date | None = None
    notas: str = ""


class ServicioFacturacion:
    def __init__(
        self,
        config: Configuracion,
        firmador: FirmadorXml,
        cliente_dian: ClienteDian,
        correo: ServicioCorreo,
    ) -> None:
        self._config = config
        self._firmador = firmador
        self._dian = cliente_dian
        self._correo = correo

    # ------------------------------------------------------------------ emisión
    def emitir(
        self, sesion: Session, usuario: Usuario, solicitud: SolicitudFactura
    ) -> FacturaRegistro:
        config = self._config
        ahora = datetime.now(ZONA_COLOMBIA).replace(microsecond=0)
        if not config.numeracion_fecha_desde <= ahora.date() <= config.numeracion_fecha_hasta:
            raise ErrorNegocio("La resolución de numeración no está vigente")

        numero = repositorios.siguiente_consecutivo(
            sesion, f"factura:{config.numeracion_prefijo}", config.numeracion_desde
        )
        if numero > config.numeracion_hasta:
            raise ErrorNegocio("El rango de numeración autorizado está agotado")

        factura = Factura(
            emisor=self._emisor(),
            adquiriente=solicitud.adquiriente,
            lineas=solicitud.lineas,
            numeracion=Numeracion(
                prefijo=config.numeracion_prefijo,
                numero=numero,
                resolucion=config.numeracion_resolucion,
                fecha_desde=config.numeracion_fecha_desde,
                fecha_hasta=config.numeracion_fecha_hasta,
                rango_desde=config.numeracion_desde,
                rango_hasta=config.numeracion_hasta,
            ),
            fecha_emision=ahora.date(),
            hora_emision=ahora.timetz(),
            forma_pago=solicitud.forma_pago,
            medio_pago=solicitud.medio_pago,
            fecha_vencimiento=solicitud.fecha_vencimiento,
            notas=solicitud.notas,
        )
        factura.cufe = calcular_cufe(
            factura,
            config.numeracion_clave_tecnica.get_secret_value(),
            config.tipo_ambiente_dian,
        )
        software = DatosSoftware(
            software_id=config.dian_software_id,
            software_security_code=calcular_software_security_code(
                config.dian_software_id,
                config.dian_pin.get_secret_value(),
                factura.numeracion.numero_completo,
            ),
            tipo_ambiente=config.tipo_ambiente_dian,
            contenido_qr=self.contenido_qr(factura),
        )
        xml_firmado = self._firmador.firmar(generar_xml_factura(factura, software))

        consecutivo_envio = repositorios.siguiente_consecutivo(sesion, f"envio:{ahora.year}", 1)
        base = nombre_base(config.emisor_nit, ahora.year, consecutivo_envio)
        registro = FacturaRegistro(
            usuario_id=usuario.id,
            numero=factura.numeracion.numero_completo,
            cufe=factura.cufe,
            fecha_emision=factura.fecha_emision,
            adquiriente_nombre=factura.adquiriente.nombre,
            adquiriente_documento=factura.adquiriente.numero_documento,
            adquiriente_email=factura.adquiriente.email,
            total=factura.totales.total_a_pagar,
            estado=EstadoFactura.ERROR_ENVIO,
            datos=factura_a_json(factura),
            nombre_archivo=base,
            xml_firmado=xml_firmado,
        )
        self._transmitir(registro)
        sesion.add(registro)
        sesion.commit()
        registro_log.info(
            "factura_emitida", extra={"factura_id": registro.id, "estado": registro.estado}
        )
        return registro

    def reintentar_envio(self, sesion: Session, registro: FacturaRegistro) -> FacturaRegistro:
        if registro.estado != EstadoFactura.ERROR_ENVIO:
            raise EstadoNoPermitido("Solo se reintentan facturas con error de envío")
        self._transmitir(registro)
        sesion.commit()
        return registro

    def actualizar_estado(self, sesion: Session, registro: FacturaRegistro) -> FacturaRegistro:
        """Consulta ``GetStatusZip`` para las facturas enviadas en el set de pruebas."""
        if registro.estado != EstadoFactura.EN_PROCESO or not registro.track_id:
            raise EstadoNoPermitido("La factura no tiene un envío pendiente de consulta")
        try:
            respuesta = self._dian.consultar_estado_zip(registro.track_id)
        except ErrorDian as error:
            raise ErrorNegocio("No fue posible consultar el estado en la DIAN") from error
        self._aplicar_respuesta(registro, respuesta, asincrono=False)
        sesion.commit()
        return registro

    def _transmitir(self, registro: FacturaRegistro) -> None:
        nombre_xml = f"{registro.nombre_archivo}.xml"
        nombre_zip = f"z{registro.nombre_archivo[2:]}.zip"
        contenido_zip = empaquetar_zip(nombre_xml, registro.xml_firmado)
        usar_set_pruebas = bool(self._config.dian_test_set_id)
        try:
            if usar_set_pruebas:
                respuesta = self._dian.enviar_set_pruebas(nombre_zip, contenido_zip)
            else:
                respuesta = self._dian.enviar_factura(nombre_zip, contenido_zip)
        except ErrorDian:
            registro_log.warning("envio_dian_fallido", extra={"numero": registro.numero})
            registro.estado = EstadoFactura.ERROR_ENVIO
            registro.respuesta_dian = {"descripcion": "No fue posible comunicarse con la DIAN"}
            return
        self._aplicar_respuesta(registro, respuesta, asincrono=usar_set_pruebas)

    @staticmethod
    def _aplicar_respuesta(
        registro: FacturaRegistro, respuesta: RespuestaDian, *, asincrono: bool
    ) -> None:
        registro.respuesta_dian = {
            "codigo": respuesta.codigo_estado,
            "descripcion": respuesta.descripcion,
            "mensajes": respuesta.mensajes,
            "consultado_en": datetime.now(UTC).isoformat(),
        }
        if respuesta.track_id:
            registro.track_id = respuesta.track_id
        if respuesta.application_response:
            registro.application_response = respuesta.application_response
        if asincrono and respuesta.aceptado:
            registro.estado = EstadoFactura.EN_PROCESO
        else:
            registro.estado = (
                EstadoFactura.ACEPTADA if respuesta.aceptado else EstadoFactura.RECHAZADA
            )

    # --------------------------------------------------------------- derivados
    def reconstruir(self, registro: FacturaRegistro) -> Factura:
        return factura_desde_json(registro.datos)

    def url_consulta(self, cufe: str) -> str:
        if self._config.qr_url_modo is ModoUrlQr.DIAN:
            return f"{URL_CATALOGO_HABILITACION}{cufe}"
        return f"{self._config.url_publica_base.rstrip('/')}/api/v1/verificacion/{cufe}"

    def contenido_qr(self, factura: Factura) -> str:
        return contenido_qr(factura, self.url_consulta(factura.cufe))

    def qr_png(self, registro: FacturaRegistro) -> bytes:
        return generar_qr_png(self.contenido_qr(self.reconstruir(registro)))

    def pdf(self, registro: FacturaRegistro) -> bytes:
        factura = self.reconstruir(registro)
        return generar_pdf(factura, self.contenido_qr(factura), str(registro.estado))

    def enviar_correo(
        self, sesion: Session, registro: FacturaRegistro, destinatario: str | None
    ) -> str:
        if registro.estado != EstadoFactura.ACEPTADA:
            raise EstadoNoPermitido("Solo se envían por correo facturas aceptadas por la DIAN")
        destino = destinatario or registro.adquiriente_email
        emisor = self._config.emisor_razon_social
        mensaje = MensajeCorreo(
            destinatario=destino,
            asunto=f"{self._config.emisor_nit};{emisor};{registro.numero};01;{emisor}",
            cuerpo_texto=(
                f"Señor(a) {registro.adquiriente_nombre}:\n\n"
                f"Adjuntamos la factura electrónica {registro.numero} emitida por {emisor}.\n"
                f"CUFE: {registro.cufe}\n"
                f"Puede verificarla en: {self.url_consulta(registro.cufe)}\n"
            ),
            adjuntos=[
                Adjunto(
                    f"{registro.nombre_archivo}.zip",
                    self._zip_adquiriente(registro),
                    "application/zip",
                ),
            ],
        )
        self._correo.enviar(mensaje)
        registro.correo_enviado_en = datetime.now(UTC)
        sesion.commit()
        return destino

    def _zip_adquiriente(self, registro: FacturaRegistro) -> bytes:
        """ZIP con el PDF y el XML firmado, como lo exige el anexo para el adquiriente."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archivo:
            archivo.writestr(f"{registro.nombre_archivo}.pdf", self.pdf(registro))
            archivo.writestr(f"{registro.nombre_archivo}.xml", registro.xml_firmado)
            if registro.application_response:
                archivo.writestr(
                    f"ar{registro.nombre_archivo[2:]}.xml", registro.application_response
                )
        return buffer.getvalue()

    def _emisor(self) -> Emisor:
        c = self._config
        return Emisor(
            nit=c.emisor_nit,
            dv=c.emisor_dv,
            razon_social=c.emisor_razon_social,
            nombre_comercial=c.emisor_nombre_comercial,
            tipo_organizacion=c.emisor_tipo_organizacion,
            responsabilidades=c.emisor_responsabilidades,
            direccion=c.emisor_direccion,
            ciudad=c.emisor_ciudad,
            codigo_municipio=c.emisor_codigo_municipio,
            departamento=c.emisor_departamento,
            codigo_departamento=c.emisor_codigo_departamento,
            email=c.emisor_email,
            telefono=c.emisor_telefono,
        )
