"""Firma XAdES-EPES de documentos UBL 2.1 según la Política de Firma DIAN v2.

La firma es *enveloped*: el ``ds:Signature`` queda dentro del
``ext:ExtensionContent`` de la segunda ``ext:UBLExtension`` (la primera la
ocupan las ``sts:DianExtensions``). Se apoya en ``signxml`` usando un nodo
``<ds:Signature Id="placeholder"/>`` para fijar la ubicación antes de firmar,
de modo que los resúmenes (digests) se calculan con la firma ya en su sitio
definitivo y el documento resultante verifica sin manipulaciones posteriores.
"""

from __future__ import annotations

import datetime
import logging
from base64 import b64encode
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, pkcs12
from cryptography.x509.oid import NameOID
from lxml import etree
from signxml import CanonicalizationMethod, DigestAlgorithm, SignatureMethod
from signxml.util import ds_tag, xades_tag
from signxml.xades import XAdESSignaturePolicy, XAdESSigner

from facturacion.firma.puertos import ErrorFirma

logger = logging.getLogger(__name__)

NS_DS = "http://www.w3.org/2000/09/xmldsig#"
NS_XADES = "http://uri.etsi.org/01903/v1.3.2#"
NS_XADES141 = "http://uri.etsi.org/01903/v1.4.1#"
NS_EXT = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"

URL_POLITICA_FIRMA_DIAN = (
    "https://facturaelectronica.dian.gov.co/politicadefirma/v2/politicadefirmav2.pdf"
)
# SHA-256 (Base64) del PDF de la política, publicado por la DIAN en el anexo técnico.
HUELLA_POLITICA_FIRMA_DIAN = "dMoMvtcG5aIzgYo0tIsSQeVJBDnUnfSOfBpxXrmor0Y="
DESCRIPCION_POLITICA_FIRMA_DIAN = (
    "Política de firma para facturas electrónicas de la República de Colombia."
)
ROL_FIRMANTE = "supplier"

POLITICA_FIRMA_DIAN = XAdESSignaturePolicy(
    Identifier=URL_POLITICA_FIRMA_DIAN,
    Description=DESCRIPCION_POLITICA_FIRMA_DIAN,
    DigestMethod=DigestAlgorithm.SHA256,
    DigestValue=HUELLA_POLITICA_FIRMA_DIAN,
)

# Colombia no tiene horario de verano: UTC-5 fijo.
ZONA_COLOMBIA = datetime.timezone(datetime.timedelta(hours=-5))

CN_CERTIFICADO_DESARROLLO = "Certificado de desarrollo - NO VALIDO ANTE DIAN"

# Parser seguro: sin entidades externas, sin red, sin árboles gigantes.
_PARSER_SEGURO = etree.XMLParser(
    resolve_entities=False, no_network=True, huge_tree=False, remove_blank_text=False
)

_XPATH_CONTENIDO_FIRMA = "ext:UBLExtensions/ext:UBLExtension[2]/ext:ExtensionContent"


class _FirmadorSignxmlDian(XAdESSigner):
    """Ajustes de ``signxml`` para el perfil DIAN.

    - ``SigningCertificate`` (no ``SigningCertificateV2``) con resumen SHA-256 e
      ``IssuerSerial``, como en los ejemplos del anexo técnico.
    - ``SigningTime`` en hora de Colombia.
    - Sin ``SignedDataObjectProperties`` (la política DIAN no lo exige).
    """

    def _build_xades_ds_object(self, sig_root: Any, signing_settings: Any) -> None:
        ds_object = etree.SubElement(sig_root, ds_tag("Object"), nsmap=self.namespaces)
        if "Id" not in sig_root.attrib:
            sig_root.set("Id", f"xmldsig-{self._get_token(8)}")
        id_firma = sig_root.get("Id")
        key_info = self._find(sig_root, "KeyInfo")
        if "Id" not in key_info.attrib:
            key_info.set("Id", f"{id_firma}-keyinfo")
        referencia_documento = self._find(self._find(sig_root, "SignedInfo"), "Reference")
        if "Id" not in referencia_documento.attrib:
            referencia_documento.set("Id", f"{id_firma}-ref0")

        propiedades = etree.SubElement(
            ds_object,
            xades_tag("QualifyingProperties"),
            nsmap=self.namespaces,
            Target=f"#{id_firma}",
        )
        propiedades_firmadas = etree.SubElement(
            propiedades,
            xades_tag("SignedProperties"),
            nsmap=self.namespaces,
            Id=f"{id_firma}-signedprops",
        )
        propiedades_firma = etree.SubElement(
            propiedades_firmadas, xades_tag("SignedSignatureProperties"), nsmap=self.namespaces
        )
        for anotador in self.signed_signature_properties_annotators:
            anotador(propiedades_firma, sig_root=sig_root, signing_settings=signing_settings)
        self._add_reference_to_signed_info(sig_root, key_info)
        self._add_reference_to_signed_info(
            sig_root, propiedades_firmadas, Type="http://uri.etsi.org/01903#SignedProperties"
        )

    def add_signing_time(
        self, signed_signature_properties: Any, sig_root: Any, signing_settings: Any
    ) -> None:
        nodo = etree.SubElement(
            signed_signature_properties, xades_tag("SigningTime"), nsmap=self.namespaces
        )
        nodo.text = datetime.datetime.now(ZONA_COLOMBIA).isoformat(timespec="seconds")

    def add_signing_certificate(
        self, signed_signature_properties: Any, sig_root: Any, signing_settings: Any
    ) -> None:
        certificado_firma = etree.SubElement(
            signed_signature_properties, xades_tag("SigningCertificate"), nsmap=self.namespaces
        )
        for certificado in signing_settings.cert_chain:
            der = certificado.public_bytes(Encoding.DER)
            nodo_cert = etree.SubElement(
                certificado_firma, xades_tag("Cert"), nsmap=self.namespaces
            )
            resumen = etree.SubElement(nodo_cert, xades_tag("CertDigest"), nsmap=self.namespaces)
            etree.SubElement(
                resumen,
                ds_tag("DigestMethod"),
                nsmap=self.namespaces,
                Algorithm=DigestAlgorithm.SHA256.value,
            )
            valor = etree.SubElement(resumen, ds_tag("DigestValue"), nsmap=self.namespaces)
            valor.text = b64encode(self._get_digest(der, algorithm=DigestAlgorithm.SHA256)).decode()
            emisor_serial = etree.SubElement(
                nodo_cert, xades_tag("IssuerSerial"), nsmap=self.namespaces
            )
            nombre_emisor = etree.SubElement(
                emisor_serial, ds_tag("X509IssuerName"), nsmap=self.namespaces
            )
            nombre_emisor.text = certificado.issuer.rfc4514_string()
            serial = etree.SubElement(
                emisor_serial, ds_tag("X509SerialNumber"), nsmap=self.namespaces
            )
            serial.text = str(certificado.serial_number)


class FirmadorXades:
    """Implementación de ``FirmadorXml`` con XAdES-EPES (Política de Firma DIAN v2)."""

    def __init__(
        self,
        llave_privada: rsa.RSAPrivateKey,
        certificado: x509.Certificate,
        cadena: list[x509.Certificate] | None = None,
    ) -> None:
        if not isinstance(llave_privada, rsa.RSAPrivateKey):
            raise ErrorFirma("La llave privada del certificado debe ser RSA")
        self._llave = llave_privada
        self._certificado = certificado
        self._cadena = list(cadena or [])

    # --- Construcción ---

    @classmethod
    def desde_pkcs12(cls, ruta: Path, clave: str) -> FirmadorXades:
        """Carga el certificado de firma desde un archivo ``.p12``/``.pfx``.

        Los mensajes de error son genéricos a propósito: nunca incluyen la clave.
        """
        try:
            contenido = Path(ruta).read_bytes()
        except OSError as exc:
            raise ErrorFirma("No se pudo leer el archivo del certificado") from exc
        try:
            llave, certificado, adicionales = pkcs12.load_key_and_certificates(
                contenido, clave.encode("utf-8") if clave else None
            )
        except (ValueError, TypeError):
            # Se descarta la excepción original: podría contener detalles sensibles.
            raise ErrorFirma(
                "No se pudo abrir el certificado: archivo inválido o clave incorrecta"
            ) from None
        if llave is None or certificado is None:
            raise ErrorFirma("El archivo PKCS#12 no contiene llave privada y certificado")
        if not isinstance(llave, rsa.RSAPrivateKey):
            raise ErrorFirma("La llave privada del certificado debe ser RSA")
        return cls(llave, certificado, list(adicionales or []))

    @classmethod
    def autofirmado_para_desarrollo(cls) -> FirmadorXades:
        """Genera en memoria una llave RSA-2048 y un certificado autofirmado de un año.

        Solo sirve para desarrollo y pruebas: la DIAN rechazará cualquier documento
        firmado con él.
        """
        llave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        nombre = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "CO"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "API Facturacion (desarrollo)"),
                x509.NameAttribute(NameOID.COMMON_NAME, CN_CERTIFICADO_DESARROLLO),
            ]
        )
        ahora = datetime.datetime.now(datetime.UTC)
        certificado = (
            x509.CertificateBuilder()
            .subject_name(nombre)
            .issuer_name(nombre)
            .public_key(llave.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(ahora - datetime.timedelta(minutes=5))
            .not_valid_after(ahora + datetime.timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=True,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(llave, hashes.SHA256())
        )
        return cls(llave, certificado)

    # --- Acceso de solo lectura (lo usa el cliente SOAP para WS-Security) ---

    @property
    def llave_privada(self) -> rsa.RSAPrivateKey:
        return self._llave

    @property
    def certificado(self) -> x509.Certificate:
        return self._certificado

    @property
    def cadena(self) -> list[x509.Certificate]:
        return list(self._cadena)

    def __repr__(self) -> str:
        # Nunca exponer la llave en logs o trazas.
        return f"FirmadorXades(sujeto={self._certificado.subject.rfc4514_string()!r})"

    # --- Firma ---

    def firmar(self, xml: bytes) -> bytes:
        """Devuelve el documento UBL con ``ds:Signature`` dentro de ``UBLExtension[2]``."""
        try:
            raiz = etree.fromstring(xml, parser=_PARSER_SEGURO)
        except etree.XMLSyntaxError as exc:
            raise ErrorFirma("El documento a firmar no es XML bien formado") from exc

        contenidos = raiz.xpath(_XPATH_CONTENIDO_FIRMA, namespaces={"ext": NS_EXT})
        if not contenidos:
            raise ErrorFirma(
                "El documento no tiene ext:ExtensionContent en la segunda ext:UBLExtension"
            )
        contenido = contenidos[0]
        if len(contenido) or (contenido.text or "").strip():
            raise ErrorFirma("La segunda ext:UBLExtension ya tiene contenido (¿firmado antes?)")
        # signxml reemplaza este marcador por la firma y lo excluye del resumen.
        etree.SubElement(contenido, f"{{{NS_DS}}}Signature", Id="placeholder", nsmap={"ds": NS_DS})

        firmador = _FirmadorSignxmlDian(
            signature_policy=POLITICA_FIRMA_DIAN,
            claimed_roles=[ROL_FIRMANTE],
            signature_algorithm=SignatureMethod.RSA_SHA256,
            digest_algorithm=DigestAlgorithm.SHA256,
            c14n_algorithm=CanonicalizationMethod.CANONICAL_XML_1_0,
        )
        firmador.namespaces.update(xades141=NS_XADES141)
        try:
            firmado = firmador.sign(
                raiz,
                key=self._llave,
                cert=[self._certificado, *self._cadena],
                always_add_key_value=False,
                # La DIAN espera solo la transformación enveloped-signature en la referencia.
                exclude_c14n_transform_element=True,
            )
        except Exception as exc:
            logger.exception("Fallo al firmar el documento XAdES")
            raise ErrorFirma("No se pudo firmar el documento") from exc
        return etree.tostring(firmado, xml_declaration=True, encoding="UTF-8")
