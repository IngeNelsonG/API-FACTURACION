"""Adaptador de ``ClienteDian`` que no sale a internet (desarrollo y pruebas).

Hace validaciones mínimas y deterministas sobre el ZIP recibido (un único XML
bien formado, firmado y con CUFE) y responde como lo haría la DIAN, incluido
un ``ApplicationResponse`` marcado explícitamente como simulado.
"""

from __future__ import annotations

import datetime
import io
import logging
import re
import uuid
import zipfile
from pathlib import Path

from lxml import etree

from facturacion.dian.puertos import CODIGO_VALIDACION_EXITOSA, RespuestaDian

logger = logging.getLogger(__name__)

NS_DS = "http://www.w3.org/2000/09/xmldsig#"
NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
NS_APPLICATION_RESPONSE = "urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2"

CODIGO_RECHAZO = "99"
CODIGO_TRACK_ID_NO_ENCONTRADO = "66"
DESCRIPCION_EXITO = "Procesado Correctamente (simulado)"
NOTA_SIMULADA = "Respuesta SIMULADA por la API de facturación: no tiene validez ante la DIAN."

# Límites defensivos contra ZIP bomba.
MAX_TAMANO_XML = 10 * 1024 * 1024
MAX_ENTRADAS_ZIP = 10

_PATRON_CUFE = re.compile(r"^[0-9a-fA-F]{96}$")
_ZONA_COLOMBIA = datetime.timezone(datetime.timedelta(hours=-5))
_PARSER_SEGURO = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)


class _Rechazo(Exception):
    def __init__(self, regla: str, motivo: str) -> None:
        super().__init__(f"Regla: {regla}, Rechazo: {motivo}")


class ClienteDianSimulado:
    """``ClienteDian`` sin red. Si se indica ``directorio``, guarda allí lo recibido."""

    def __init__(self, directorio: Path | None = None) -> None:
        self._directorio = directorio
        self._envios: dict[str, RespuestaDian] = {}

    # --- Operaciones del puerto ---

    def enviar_set_pruebas(self, nombre_zip: str, contenido_zip: bytes) -> RespuestaDian:
        track_id = str(uuid.uuid4())
        respuesta = self._procesar(nombre_zip, contenido_zip, track_id=track_id)
        self._envios[track_id] = respuesta
        return respuesta

    def enviar_factura(self, nombre_zip: str, contenido_zip: bytes) -> RespuestaDian:
        return self._procesar(nombre_zip, contenido_zip, track_id=None)

    def consultar_estado_zip(self, track_id: str) -> RespuestaDian:
        respuesta = self._envios.get(track_id)
        if respuesta is None:
            return RespuestaDian(
                aceptado=False,
                codigo_estado=CODIGO_TRACK_ID_NO_ENCONTRADO,
                descripcion="TrackId no encontrado",
                track_id=track_id,
            )
        return respuesta

    # --- Validación ---

    def _procesar(
        self, nombre_zip: str, contenido_zip: bytes, *, track_id: str | None
    ) -> RespuestaDian:
        self._guardar(nombre_zip, contenido_zip)
        try:
            raiz = _extraer_xml(contenido_zip)
            cufe = _validar_documento(raiz)
        except _Rechazo as rechazo:
            logger.info("Envío simulado rechazado (%s): %s", nombre_zip, rechazo)
            return RespuestaDian(
                aceptado=False,
                codigo_estado=CODIGO_RECHAZO,
                descripcion="Validación contiene errores en campos mandatorios (simulado)",
                mensajes=[str(rechazo)],
                track_id=track_id,
            )
        numero = raiz.findtext(f"{{{NS_CBC}}}ID") or ""
        application_response = construir_application_response(cufe, numero)
        self._guardar(f"ar-{cufe[:16]}.xml", application_response)
        return RespuestaDian(
            aceptado=True,
            codigo_estado=CODIGO_VALIDACION_EXITOSA,
            descripcion=DESCRIPCION_EXITO,
            mensajes=[f"La Factura electrónica {numero}, ha sido autorizada (simulado)."],
            track_id=track_id,
            application_response=application_response,
        )

    def _guardar(self, nombre: str, contenido: bytes) -> None:
        if self._directorio is None:
            return
        self._directorio.mkdir(parents=True, exist_ok=True)
        # Solo el nombre base: evita rutas que salgan del directorio.
        (self._directorio / Path(nombre).name).write_bytes(contenido)


def _extraer_xml(contenido_zip: bytes) -> etree._Element:
    try:
        archivo = zipfile.ZipFile(io.BytesIO(contenido_zip))
    except (zipfile.BadZipFile, ValueError) as exc:
        raise _Rechazo("ZIP01", "el contenido no es un archivo ZIP válido") from exc
    with archivo:
        entradas = [e for e in archivo.infolist() if not e.is_dir()]
        if len(entradas) > MAX_ENTRADAS_ZIP:
            raise _Rechazo("ZIP02", "el ZIP contiene demasiados archivos")
        xmls = [e for e in entradas if e.filename.lower().endswith(".xml")]
        if len(xmls) != 1 or len(entradas) != 1:
            raise _Rechazo("ZIP02", "el ZIP debe contener exactamente un archivo .xml")
        entrada = xmls[0]
        if entrada.file_size > MAX_TAMANO_XML:
            raise _Rechazo("ZIP03", "el XML excede el tamaño máximo permitido")
        try:
            with archivo.open(entrada) as flujo:
                datos = flujo.read(MAX_TAMANO_XML + 1)
        except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
            raise _Rechazo("ZIP01", "no se pudo leer el XML dentro del ZIP") from exc
    if len(datos) > MAX_TAMANO_XML:
        raise _Rechazo("ZIP03", "el XML excede el tamaño máximo permitido")
    try:
        return etree.fromstring(datos, parser=_PARSER_SEGURO)
    except etree.XMLSyntaxError as exc:
        raise _Rechazo("XML01", "el documento XML está mal formado") from exc


def _validar_documento(raiz: etree._Element) -> str:
    """Devuelve el CUFE si el documento pasa las validaciones mínimas."""
    if raiz.find(f".//{{{NS_DS}}}Signature") is None:
        raise _Rechazo("FAD09e", "el documento no contiene firma digital (ds:Signature)")
    cufe = (
        raiz.findtext(f"{{{NS_CBC}}}UUID") or raiz.findtext(f".//{{{NS_CBC}}}UUID") or ""
    ).strip()
    if not cufe:
        raise _Rechazo("FAD06", "el documento no contiene CUFE (cbc:UUID)")
    if not _PATRON_CUFE.fullmatch(cufe):
        raise _Rechazo("FAD06", "el CUFE debe ser un SHA-384 en hexadecimal (96 caracteres)")
    return cufe


def construir_application_response(cufe: str, numero_documento: str = "") -> bytes:
    """``ApplicationResponse`` UBL mínimo con ``ResponseCode`` 02 (documento validado)."""
    ahora = datetime.datetime.now(_ZONA_COLOMBIA)
    raiz = etree.Element(
        f"{{{NS_APPLICATION_RESPONSE}}}ApplicationResponse",
        nsmap={None: NS_APPLICATION_RESPONSE, "cbc": NS_CBC, "cac": NS_CAC},
    )

    def cbc(padre: etree._Element, nombre: str, texto: str, **atributos: str) -> None:
        etree.SubElement(padre, f"{{{NS_CBC}}}{nombre}", **atributos).text = texto

    cbc(raiz, "UBLVersionID", "UBL 2.1")
    cbc(raiz, "CustomizationID", "1")
    cbc(raiz, "ProfileID", "DIAN 2.1")
    cbc(raiz, "ProfileExecutionID", "2")
    cbc(raiz, "ID", str(uuid.uuid4()))
    cbc(raiz, "IssueDate", ahora.date().isoformat())
    cbc(raiz, "IssueTime", ahora.strftime("%H:%M:%S-05:00"))
    cbc(raiz, "Note", NOTA_SIMULADA)

    respuesta_documento = etree.SubElement(raiz, f"{{{NS_CAC}}}DocumentResponse")
    respuesta = etree.SubElement(respuesta_documento, f"{{{NS_CAC}}}Response")
    cbc(respuesta, "ResponseCode", "02")
    cbc(respuesta, "Description", "Documento validado por la DIAN")
    referencia = etree.SubElement(respuesta_documento, f"{{{NS_CAC}}}DocumentReference")
    if numero_documento:
        cbc(referencia, "ID", numero_documento)
    cbc(referencia, "UUID", cufe, schemeName="CUFE-SHA384")

    return etree.tostring(raiz, xml_declaration=True, encoding="UTF-8")
