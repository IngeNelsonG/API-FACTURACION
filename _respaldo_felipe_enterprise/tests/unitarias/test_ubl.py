from __future__ import annotations

import io
import zipfile
from decimal import Decimal

import pytest
from lxml import etree

from facturacion.dominio.factura import LineaFactura
from facturacion.ubl.empaquetado import empaquetar_zip, nombre_base
from facturacion.ubl.generador import NS, DatosSoftware, generar_xml_factura
from tests.unitarias.test_dominio import _factura

SOFTWARE = DatosSoftware("software-id", "a" * 96, "2", "NumFac=X")
NSX = {k: v for k, v in NS.items() if k}
NSX["inv"] = NS[None]


def _xml() -> etree._Element:
    factura = _factura(
        [
            LineaFactura("Uno <&>", Decimal("2"), Decimal("10.00"), Decimal("19"), codigo="P1"),
            LineaFactura("Dos", Decimal("1"), Decimal("5.00"), Decimal("0")),
        ],
        prefijo="SETP",
        numero=990000001,
    )
    factura.cufe = "b" * 96
    return etree.fromstring(generar_xml_factura(factura, SOFTWARE))


def test_estructura_basica_del_invoice():
    raiz = _xml()
    assert raiz.tag == f"{{{NS[None]}}}Invoice"
    assert raiz.findtext("cbc:ID", namespaces=NSX) == "SETP990000001"
    assert raiz.findtext("cbc:UUID", namespaces=NSX) == "b" * 96
    assert raiz.find("cbc:UUID", NSX).get("schemeName") == "CUFE-SHA384"
    assert raiz.findtext("cbc:ProfileExecutionID", namespaces=NSX) == "2"
    assert raiz.findtext("cbc:LineCountNumeric", namespaces=NSX) == "2"
    assert raiz.findtext("cac:LegalMonetaryTotal/cbc:PayableAmount", namespaces=NSX) == "28.80"
    assert raiz.findtext("cac:TaxTotal/cbc:TaxAmount", namespaces=NSX) == "3.80"
    # El texto del usuario se escapa: no se interpreta como XML.
    assert raiz.findtext("cac:InvoiceLine/cac:Item/cbc:Description", namespaces=NSX) == "Uno <&>"


def test_extensiones_dian_y_contenedor_de_firma():
    extensiones = _xml().findall("ext:UBLExtensions/ext:UBLExtension", NSX)
    assert len(extensiones) == 2
    dian = extensiones[0].find("ext:ExtensionContent/sts:DianExtensions", NSX)
    assert dian.findtext("sts:SoftwareProvider/sts:SoftwareID", namespaces=NSX) == "software-id"
    assert dian.findtext("sts:QRCode", namespaces=NSX) == "NumFac=X"
    assert len(extensiones[1].find("ext:ExtensionContent", NSX)) == 0


def test_orden_de_elementos_segun_xsd():
    nombres = [etree.QName(hijo).localname for hijo in _xml()]
    esperado = [
        "UBLExtensions",
        "UBLVersionID",
        "CustomizationID",
        "ProfileID",
        "ProfileExecutionID",
        "ID",
        "UUID",
        "IssueDate",
        "IssueTime",
        "InvoiceTypeCode",
        "DocumentCurrencyCode",
        "LineCountNumeric",
        "AccountingSupplierParty",
        "AccountingCustomerParty",
        "PaymentMeans",
        "TaxTotal",
        "LegalMonetaryTotal",
        "InvoiceLine",
        "InvoiceLine",
    ]
    assert nombres == esperado


def test_sin_cufe_falla():
    factura = _factura([LineaFactura("A", Decimal(1), Decimal(1))])
    with pytest.raises(ValueError):
        generar_xml_factura(factura, SOFTWARE)


def test_nombre_de_archivo_dian():
    assert nombre_base("900123456", 2026, 255) == "fv090012345600026000000ff"
    with pytest.raises(ValueError):
        nombre_base("90012345A", 2026, 1)
    with pytest.raises(ValueError):
        nombre_base("900123456", 2026, 0)


def test_zip_contiene_un_xml():
    contenido = empaquetar_zip("fv1.xml", b"<a/>")
    with zipfile.ZipFile(io.BytesIO(contenido)) as archivo:
        assert archivo.namelist() == ["fv1.xml"]
        assert archivo.read("fv1.xml") == b"<a/>"
