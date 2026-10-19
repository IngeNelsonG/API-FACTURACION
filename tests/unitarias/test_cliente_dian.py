"""Pruebas de los adaptadores de ``ClienteDian``: SOAP (sin red) y simulado."""

from __future__ import annotations

import base64
import datetime
import hashlib
import io
import zipfile
from pathlib import Path

import httpx
import pytest
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from lxml import etree

from facturacion.dian.puertos import ErrorDian
from facturacion.dian.simulado import ClienteDianSimulado
from facturacion.dian.soap import (
    ACCION_GET_STATUS_ZIP,
    ACCION_SEND_BILL_SYNC,
    ACCION_SEND_TEST_SET_ASYNC,
    CODIGO_RECIBIDO_ASINCRONO,
    ClienteDianSoap,
    construir_sobre,
    cuerpo_send_bill_sync,
)
from facturacion.firma.xades import FirmadorXades

URL = "https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc"
TEST_SET_ID = "11111111-2222-3333-4444-555555555555"
CUFE = "0123456789abcdef" * 6

NS = {
    "soap": "http://www.w3.org/2003/05/soap-envelope",
    "wcf": "http://wcf.dian.colombia",
    "wsa": "http://www.w3.org/2005/08/addressing",
    "wsse": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd",
    "wsu": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd",
    "ds": "http://www.w3.org/2000/09/xmldsig#",
    "ec": "http://www.w3.org/2001/10/xml-exc-c14n#",
    "ar": "urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}
WSU_ID = f"{{{NS['wsu']}}}Id"


@pytest.fixture(scope="module")
def firmador() -> FirmadorXades:
    return FirmadorXades.autofirmado_para_desarrollo()


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #


def factura_ubl(cufe: str = CUFE) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2">
  <ext:UBLExtensions>
    <ext:UBLExtension><ext:ExtensionContent/></ext:UBLExtension>
    <ext:UBLExtension><ext:ExtensionContent/></ext:UBLExtension>
  </ext:UBLExtensions>
  <cbc:ID>SETP990000001</cbc:ID>
  <cbc:UUID schemeName="CUFE-SHA384">{cufe}</cbc:UUID>
</Invoice>""".encode()


def comprimir(archivos: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_:
        for nombre, contenido in archivos.items():
            zip_.writestr(nombre, contenido)
    return buffer.getvalue()


def verificar_firma_ws(sobre: bytes) -> etree._Element:
    """Verifica la firma WS-Security sobre ``wsa:To`` y devuelve el elemento firmado."""
    raiz = etree.fromstring(sobre)
    firma = raiz.find("soap:Header/wsse:Security/ds:Signature", NS)
    signed_info = firma.find("ds:SignedInfo", NS)
    referencia = signed_info.find("ds:Reference", NS)
    id_firmado = referencia.get("URI").removeprefix("#")
    (firmado,) = raiz.xpath("//*[@wsu:Id=$id]", namespaces=NS, id=id_firmado)

    prefijos_ref = (
        referencia.find("ds:Transforms/ds:Transform/ec:InclusiveNamespaces", NS)
        .get("PrefixList")
        .split()
    )
    c14n = etree.tostring(
        firmado, method="c14n", exclusive=True, inclusive_ns_prefixes=prefijos_ref
    )
    resumen = base64.b64encode(hashlib.sha256(c14n).digest()).decode()
    assert resumen == referencia.find("ds:DigestValue", NS).text, "DigestValue no coincide"

    id_token = (
        firma.find("ds:KeyInfo/wsse:SecurityTokenReference/wsse:Reference", NS)
        .get("URI")
        .removeprefix("#")
    )
    (token,) = raiz.xpath("//wsse:BinarySecurityToken[@wsu:Id=$id]", namespaces=NS, id=id_token)
    certificado = x509.load_der_x509_certificate(base64.b64decode(token.text))
    prefijos_si = (
        signed_info.find("ds:CanonicalizationMethod/ec:InclusiveNamespaces", NS)
        .get("PrefixList")
        .split()
    )
    c14n_si = etree.tostring(
        signed_info, method="c14n", exclusive=True, inclusive_ns_prefixes=prefijos_si
    )
    certificado.public_key().verify(
        base64.b64decode(firma.find("ds:SignatureValue", NS).text),
        c14n_si,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return firmado


def sobre_respuesta(cuerpo: str, accion: str) -> bytes:
    return f"""<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
    xmlns:a="http://www.w3.org/2005/08/addressing"
    xmlns:u="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
  <s:Header>
    <a:Action s:mustUnderstand="1">{accion}Response</a:Action>
    <o:Security s:mustUnderstand="1"
        xmlns:o="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
      <u:Timestamp u:Id="_0">
        <u:Created>2026-01-15T15:00:00.000Z</u:Created>
        <u:Expires>2026-01-15T15:05:00.000Z</u:Expires>
      </u:Timestamp>
    </o:Security>
  </s:Header>
  <s:Body>{cuerpo}</s:Body>
</s:Envelope>""".encode()


APPLICATION_RESPONSE = (
    b'<ApplicationResponse xmlns="urn:oasis:names:specification:ubl:schema:xsd:'
    b'ApplicationResponse-2"/>'
)

RESPUESTA_ACEPTADA = sobre_respuesta(
    f"""<SendBillSyncResponse xmlns="http://wcf.dian.colombia">
  <SendBillSyncResult xmlns:b="http://schemas.datacontract.org/2004/07/DianResponse"
      xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
    <b:ErrorMessage xmlns:c="http://schemas.microsoft.com/2003/10/Serialization/Arrays"/>
    <b:IsValid>true</b:IsValid>
    <b:StatusCode>00</b:StatusCode>
    <b:StatusDescription>Procesado Correctamente.</b:StatusDescription>
    <b:StatusMessage>La Factura electrónica SETP990000001, ha sido autorizada.</b:StatusMessage>
    <b:XmlBase64Bytes>{base64.b64encode(APPLICATION_RESPONSE).decode()}</b:XmlBase64Bytes>
    <b:XmlBytes i:nil="true"/>
    <b:XmlDocumentKey>{CUFE}</b:XmlDocumentKey>
    <b:XmlFileName>fv09000000000260000000001</b:XmlFileName>
  </SendBillSyncResult>
</SendBillSyncResponse>""",
    ACCION_SEND_BILL_SYNC,
)

RESPUESTA_RECHAZADA = sobre_respuesta(
    f"""<SendBillSyncResponse xmlns="http://wcf.dian.colombia">
  <SendBillSyncResult xmlns:b="http://schemas.datacontract.org/2004/07/DianResponse"
      xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
    <b:ErrorMessage xmlns:c="http://schemas.microsoft.com/2003/10/Serialization/Arrays">
      <c:string>Regla: FAD06, Rechazo: Valor del CUFE no está calculado correctamente.</c:string>
      <c:string>Regla: FAJ43b, Rechazo: Nombre informado no corresponde al del RUT.</c:string>
    </b:ErrorMessage>
    <b:IsValid>false</b:IsValid>
    <b:StatusCode>99</b:StatusCode>
    <b:StatusDescription>Validación contiene errores en campos mandatorios.</b:StatusDescription>
    <b:StatusMessage/>
    <b:XmlBase64Bytes/>
    <b:XmlBytes i:nil="true"/>
    <b:XmlDocumentKey>{CUFE}</b:XmlDocumentKey>
    <b:XmlFileName>fv09000000000260000000001</b:XmlFileName>
  </SendBillSyncResult>
</SendBillSyncResponse>""",
    ACCION_SEND_BILL_SYNC,
)

RESPUESTA_SET_PRUEBAS = sobre_respuesta(
    """<SendTestSetAsyncResponse xmlns="http://wcf.dian.colombia">
  <SendTestSetAsyncResult xmlns:b="http://schemas.datacontract.org/2004/07/UploadDocumentResponse"
      xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
    <b:ErrorMessageList
        xmlns:c="http://schemas.datacontract.org/2004/07/XmlParamsResponseTrackId"/>
    <b:ZipKey>9b2f1a3c-7d4e-4c5b-8a6f-0e1d2c3b4a59</b:ZipKey>
  </SendTestSetAsyncResult>
</SendTestSetAsyncResponse>""",
    ACCION_SEND_TEST_SET_ASYNC,
)

RESPUESTA_SET_PRUEBAS_SIN_ZIPKEY = sobre_respuesta(
    """<SendTestSetAsyncResponse xmlns="http://wcf.dian.colombia">
  <SendTestSetAsyncResult xmlns:b="http://schemas.datacontract.org/2004/07/UploadDocumentResponse"
      xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
    <b:ErrorMessageList
        xmlns:c="http://schemas.datacontract.org/2004/07/XmlParamsResponseTrackId">
      <c:XmlParamsResponseTrackId>
        <c:DocumentKey i:nil="true"/>
        <c:ProcessedMessage>Set de prueba con identificador inexistente.</c:ProcessedMessage>
        <c:Success>false</c:Success>
        <c:XmlFileName>fv09000000000260000000001</c:XmlFileName>
      </c:XmlParamsResponseTrackId>
    </b:ErrorMessageList>
    <b:ZipKey i:nil="true"/>
  </SendTestSetAsyncResult>
</SendTestSetAsyncResponse>""",
    ACCION_SEND_TEST_SET_ASYNC,
)

RESPUESTA_ESTADO_ZIP = sobre_respuesta(
    f"""<GetStatusZipResponse xmlns="http://wcf.dian.colombia">
  <GetStatusZipResult xmlns:b="http://schemas.datacontract.org/2004/07/DianResponse"
      xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
    <b:DianResponse>
      <b:ErrorMessage xmlns:c="http://schemas.microsoft.com/2003/10/Serialization/Arrays">
        <c:string>Regla: FAJ44b, Notificación: Nit o Documento no corresponde.</c:string>
      </b:ErrorMessage>
      <b:IsValid>true</b:IsValid>
      <b:StatusCode>00</b:StatusCode>
      <b:StatusDescription>Procesado Correctamente.</b:StatusDescription>
      <b:StatusMessage>La Factura electrónica SETP990000001, ha sido autorizada.</b:StatusMessage>
      <b:XmlBase64Bytes>{base64.b64encode(APPLICATION_RESPONSE).decode()}</b:XmlBase64Bytes>
      <b:XmlBytes i:nil="true"/>
      <b:XmlDocumentKey>{CUFE}</b:XmlDocumentKey>
      <b:XmlFileName>fv09000000000260000000001</b:XmlFileName>
    </b:DianResponse>
  </GetStatusZipResult>
</GetStatusZipResponse>""",
    ACCION_GET_STATUS_ZIP,
)

FAULT = b"""<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"><s:Body><s:Fault>
<s:Code><s:Value>s:Sender</s:Value></s:Code>
<s:Reason><s:Text xml:lang="es-CO">An error occurred when verifying security.</s:Text></s:Reason>
</s:Fault></s:Body></s:Envelope>"""


class Grabador:
    """Transporte simulado de httpx que guarda las peticiones y responde lo indicado."""

    def __init__(self, respuesta: bytes, estado: int = 200) -> None:
        self.respuesta = respuesta
        self.estado = estado
        self.peticiones: list[httpx.Request] = []

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones.append(peticion)
        return httpx.Response(self.estado, content=self.respuesta)


def cliente_con(firmador: FirmadorXades, grabador: Grabador) -> ClienteDianSoap:
    http = httpx.Client(transport=httpx.MockTransport(grabador))
    return ClienteDianSoap(URL, firmador, TEST_SET_ID, timeout=5.0, http_client=http)


# --------------------------------------------------------------------------- #
# Sobre SOAP
# --------------------------------------------------------------------------- #


def test_sobre_tiene_addressing_y_seguridad(firmador: FirmadorXades) -> None:
    ahora = datetime.datetime(2026, 1, 15, 15, 0, tzinfo=datetime.UTC)
    sobre = construir_sobre(
        ACCION_SEND_BILL_SYNC,
        cuerpo_send_bill_sync("z.zip", b"PK-datos"),
        url=URL,
        llave_privada=firmador.llave_privada,
        certificado=firmador.certificado,
        ahora=ahora,
    )
    raiz = etree.fromstring(sobre)
    assert raiz.tag == f"{{{NS['soap']}}}Envelope"
    cabecera = raiz.find("soap:Header", NS)
    assert cabecera.find("wsa:Action", NS).text == ACCION_SEND_BILL_SYNC
    destino = cabecera.find("wsa:To", NS)
    assert destino.text == URL
    assert destino.get(WSU_ID)

    seguridad = cabecera.find("wsse:Security", NS)
    assert seguridad.get(f"{{{NS['soap']}}}mustUnderstand") == "true"
    assert seguridad.find("wsu:Timestamp/wsu:Created", NS).text == "2026-01-15T15:00:00.000Z"
    assert seguridad.find("wsu:Timestamp/wsu:Expires", NS).text == "2026-01-15T15:05:00.000Z"
    token = seguridad.find("wsse:BinarySecurityToken", NS)
    assert token.get("EncodingType").endswith("#Base64Binary")
    assert token.get("ValueType").endswith("#X509v3")
    assert x509.load_der_x509_certificate(base64.b64decode(token.text)) == firmador.certificado

    firma = seguridad.find("ds:Signature", NS)
    assert (
        firma.find("ds:SignedInfo/ds:CanonicalizationMethod", NS).get("Algorithm")
        == "http://www.w3.org/2001/10/xml-exc-c14n#"
    )
    assert (
        firma.find("ds:SignedInfo/ds:SignatureMethod", NS).get("Algorithm")
        == "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
    )
    referencia_token = firma.find("ds:KeyInfo/wsse:SecurityTokenReference/wsse:Reference", NS)
    assert referencia_token.get("URI") == f"#{token.get(WSU_ID)}"

    envio = raiz.find("soap:Body/wcf:SendBillSync", NS)
    assert envio.find("wcf:fileName", NS).text == "z.zip"
    assert base64.b64decode(envio.find("wcf:contentFile", NS).text) == b"PK-datos"


def test_firma_del_sobre_cubre_wsa_to_y_verifica(firmador: FirmadorXades) -> None:
    sobre = construir_sobre(
        ACCION_GET_STATUS_ZIP,
        etree.Element(f"{{{NS['wcf']}}}GetStatusZip"),
        url=URL,
        llave_privada=firmador.llave_privada,
        certificado=firmador.certificado,
    )
    firmado = verificar_firma_ws(sobre)
    assert firmado.tag == f"{{{NS['wsa']}}}To"


def test_alterar_wsa_to_invalida_la_firma_del_sobre(firmador: FirmadorXades) -> None:
    sobre = construir_sobre(
        ACCION_GET_STATUS_ZIP,
        etree.Element(f"{{{NS['wcf']}}}GetStatusZip"),
        url=URL,
        llave_privada=firmador.llave_privada,
        certificado=firmador.certificado,
    )
    alterado = sobre.replace(URL.encode(), b"https://atacante.example/svc")
    with pytest.raises(AssertionError, match="DigestValue"):
        verificar_firma_ws(alterado)
    # Y alterar el SignedInfo rompe la firma RSA.
    raiz = etree.fromstring(sobre)
    raiz.find(".//ds:SignatureMethod", NS).set("Algorithm", "x")
    with pytest.raises(InvalidSignature):
        verificar_firma_ws(etree.tostring(raiz))


# --------------------------------------------------------------------------- #
# Cliente SOAP
# --------------------------------------------------------------------------- #


def test_send_bill_sync_aceptado(firmador: FirmadorXades) -> None:
    grabador = Grabador(RESPUESTA_ACEPTADA)
    respuesta = cliente_con(firmador, grabador).enviar_factura("z.zip", b"zip")

    assert respuesta.aceptado is True
    assert respuesta.codigo_estado == "00"
    assert respuesta.descripcion == "Procesado Correctamente."
    assert respuesta.application_response == APPLICATION_RESPONSE
    assert respuesta.track_id == CUFE
    assert "ha sido autorizada" in respuesta.mensajes[0]

    (peticion,) = grabador.peticiones
    assert peticion.method == "POST"
    assert str(peticion.url) == URL
    assert peticion.headers["Content-Type"] == (
        f'application/soap+xml;charset=UTF-8;action="{ACCION_SEND_BILL_SYNC}"'
    )
    verificar_firma_ws(peticion.content)
    cuerpo = etree.fromstring(peticion.content).find("soap:Body/wcf:SendBillSync", NS)
    assert base64.b64decode(cuerpo.find("wcf:contentFile", NS).text) == b"zip"


def test_send_bill_sync_rechazado(firmador: FirmadorXades) -> None:
    respuesta = cliente_con(firmador, Grabador(RESPUESTA_RECHAZADA)).enviar_factura("z.zip", b"x")
    assert respuesta.aceptado is False
    assert respuesta.codigo_estado == "99"
    assert respuesta.application_response is None
    assert respuesta.mensajes == [
        "Regla: FAD06, Rechazo: Valor del CUFE no está calculado correctamente.",
        "Regla: FAJ43b, Rechazo: Nombre informado no corresponde al del RUT.",
    ]


def test_send_test_set_async_devuelve_track_id(firmador: FirmadorXades) -> None:
    grabador = Grabador(RESPUESTA_SET_PRUEBAS)
    respuesta = cliente_con(firmador, grabador).enviar_set_pruebas("z.zip", b"zip")
    assert respuesta.aceptado is True
    assert respuesta.codigo_estado == CODIGO_RECIBIDO_ASINCRONO
    assert respuesta.track_id == "9b2f1a3c-7d4e-4c5b-8a6f-0e1d2c3b4a59"

    (peticion,) = grabador.peticiones
    assert ACCION_SEND_TEST_SET_ASYNC in peticion.headers["Content-Type"]
    cuerpo = etree.fromstring(peticion.content).find("soap:Body/wcf:SendTestSetAsync", NS)
    assert cuerpo.find("wcf:testSetId", NS).text == TEST_SET_ID
    assert cuerpo.find("wcf:fileName", NS).text == "z.zip"


def test_send_test_set_async_sin_zipkey(firmador: FirmadorXades) -> None:
    respuesta = cliente_con(
        firmador, Grabador(RESPUESTA_SET_PRUEBAS_SIN_ZIPKEY)
    ).enviar_set_pruebas("z.zip", b"zip")
    assert respuesta.aceptado is False
    assert respuesta.track_id is None
    assert respuesta.mensajes == ["Set de prueba con identificador inexistente."]


def test_get_status_zip_usa_el_primer_dian_response(firmador: FirmadorXades) -> None:
    grabador = Grabador(RESPUESTA_ESTADO_ZIP)
    respuesta = cliente_con(firmador, grabador).consultar_estado_zip("track-1")
    assert respuesta.aceptado is True
    assert respuesta.codigo_estado == "00"
    assert respuesta.application_response == APPLICATION_RESPONSE
    assert "Regla: FAJ44b, Notificación: Nit o Documento no corresponde." in respuesta.mensajes
    cuerpo = etree.fromstring(grabador.peticiones[0].content).find("soap:Body/wcf:GetStatusZip", NS)
    assert cuerpo.find("wcf:trackId", NS).text == "track-1"


def test_http_500_lanza_error_dian(firmador: FirmadorXades) -> None:
    with pytest.raises(ErrorDian, match="HTTP 500"):
        cliente_con(firmador, Grabador(FAULT, estado=500)).enviar_factura("z.zip", b"x")


def test_timeout_lanza_error_dian(firmador: FirmadorXades) -> None:
    def expira(peticion: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("tiempo agotado", request=peticion)

    http = httpx.Client(transport=httpx.MockTransport(expira))
    cliente = ClienteDianSoap(URL, firmador, TEST_SET_ID, timeout=0.1, http_client=http)
    with pytest.raises(ErrorDian, match="Tiempo de espera"):
        cliente.consultar_estado_zip("track-1")


def test_error_de_conexion_lanza_error_dian(firmador: FirmadorXades) -> None:
    def falla(peticion: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red", request=peticion)

    http = httpx.Client(transport=httpx.MockTransport(falla))
    cliente = ClienteDianSoap(URL, firmador, TEST_SET_ID, timeout=1, http_client=http)
    with pytest.raises(ErrorDian, match="comunicación"):
        cliente.enviar_factura("z.zip", b"x")


@pytest.mark.parametrize(
    "contenido",
    [
        b"esto no es XML",
        b"<html><body>Service Unavailable</body></html>",
        sobre_respuesta("<Otro/>", ACCION_SEND_BILL_SYNC),
    ],
)
def test_respuesta_inesperada_lanza_error_dian(firmador: FirmadorXades, contenido: bytes) -> None:
    with pytest.raises(ErrorDian):
        cliente_con(firmador, Grabador(contenido)).enviar_factura("z.zip", b"x")


def test_respuesta_con_entidades_externas_no_las_resuelve(
    firmador: FirmadorXades, tmp_path: Path
) -> None:
    secreto = tmp_path / "secreto.txt"
    secreto.write_text("CONTENIDO-SECRETO")
    malicioso = RESPUESTA_RECHAZADA.replace(
        b"<s:Envelope",
        f'<!DOCTYPE s:Envelope [<!ENTITY x SYSTEM "file://{secreto}">]><s:Envelope'.encode(),
        1,
    ).replace(b"Validaci\xc3\xb3n contiene", b"&x;")
    try:
        respuesta = cliente_con(firmador, Grabador(malicioso)).enviar_factura("z.zip", b"x")
    except ErrorDian:
        return
    assert "CONTENIDO-SECRETO" not in respuesta.descripcion


def test_url_sin_https_se_rechaza(firmador: FirmadorXades) -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        ClienteDianSoap("http://vpfe-hab.dian.gov.co/x.svc", firmador, TEST_SET_ID, timeout=1)


def test_cliente_propio_verifica_tls(
    firmador: FirmadorXades, monkeypatch: pytest.MonkeyPatch
) -> None:
    argumentos: dict[str, object] = {}
    cliente_original = httpx.Client

    def capturar(**kwargs: object) -> httpx.Client:
        argumentos.update(kwargs)
        return cliente_original(**kwargs)

    monkeypatch.setattr(httpx, "Client", capturar)
    with ClienteDianSoap(URL, firmador, TEST_SET_ID, timeout=7):
        pass
    assert argumentos["verify"] is True
    assert argumentos["timeout"] == 7


# --------------------------------------------------------------------------- #
# Cliente simulado
# --------------------------------------------------------------------------- #


def test_simulado_acepta_factura_firmada(firmador: FirmadorXades, tmp_path: Path) -> None:
    cliente = ClienteDianSimulado(tmp_path)
    zip_ = comprimir({"fv.xml": firmador.firmar(factura_ubl())})
    respuesta = cliente.enviar_factura("z.zip", zip_)

    assert respuesta.aceptado is True
    assert respuesta.codigo_estado == "00"
    assert respuesta.descripcion == "Procesado Correctamente (simulado)"
    assert respuesta.track_id is None
    ar = etree.fromstring(respuesta.application_response)
    assert ar.tag == f"{{{NS['ar']}}}ApplicationResponse"
    assert ar.find(".//cbc:ResponseCode", NS).text == "02"
    assert ar.find(".//cbc:Description", NS).text == "Documento validado por la DIAN"
    assert ar.find(".//cbc:UUID", NS).text == CUFE
    assert "SIMULADA" in ar.find("cbc:Note", NS).text
    assert (tmp_path / "z.zip").read_bytes() == zip_


def test_simulado_set_pruebas_y_consulta_por_track_id(firmador: FirmadorXades) -> None:
    cliente = ClienteDianSimulado()
    respuesta = cliente.enviar_set_pruebas(
        "z.zip", comprimir({"fv.xml": firmador.firmar(factura_ubl())})
    )
    assert respuesta.aceptado is True
    assert respuesta.track_id
    estado = cliente.consultar_estado_zip(respuesta.track_id)
    assert estado.aceptado is True
    assert estado.application_response == respuesta.application_response

    desconocido = cliente.consultar_estado_zip("no-existe")
    assert desconocido.aceptado is False
    assert desconocido.codigo_estado == "66"
    assert desconocido.descripcion == "TrackId no encontrado"


def test_simulado_rechaza_documento_sin_firma() -> None:
    respuesta = ClienteDianSimulado().enviar_factura("z.zip", comprimir({"fv.xml": factura_ubl()}))
    assert respuesta.aceptado is False
    assert respuesta.codigo_estado == "99"
    assert "firma" in respuesta.mensajes[0]
    assert respuesta.mensajes[0].startswith("Regla: ")


def test_simulado_rechaza_cufe_invalido(firmador: FirmadorXades) -> None:
    zip_ = comprimir({"fv.xml": firmador.firmar(factura_ubl(cufe="123"))})
    respuesta = ClienteDianSimulado().enviar_factura("z.zip", zip_)
    assert respuesta.aceptado is False
    assert "CUFE" in respuesta.mensajes[0]


@pytest.mark.parametrize(
    "contenido",
    [
        b"no es un zip",
        comprimir({}),
        comprimir({"a.xml": b"<a/>", "b.xml": b"<b/>"}),
        comprimir({"leeme.txt": b"hola"}),
        comprimir({"fv.xml": b"<Invoice>"}),
    ],
)
def test_simulado_rechaza_zip_invalido(contenido: bytes) -> None:
    respuesta = ClienteDianSimulado().enviar_set_pruebas("z.zip", contenido)
    assert respuesta.aceptado is False
    assert respuesta.codigo_estado == "99"
    assert respuesta.mensajes
