"""Pruebas del firmador XAdES-EPES (Política de Firma DIAN v2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, pkcs12
from cryptography.x509.oid import NameOID
from lxml import etree
from signxml import CanonicalizationMethod
from signxml.exceptions import InvalidSignature
from signxml.xades import XAdESSignatureConfiguration, XAdESVerifier

from facturacion.firma.puertos import ErrorFirma
from facturacion.firma.xades import (
    CN_CERTIFICADO_DESARROLLO,
    HUELLA_POLITICA_FIRMA_DIAN,
    POLITICA_FIRMA_DIAN,
    URL_POLITICA_FIRMA_DIAN,
    FirmadorXades,
)

NS = {
    "inv": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "ds": "http://www.w3.org/2000/09/xmldsig#",
    "xades": "http://uri.etsi.org/01903/v1.3.2#",
    "sts": "dian:gov:co:facturaelectronica:Structures-2-1",
}

CUFE = "a" * 96


def factura_ubl(segunda_extension: bool = True) -> bytes:
    segunda = (
        "<ext:UBLExtension><ext:ExtensionContent/></ext:UBLExtension>" if segunda_extension else ""
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
    xmlns:sts="dian:gov:co:facturaelectronica:Structures-2-1">
  <ext:UBLExtensions>
    <ext:UBLExtension>
      <ext:ExtensionContent>
        <sts:DianExtensions>
          <sts:SoftwareProvider><sts:ProviderID>900000000</sts:ProviderID></sts:SoftwareProvider>
        </sts:DianExtensions>
      </ext:ExtensionContent>
    </ext:UBLExtension>
    {segunda}
  </ext:UBLExtensions>
  <cbc:UBLVersionID>UBL 2.1</cbc:UBLVersionID>
  <cbc:ID>SETP990000001</cbc:ID>
  <cbc:UUID schemeID="2" schemeName="CUFE-SHA384">{CUFE}</cbc:UUID>
  <cbc:IssueDate>2026-01-15</cbc:IssueDate>
  <cac:LegalMonetaryTotal>
    <cbc:PayableAmount currencyID="COP">119000.00</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
</Invoice>""".encode()


@pytest.fixture(scope="module")
def firmador() -> FirmadorXades:
    return FirmadorXades.autofirmado_para_desarrollo()


def verificar(xml: bytes, firmador: FirmadorXades) -> list:
    return XAdESVerifier().verify(
        xml,
        x509_cert=firmador.certificado,
        expect_signature_policy=POLITICA_FIRMA_DIAN,
        expect_config=XAdESSignatureConfiguration(
            default_reference_c14n_method=CanonicalizationMethod.CANONICAL_XML_1_0
        ),
    )


def test_firma_queda_en_la_segunda_extension(firmador: FirmadorXades) -> None:
    raiz = etree.fromstring(firmador.firmar(factura_ubl()))
    extensiones = raiz.findall("ext:UBLExtensions/ext:UBLExtension", NS)
    assert len(extensiones) == 2
    assert extensiones[0].find(".//ds:Signature", NS) is None
    firmas = raiz.findall(".//ds:Signature", NS)
    assert len(firmas) == 1
    assert firmas[0].getparent() is extensiones[1].find("ext:ExtensionContent", NS)
    # El contenido de la primera extensión se conserva.
    assert extensiones[0].find(".//sts:ProviderID", NS).text == "900000000"


def test_firma_usa_algoritmos_y_politica_dian(firmador: FirmadorXades) -> None:
    raiz = etree.fromstring(firmador.firmar(factura_ubl()))
    firma = raiz.find(".//ds:Signature", NS)
    signed_info = firma.find("ds:SignedInfo", NS)
    assert (
        signed_info.find("ds:CanonicalizationMethod", NS).get("Algorithm")
        == "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
    )
    assert (
        signed_info.find("ds:SignatureMethod", NS).get("Algorithm")
        == "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
    )
    referencias = signed_info.findall("ds:Reference", NS)
    assert len(referencias) == 3
    documento = referencias[0]
    assert documento.get("URI") == ""
    assert [t.get("Algorithm") for t in documento.findall("ds:Transforms/ds:Transform", NS)] == [
        "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
    ]
    for ref in referencias:
        assert (
            ref.find("ds:DigestMethod", NS).get("Algorithm")
            == "http://www.w3.org/2001/04/xmlenc#sha256"
        )

    propiedades = firma.find(".//xades:SignedSignatureProperties", NS)
    assert propiedades.find("xades:SigningTime", NS).text
    assert propiedades.find("xades:SigningCertificate/xades:Cert/xades:CertDigest", NS) is not None
    politica = propiedades.find("xades:SignaturePolicyIdentifier/xades:SignaturePolicyId", NS)
    assert politica.find("xades:SigPolicyId/xades:Identifier", NS).text == URL_POLITICA_FIRMA_DIAN
    assert (
        politica.find("xades:SigPolicyHash/ds:DigestValue", NS).text == HUELLA_POLITICA_FIRMA_DIAN
    )
    assert (
        propiedades.find("xades:SignerRole/xades:ClaimedRoles/xades:ClaimedRole", NS).text
        == "supplier"
    )


def test_firma_verifica_criptograficamente(firmador: FirmadorXades) -> None:
    resultados = verificar(firmador.firmar(factura_ubl()), firmador)
    assert len(resultados) == 3
    # La primera referencia es el documento completo, sin la firma (enveloped).
    documento = resultados[0].signed_xml
    assert documento.find("cbc:UUID", NS).text == CUFE
    assert documento.find(".//ds:Signature", NS) is None


def test_modificar_el_documento_firmado_invalida_la_firma(firmador: FirmadorXades) -> None:
    firmado = firmador.firmar(factura_ubl())
    alterado = firmado.replace(b"119000.00", b"1.00")
    assert alterado != firmado
    with pytest.raises(InvalidSignature):
        verificar(alterado, firmador)


def test_modificar_propiedades_firmadas_invalida_la_firma(firmador: FirmadorXades) -> None:
    raiz = etree.fromstring(firmador.firmar(factura_ubl()))
    raiz.find(".//xades:ClaimedRole", NS).text = "third party"
    with pytest.raises(InvalidSignature):
        verificar(etree.tostring(raiz), firmador)


def test_sin_segunda_extension_lanza_error_firma(firmador: FirmadorXades) -> None:
    with pytest.raises(ErrorFirma, match="segunda"):
        firmador.firmar(factura_ubl(segunda_extension=False))


def test_documento_ya_firmado_lanza_error_firma(firmador: FirmadorXades) -> None:
    with pytest.raises(ErrorFirma):
        firmador.firmar(firmador.firmar(factura_ubl()))


def test_xml_mal_formado_lanza_error_firma(firmador: FirmadorXades) -> None:
    with pytest.raises(ErrorFirma):
        firmador.firmar(b"<Invoice>")


def test_xml_con_entidades_externas_no_se_resuelve(firmador: FirmadorXades, tmp_path: Path) -> None:
    secreto = tmp_path / "secreto.txt"
    secreto.write_text("CONTENIDO-SECRETO")
    xml = (
        factura_ubl()
        .replace(
            b'<?xml version="1.0" encoding="UTF-8"?>',
            f'<?xml version="1.0"?><!DOCTYPE Invoice [<!ENTITY x SYSTEM "file://{secreto}">]>'.encode(),
        )
        .replace(b"SETP990000001", b"&x;")
    )
    try:
        firmado = firmador.firmar(xml)
    except ErrorFirma:
        return
    assert b"CONTENIDO-SECRETO" not in firmado


def test_certificado_de_desarrollo(firmador: FirmadorXades) -> None:
    cn = firmador.certificado.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    assert cn == CN_CERTIFICADO_DESARROLLO
    vigencia = firmador.certificado.not_valid_after_utc - firmador.certificado.not_valid_before_utc
    assert 364 <= vigencia.days <= 366
    assert firmador.llave_privada.key_size == 2048
    assert "PRIVATE" not in repr(firmador)


def _escribir_p12(tmp_path: Path, firmador: FirmadorXades, clave: bytes) -> Path:
    ruta = tmp_path / "certificado.p12"
    ruta.write_bytes(
        pkcs12.serialize_key_and_certificates(
            b"facturador",
            firmador.llave_privada,
            firmador.certificado,
            None,
            BestAvailableEncryption(clave),
        )
    )
    return ruta


def test_pkcs12_ida_y_vuelta(firmador: FirmadorXades, tmp_path: Path) -> None:
    ruta = _escribir_p12(tmp_path, firmador, b"clave-segura-123")
    cargado = FirmadorXades.desde_pkcs12(ruta, "clave-segura-123")
    assert cargado.certificado == firmador.certificado
    verificar(cargado.firmar(factura_ubl()), firmador)


def test_pkcs12_con_clave_incorrecta_lanza_error_firma(
    firmador: FirmadorXades, tmp_path: Path
) -> None:
    ruta = _escribir_p12(tmp_path, firmador, b"clave-segura-123")
    with pytest.raises(ErrorFirma) as error:
        FirmadorXades.desde_pkcs12(ruta, "clave-equivocada-xyz")
    assert "clave-equivocada-xyz" not in str(error.value)
    assert error.value.__cause__ is None


def test_pkcs12_inexistente_lanza_error_firma(tmp_path: Path) -> None:
    with pytest.raises(ErrorFirma):
        FirmadorXades.desde_pkcs12(tmp_path / "no-existe.p12", "x")
