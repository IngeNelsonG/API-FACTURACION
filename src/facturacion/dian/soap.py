"""Adaptador SOAP 1.2 + WS-Security del servicio ``WcfDianCustomerServices`` de la DIAN.

Cada petición lleva en la cabecera WS-Addressing (``wsa:Action`` y ``wsa:To``)
y un ``wsse:Security`` con ``wsu:Timestamp``, el certificado del facturador
como ``wsse:BinarySecurityToken`` y un ``ds:Signature`` (RSA-SHA256,
C14N exclusiva) sobre el elemento ``wsa:To``, tal como en los ejemplos de la
DIAN. La firma se construye directamente con ``lxml`` y ``cryptography``.

Las respuestas se analizan con un parser seguro y buscando los elementos por
nombre local, para no depender de los prefijos que use el servidor WCF.
"""

from __future__ import annotations

import base64
import binascii
import datetime
import hashlib
import logging
import uuid
from typing import Protocol

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import Encoding
from lxml import etree

from facturacion.dian.puertos import ErrorDian, RespuestaDian

logger = logging.getLogger(__name__)

# --- Espacios de nombres ---
NS_SOAP = "http://www.w3.org/2003/05/soap-envelope"
NS_WCF = "http://wcf.dian.colombia"
NS_WSA = "http://www.w3.org/2005/08/addressing"
NS_WSSE = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
NS_WSU = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
NS_DS = "http://www.w3.org/2000/09/xmldsig#"
NS_EC = "http://www.w3.org/2001/10/xml-exc-c14n#"

# --- Acciones del servicio ---
_PREFIJO_ACCION = "http://wcf.dian.colombia/IWcfDianCustomerServices/"
ACCION_SEND_TEST_SET_ASYNC = _PREFIJO_ACCION + "SendTestSetAsync"
ACCION_SEND_BILL_SYNC = _PREFIJO_ACCION + "SendBillSync"
ACCION_GET_STATUS_ZIP = _PREFIJO_ACCION + "GetStatusZip"

# --- Algoritmos y tipos WS-Security ---
ALG_C14N_EXCLUSIVA = "http://www.w3.org/2001/10/xml-exc-c14n#"
ALG_RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
ALG_SHA256 = "http://www.w3.org/2001/04/xmlenc#sha256"
TIPO_BASE64 = (
    "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary"
)
TIPO_X509V3 = (
    "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3"
)

# Prefijos que se conservan en la C14N exclusiva (como en los ejemplos de la DIAN).
_PREFIJOS_INCLUSIVOS_REFERENCIA = ["soap", "wcf"]
_PREFIJOS_INCLUSIVOS_SIGNED_INFO = ["wsa", "soap", "wcf"]

VIGENCIA_TIMESTAMP_SEGUNDOS = 300

# Estado que se devuelve cuando ``SendTestSetAsync`` recibe el ZIP: aún no hay validación.
CODIGO_RECIBIDO_ASINCRONO = "RECIBIDO"

_PARSER_SEGURO = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)

_NSMAP_SOBRE = {"soap": NS_SOAP, "wcf": NS_WCF}


class CredencialWs(Protocol):
    """Lo mínimo que necesita el cliente para firmar la cabecera WS-Security.

    ``FirmadorXades`` cumple este protocolo.
    """

    @property
    def llave_privada(self) -> rsa.RSAPrivateKey: ...

    @property
    def certificado(self) -> x509.Certificate: ...


# --------------------------------------------------------------------------- #
# Construcción del sobre SOAP
# --------------------------------------------------------------------------- #


def _c14n_exclusiva(elemento: etree._Element, prefijos: list[str]) -> bytes:
    return etree.tostring(
        elemento, method="c14n", exclusive=True, with_comments=False, inclusive_ns_prefixes=prefijos
    )


def _formatear_instante(instante: datetime.datetime) -> str:
    """``2026-01-01T12:00:00.000Z``: formato de ``wsu:Created``/``wsu:Expires``."""
    utc = instante.astimezone(datetime.UTC)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z"


def construir_sobre(
    accion: str,
    cuerpo: etree._Element,
    *,
    url: str,
    llave_privada: rsa.RSAPrivateKey,
    certificado: x509.Certificate,
    ahora: datetime.datetime | None = None,
    vigencia_segundos: int = VIGENCIA_TIMESTAMP_SEGUNDOS,
) -> bytes:
    """Arma el sobre SOAP 1.2 con WS-Addressing y WS-Security firmado.

    ``cuerpo`` es el elemento que va dentro de ``soap:Body`` (p. ej.
    ``wcf:SendBillSync``). Función pura: no hace red, útil para pruebas.
    """
    ahora = ahora or datetime.datetime.now(datetime.UTC)
    sufijo = uuid.uuid4().hex.upper()
    id_timestamp = f"TS-{sufijo}"
    id_token = f"X509-{sufijo}"
    id_firma = f"SIG-{sufijo}"
    id_key_info = f"KI-{sufijo}"
    id_str = f"STR-{sufijo}"
    id_to = f"id-{sufijo}"

    sobre = etree.Element(f"{{{NS_SOAP}}}Envelope", nsmap=_NSMAP_SOBRE)
    cabecera = etree.SubElement(sobre, f"{{{NS_SOAP}}}Header", nsmap={"wsa": NS_WSA})

    seguridad = etree.SubElement(
        cabecera,
        f"{{{NS_WSSE}}}Security",
        {f"{{{NS_SOAP}}}mustUnderstand": "true"},
        nsmap={"wsse": NS_WSSE, "wsu": NS_WSU},
    )
    timestamp = etree.SubElement(
        seguridad, f"{{{NS_WSU}}}Timestamp", {f"{{{NS_WSU}}}Id": id_timestamp}
    )
    etree.SubElement(timestamp, f"{{{NS_WSU}}}Created").text = _formatear_instante(ahora)
    etree.SubElement(timestamp, f"{{{NS_WSU}}}Expires").text = _formatear_instante(
        ahora + datetime.timedelta(seconds=vigencia_segundos)
    )
    token = etree.SubElement(
        seguridad,
        f"{{{NS_WSSE}}}BinarySecurityToken",
        {"EncodingType": TIPO_BASE64, "ValueType": TIPO_X509V3, f"{{{NS_WSU}}}Id": id_token},
    )
    token.text = base64.b64encode(certificado.public_bytes(Encoding.DER)).decode("ascii")

    firma = etree.SubElement(
        seguridad, f"{{{NS_DS}}}Signature", {"Id": id_firma}, nsmap={"ds": NS_DS}
    )

    etree.SubElement(cabecera, f"{{{NS_WSA}}}Action").text = accion
    destino = etree.SubElement(
        cabecera, f"{{{NS_WSA}}}To", {f"{{{NS_WSU}}}Id": id_to}, nsmap={"wsu": NS_WSU}
    )
    destino.text = url

    etree.SubElement(sobre, f"{{{NS_SOAP}}}Body").append(cuerpo)

    # --- SignedInfo: se calcula con el sobre ya armado (la C14N depende del contexto) ---
    signed_info = etree.SubElement(firma, f"{{{NS_DS}}}SignedInfo")
    metodo_c14n = etree.SubElement(
        signed_info, f"{{{NS_DS}}}CanonicalizationMethod", Algorithm=ALG_C14N_EXCLUSIVA
    )
    etree.SubElement(
        metodo_c14n,
        f"{{{NS_EC}}}InclusiveNamespaces",
        PrefixList=" ".join(_PREFIJOS_INCLUSIVOS_SIGNED_INFO),
        nsmap={"ec": NS_EC},
    )
    etree.SubElement(signed_info, f"{{{NS_DS}}}SignatureMethod", Algorithm=ALG_RSA_SHA256)
    referencia = etree.SubElement(signed_info, f"{{{NS_DS}}}Reference", URI=f"#{id_to}")
    transformaciones = etree.SubElement(referencia, f"{{{NS_DS}}}Transforms")
    transformacion = etree.SubElement(
        transformaciones, f"{{{NS_DS}}}Transform", Algorithm=ALG_C14N_EXCLUSIVA
    )
    etree.SubElement(
        transformacion,
        f"{{{NS_EC}}}InclusiveNamespaces",
        PrefixList=" ".join(_PREFIJOS_INCLUSIVOS_REFERENCIA),
        nsmap={"ec": NS_EC},
    )
    etree.SubElement(referencia, f"{{{NS_DS}}}DigestMethod", Algorithm=ALG_SHA256)
    resumen = hashlib.sha256(_c14n_exclusiva(destino, _PREFIJOS_INCLUSIVOS_REFERENCIA)).digest()
    etree.SubElement(referencia, f"{{{NS_DS}}}DigestValue").text = base64.b64encode(resumen).decode(
        "ascii"
    )

    valor_firma = etree.SubElement(firma, f"{{{NS_DS}}}SignatureValue")
    key_info = etree.SubElement(firma, f"{{{NS_DS}}}KeyInfo", Id=id_key_info)
    referencia_token = etree.SubElement(
        key_info, f"{{{NS_WSSE}}}SecurityTokenReference", {f"{{{NS_WSU}}}Id": id_str}
    )
    etree.SubElement(
        referencia_token, f"{{{NS_WSSE}}}Reference", URI=f"#{id_token}", ValueType=TIPO_X509V3
    )

    firma_bytes = llave_privada.sign(
        _c14n_exclusiva(signed_info, _PREFIJOS_INCLUSIVOS_SIGNED_INFO),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    valor_firma.text = base64.b64encode(firma_bytes).decode("ascii")

    return etree.tostring(sobre, xml_declaration=False, encoding="UTF-8")


def _elemento_wcf(nombre: str, hijos: dict[str, str]) -> etree._Element:
    raiz = etree.Element(f"{{{NS_WCF}}}{nombre}", nsmap={"wcf": NS_WCF})
    for etiqueta, texto in hijos.items():
        etree.SubElement(raiz, f"{{{NS_WCF}}}{etiqueta}").text = texto
    return raiz


def cuerpo_send_test_set_async(
    nombre_zip: str, contenido_zip: bytes, test_set_id: str
) -> etree._Element:
    return _elemento_wcf(
        "SendTestSetAsync",
        {
            "fileName": nombre_zip,
            "contentFile": base64.b64encode(contenido_zip).decode("ascii"),
            "testSetId": test_set_id,
        },
    )


def cuerpo_send_bill_sync(nombre_zip: str, contenido_zip: bytes) -> etree._Element:
    return _elemento_wcf(
        "SendBillSync",
        {"fileName": nombre_zip, "contentFile": base64.b64encode(contenido_zip).decode("ascii")},
    )


def cuerpo_get_status_zip(track_id: str) -> etree._Element:
    return _elemento_wcf("GetStatusZip", {"trackId": track_id})


# --------------------------------------------------------------------------- #
# Análisis de respuestas
# --------------------------------------------------------------------------- #


def _local(elemento: etree._Element) -> str:
    return etree.QName(elemento).localname if isinstance(elemento.tag, str) else ""


def _hijo(elemento: etree._Element, nombre: str) -> etree._Element | None:
    for hijo in elemento:
        if _local(hijo) == nombre:
            return hijo
    return None


def _buscar(elemento: etree._Element, nombre: str) -> etree._Element | None:
    for nodo in elemento.iter():
        if _local(nodo) == nombre:
            return nodo
    return None


def _texto(elemento: etree._Element | None, nombre: str) -> str:
    if elemento is None:
        return ""
    hijo = _hijo(elemento, nombre)
    return (hijo.text or "").strip() if hijo is not None else ""


def _parsear_sobre(contenido: bytes) -> etree._Element:
    try:
        raiz = etree.fromstring(contenido, parser=_PARSER_SEGURO)
    except etree.XMLSyntaxError as exc:
        raise ErrorDian("Respuesta de la DIAN con XML inválido") from exc
    cuerpo = (
        next((h for h in raiz if _local(h) == "Body"), None) if _local(raiz) == "Envelope" else None
    )
    if cuerpo is None:
        raise ErrorDian("Respuesta de la DIAN sin sobre SOAP válido")
    return cuerpo


def _descripcion_fault(contenido: bytes) -> str | None:
    """Texto del ``soap:Fault`` (solo para el log), si la respuesta lo trae."""
    try:
        raiz = etree.fromstring(contenido, parser=_PARSER_SEGURO)
    except etree.XMLSyntaxError:
        return None
    fault = _buscar(raiz, "Fault")
    if fault is None:
        return None
    texto = _buscar(fault, "Text")
    if texto is None:
        texto = _buscar(fault, "faultstring")
    return (texto.text or "").strip() if texto is not None else "soap:Fault sin descripción"


def interpretar_dian_response(nodo: etree._Element) -> RespuestaDian:
    """Convierte un ``DianResponse`` (SendBillSync / GetStatusZip) en ``RespuestaDian``."""
    mensajes: list[str] = []
    estado = _texto(nodo, "StatusMessage")
    if estado:
        mensajes.append(estado)
    errores = _hijo(nodo, "ErrorMessage")
    if errores is not None:
        mensajes.extend((e.text or "").strip() for e in errores if _local(e) == "string" and e.text)

    application_response: bytes | None = None
    base64_ar = _texto(nodo, "XmlBase64Bytes")
    if base64_ar:
        try:
            application_response = base64.b64decode(base64_ar, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ErrorDian("La DIAN devolvió un ApplicationResponse con Base64 inválido") from exc

    return RespuestaDian(
        aceptado=_texto(nodo, "IsValid").lower() == "true",
        codigo_estado=_texto(nodo, "StatusCode"),
        descripcion=_texto(nodo, "StatusDescription"),
        mensajes=mensajes,
        track_id=_texto(nodo, "XmlDocumentKey") or None,
        application_response=application_response,
    )


def interpretar_send_bill_sync(contenido: bytes) -> RespuestaDian:
    cuerpo = _parsear_sobre(contenido)
    resultado = _buscar(cuerpo, "SendBillSyncResult")
    if resultado is None:
        raise ErrorDian("Respuesta de SendBillSync sin SendBillSyncResult")
    return interpretar_dian_response(resultado)


def interpretar_get_status_zip(contenido: bytes) -> RespuestaDian:
    cuerpo = _parsear_sobre(contenido)
    resultado = _buscar(cuerpo, "GetStatusZipResult")
    if resultado is None:
        raise ErrorDian("Respuesta de GetStatusZip sin GetStatusZipResult")
    primero = _hijo(resultado, "DianResponse")
    if primero is None:
        raise ErrorDian("Respuesta de GetStatusZip sin DianResponse")
    return interpretar_dian_response(primero)


def interpretar_send_test_set_async(contenido: bytes) -> RespuestaDian:
    cuerpo = _parsear_sobre(contenido)
    resultado = _buscar(cuerpo, "SendTestSetAsyncResult")
    if resultado is None:
        raise ErrorDian("Respuesta de SendTestSetAsync sin SendTestSetAsyncResult")
    mensajes: list[str] = []
    lista = _hijo(resultado, "ErrorMessageList")
    if lista is not None:
        for item in lista:
            mensaje = _texto(item, "ProcessedMessage")
            if mensaje:
                mensajes.append(mensaje)
    track_id = _texto(resultado, "ZipKey") or None
    if track_id:
        return RespuestaDian(
            aceptado=True,
            codigo_estado=CODIGO_RECIBIDO_ASINCRONO,
            descripcion="ZIP recibido por la DIAN; consulte el resultado con GetStatusZip",
            mensajes=mensajes,
            track_id=track_id,
        )
    return RespuestaDian(
        aceptado=False,
        codigo_estado="99",
        descripcion="La DIAN no asignó ZipKey al envío del set de pruebas",
        mensajes=mensajes,
    )


# --------------------------------------------------------------------------- #
# Cliente
# --------------------------------------------------------------------------- #


class ClienteDianSoap:
    """Implementación de ``ClienteDian`` contra el servicio web SOAP de la DIAN.

    La verificación TLS siempre está activa. Si se inyecta ``http_client`` (p. ej.
    en pruebas con ``httpx.MockTransport``), el llamador es responsable de su
    configuración y de cerrarlo.
    """

    def __init__(
        self,
        url: str,
        firmador_ws: CredencialWs,
        test_set_id: str,
        timeout: float,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not url.lower().startswith("https://"):
            raise ValueError("La URL del servicio DIAN debe usar HTTPS")
        self._url = url
        self._credencial = firmador_ws
        self._test_set_id = test_set_id
        self._timeout = timeout
        self._propio = http_client is None
        self._http = http_client or httpx.Client(timeout=timeout, verify=True)

    def close(self) -> None:
        if self._propio:
            self._http.close()

    def __enter__(self) -> ClienteDianSoap:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # --- Operaciones del puerto ---

    def enviar_set_pruebas(self, nombre_zip: str, contenido_zip: bytes) -> RespuestaDian:
        if not self._test_set_id:
            raise ErrorDian("No hay TestSetId configurado para el set de pruebas")
        cuerpo = cuerpo_send_test_set_async(nombre_zip, contenido_zip, self._test_set_id)
        return interpretar_send_test_set_async(self._llamar(ACCION_SEND_TEST_SET_ASYNC, cuerpo))

    def enviar_factura(self, nombre_zip: str, contenido_zip: bytes) -> RespuestaDian:
        cuerpo = cuerpo_send_bill_sync(nombre_zip, contenido_zip)
        return interpretar_send_bill_sync(self._llamar(ACCION_SEND_BILL_SYNC, cuerpo))

    def consultar_estado_zip(self, track_id: str) -> RespuestaDian:
        cuerpo = cuerpo_get_status_zip(track_id)
        return interpretar_get_status_zip(self._llamar(ACCION_GET_STATUS_ZIP, cuerpo))

    # --- Transporte ---

    def _llamar(self, accion: str, cuerpo: etree._Element) -> bytes:
        operacion = accion.rsplit("/", 1)[-1]
        sobre = construir_sobre(
            accion,
            cuerpo,
            url=self._url,
            llave_privada=self._credencial.llave_privada,
            certificado=self._credencial.certificado,
        )
        cabeceras = {"Content-Type": f'application/soap+xml;charset=UTF-8;action="{accion}"'}
        try:
            respuesta = self._http.post(
                self._url, content=sobre, headers=cabeceras, timeout=self._timeout
            )
        except httpx.TimeoutException as exc:
            logger.warning("Tiempo de espera agotado en %s contra la DIAN", operacion)
            raise ErrorDian("Tiempo de espera agotado al comunicarse con la DIAN") from exc
        except httpx.HTTPError as exc:
            logger.warning("Error de transporte en %s contra la DIAN: %s", operacion, type(exc))
            raise ErrorDian("Error de comunicación con la DIAN") from exc

        if respuesta.status_code != httpx.codes.OK:
            logger.warning(
                "La DIAN respondió HTTP %s en %s: %s",
                respuesta.status_code,
                operacion,
                _descripcion_fault(respuesta.content) or "(sin soap:Fault)",
            )
            raise ErrorDian(f"La DIAN respondió con error HTTP {respuesta.status_code}")
        logger.debug(
            "Respuesta de la DIAN a %s recibida (%d bytes)", operacion, len(respuesta.content)
        )
        return respuesta.content
