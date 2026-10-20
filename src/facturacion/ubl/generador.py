"""Generación del XML UBL 2.1 de la factura electrónica de venta (Anexo Técnico v1.9).

El documento se genera con ``UBLExtension[2]/ExtensionContent`` vacío: ahí el
firmador inserta la firma XAdES-EPES. El orden de los elementos sigue el XSD
de UBL 2.1, que es estricto con la secuencia.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from lxml import etree

from facturacion.dominio.cufe import formatear_hora
from facturacion.dominio.factura import Adquiriente, Emisor, Factura, LineaFactura

NS = {
    None: "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "sts": "dian:gov:co:facturaelectronica:Structures-2-1",
    "ds": "http://www.w3.org/2000/09/xmldsig#",
    "xades": "http://uri.etsi.org/01903/v1.3.2#",
    "xades141": "http://uri.etsi.org/01903/v1.4.1#",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

AGENCIA_DIAN = {
    "schemeAgencyID": "195",
    "schemeAgencyName": "CO, DIAN (Dirección de Impuestos y Aduanas Nacionales)",
}
NIT_DIAN = "800197268"
DV_DIAN = "4"
TIPO_DOCUMENTO_NIT = "31"
CODIGO_IVA = ("01", "IVA")


@dataclass(frozen=True, slots=True)
class DatosSoftware:
    software_id: str
    software_security_code: str
    tipo_ambiente: str
    contenido_qr: str


def _q(prefijo: str | None, nombre: str) -> str:
    return f"{{{NS[prefijo]}}}{nombre}"


def _sub(
    padre: etree._Element, prefijo: str, nombre: str, texto: str | None = None, **atributos: str
) -> etree._Element:
    elemento = etree.SubElement(padre, _q(prefijo, nombre), attrib=atributos or None)
    if texto is not None:
        elemento.text = texto
    return elemento


def _monto(padre: etree._Element, nombre: str, valor: Decimal, moneda: str) -> None:
    _sub(padre, "cbc", nombre, f"{valor:.2f}", currencyID=moneda)


def generar_xml_factura(factura: Factura, software: DatosSoftware) -> bytes:
    if not factura.cufe:
        raise ValueError("La factura debe tener CUFE antes de generar el XML")

    raiz = etree.Element(_q(None, "Invoice"), nsmap=NS)
    _extensiones(raiz, factura, software)

    _sub(raiz, "cbc", "UBLVersionID", "UBL 2.1")
    _sub(raiz, "cbc", "CustomizationID", "10")  # 10 = operación estándar
    _sub(raiz, "cbc", "ProfileID", "DIAN 2.1: Factura Electrónica de Venta")
    _sub(raiz, "cbc", "ProfileExecutionID", software.tipo_ambiente)
    _sub(raiz, "cbc", "ID", factura.numeracion.numero_completo)
    _sub(
        raiz, "cbc", "UUID", factura.cufe, schemeID=software.tipo_ambiente, schemeName="CUFE-SHA384"
    )
    _sub(raiz, "cbc", "IssueDate", factura.fecha_emision.isoformat())
    _sub(raiz, "cbc", "IssueTime", formatear_hora(factura))
    if factura.fecha_vencimiento:
        _sub(raiz, "cbc", "DueDate", factura.fecha_vencimiento.isoformat())
    _sub(raiz, "cbc", "InvoiceTypeCode", "01")  # 01 = factura electrónica de venta
    if factura.notas:
        _sub(raiz, "cbc", "Note", factura.notas)
    _sub(raiz, "cbc", "DocumentCurrencyCode", factura.moneda)
    _sub(raiz, "cbc", "LineCountNumeric", str(len(factura.lineas)))

    _emisor(raiz, factura.emisor, factura.numeracion.prefijo)
    _adquiriente(raiz, factura.adquiriente)

    medio = _sub(raiz, "cac", "PaymentMeans")
    _sub(medio, "cbc", "ID", factura.forma_pago.value)
    _sub(medio, "cbc", "PaymentMeansCode", factura.medio_pago)
    if factura.fecha_vencimiento:
        _sub(medio, "cbc", "PaymentDueDate", factura.fecha_vencimiento.isoformat())

    _total_impuestos(raiz, factura)
    _totales(raiz, factura)
    for indice, linea in enumerate(factura.lineas, start=1):
        _linea(raiz, indice, linea, factura.moneda)

    return etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=False)


def _extensiones(raiz: etree._Element, factura: Factura, software: DatosSoftware) -> None:
    extensiones = _sub(raiz, "ext", "UBLExtensions")
    contenido = _sub(_sub(extensiones, "ext", "UBLExtension"), "ext", "ExtensionContent")
    dian = _sub(contenido, "sts", "DianExtensions")

    control = _sub(dian, "sts", "InvoiceControl")
    numeracion = factura.numeracion
    _sub(control, "sts", "InvoiceAuthorization", numeracion.resolucion)
    periodo = _sub(control, "sts", "AuthorizationPeriod")
    _sub(periodo, "cbc", "StartDate", numeracion.fecha_desde.isoformat())
    _sub(periodo, "cbc", "EndDate", numeracion.fecha_hasta.isoformat())
    autorizadas = _sub(control, "sts", "AuthorizedInvoices")
    if numeracion.prefijo:
        _sub(autorizadas, "sts", "Prefix", numeracion.prefijo)
    _sub(autorizadas, "sts", "From", str(numeracion.rango_desde))
    _sub(autorizadas, "sts", "To", str(numeracion.rango_hasta))

    origen = _sub(dian, "sts", "InvoiceSource")
    _sub(
        origen,
        "cbc",
        "IdentificationCode",
        "CO",
        listAgencyID="6",
        listAgencyName="United Nations Economic Commission for Europe",
        listSchemeURI="urn:oasis:names:specification:ubl:codelist:gc:CountryIdentificationCode-2.1",
    )

    proveedor = _sub(dian, "sts", "SoftwareProvider")
    _sub(
        proveedor,
        "sts",
        "ProviderID",
        factura.emisor.nit,
        **AGENCIA_DIAN,
        schemeID=factura.emisor.dv,
        schemeName=TIPO_DOCUMENTO_NIT,
    )
    _sub(proveedor, "sts", "SoftwareID", software.software_id, **AGENCIA_DIAN)
    _sub(dian, "sts", "SoftwareSecurityCode", software.software_security_code, **AGENCIA_DIAN)

    autorizador = _sub(dian, "sts", "AuthorizationProvider")
    _sub(
        autorizador,
        "sts",
        "AuthorizationProviderID",
        NIT_DIAN,
        **AGENCIA_DIAN,
        schemeID=DV_DIAN,
        schemeName=TIPO_DOCUMENTO_NIT,
    )
    _sub(dian, "sts", "QRCode", software.contenido_qr)

    # UBLExtension[2]: contenedor vacío donde se inserta la firma XAdES.
    _sub(_sub(extensiones, "ext", "UBLExtension"), "ext", "ExtensionContent")


def _direccion(
    padre: etree._Element,
    nombre: str,
    *,
    ciudad: str,
    codigo_municipio: str,
    departamento: str,
    codigo_departamento: str,
    direccion: str,
) -> None:
    elemento = _sub(padre, "cac", nombre)
    _sub(elemento, "cbc", "ID", codigo_municipio)
    _sub(elemento, "cbc", "CityName", ciudad)
    _sub(elemento, "cbc", "CountrySubentity", departamento)
    _sub(elemento, "cbc", "CountrySubentityCode", codigo_departamento)
    if direccion:
        _sub(_sub(elemento, "cac", "AddressLine"), "cbc", "Line", direccion)
    pais = _sub(elemento, "cac", "Country")
    _sub(pais, "cbc", "IdentificationCode", "CO")
    _sub(pais, "cbc", "Name", "Colombia", languageID="es")


def _esquema_iva(padre: etree._Element) -> None:
    esquema = _sub(padre, "cac", "TaxScheme")
    _sub(esquema, "cbc", "ID", CODIGO_IVA[0])
    _sub(esquema, "cbc", "Name", CODIGO_IVA[1])


def _emisor(raiz: etree._Element, emisor: Emisor, prefijo: str) -> None:
    parte_contable = _sub(raiz, "cac", "AccountingSupplierParty")
    _sub(parte_contable, "cbc", "AdditionalAccountID", emisor.tipo_organizacion)
    parte = _sub(parte_contable, "cac", "Party")
    _sub(_sub(parte, "cac", "PartyName"), "cbc", "Name", emisor.nombre_comercial)
    ubicacion = {
        "ciudad": emisor.ciudad,
        "codigo_municipio": emisor.codigo_municipio,
        "departamento": emisor.departamento,
        "codigo_departamento": emisor.codigo_departamento,
        "direccion": emisor.direccion,
    }
    _direccion(_sub(parte, "cac", "PhysicalLocation"), "Address", **ubicacion)

    tributario = _sub(parte, "cac", "PartyTaxScheme")
    _sub(tributario, "cbc", "RegistrationName", emisor.razon_social)
    _sub(
        tributario,
        "cbc",
        "CompanyID",
        emisor.nit,
        **AGENCIA_DIAN,
        schemeID=emisor.dv,
        schemeName=TIPO_DOCUMENTO_NIT,
    )
    _sub(tributario, "cbc", "TaxLevelCode", emisor.responsabilidades, listName="48")
    _direccion(tributario, "RegistrationAddress", **ubicacion)
    _esquema_iva(tributario)

    legal = _sub(parte, "cac", "PartyLegalEntity")
    _sub(legal, "cbc", "RegistrationName", emisor.razon_social)
    _sub(
        legal,
        "cbc",
        "CompanyID",
        emisor.nit,
        **AGENCIA_DIAN,
        schemeID=emisor.dv,
        schemeName=TIPO_DOCUMENTO_NIT,
    )
    if prefijo:
        _sub(_sub(legal, "cac", "CorporateRegistrationScheme"), "cbc", "ID", prefijo)

    contacto = _sub(parte, "cac", "Contact")
    _sub(contacto, "cbc", "Telephone", emisor.telefono)
    _sub(contacto, "cbc", "ElectronicMail", emisor.email)


def _adquiriente(raiz: etree._Element, adquiriente: Adquiriente) -> None:
    parte_contable = _sub(raiz, "cac", "AccountingCustomerParty")
    _sub(
        parte_contable,
        "cbc",
        "AdditionalAccountID",
        "1" if adquiriente.es_persona_juridica else "2",
    )
    parte = _sub(parte_contable, "cac", "Party")
    identificacion = {"schemeName": adquiriente.tipo_documento.value}
    if adquiriente.dv is not None:
        identificacion["schemeID"] = adquiriente.dv
    _sub(
        _sub(parte, "cac", "PartyIdentification"),
        "cbc",
        "ID",
        adquiriente.numero_documento,
        **identificacion,
    )
    _sub(_sub(parte, "cac", "PartyName"), "cbc", "Name", adquiriente.nombre)
    ubicacion = {
        "ciudad": adquiriente.ciudad,
        "codigo_municipio": adquiriente.codigo_municipio,
        "departamento": adquiriente.departamento,
        "codigo_departamento": adquiriente.codigo_departamento,
        "direccion": adquiriente.direccion,
    }
    if adquiriente.ciudad:
        _direccion(_sub(parte, "cac", "PhysicalLocation"), "Address", **ubicacion)

    tributario = _sub(parte, "cac", "PartyTaxScheme")
    _sub(tributario, "cbc", "RegistrationName", adquiriente.nombre)
    _sub(
        tributario,
        "cbc",
        "CompanyID",
        adquiriente.numero_documento,
        **AGENCIA_DIAN,
        **identificacion,
    )
    _sub(tributario, "cbc", "TaxLevelCode", "R-99-PN", listName="48")
    _esquema_iva(tributario)

    legal = _sub(parte, "cac", "PartyLegalEntity")
    _sub(legal, "cbc", "RegistrationName", adquiriente.nombre)
    _sub(legal, "cbc", "CompanyID", adquiriente.numero_documento, **AGENCIA_DIAN, **identificacion)

    contacto = _sub(parte, "cac", "Contact")
    if adquiriente.telefono:
        _sub(contacto, "cbc", "Telephone", adquiriente.telefono)
    _sub(contacto, "cbc", "ElectronicMail", adquiriente.email)


def _subtotal_iva(
    padre: etree._Element, base: Decimal, valor: Decimal, porcentaje: Decimal, moneda: str
) -> None:
    subtotal = _sub(padre, "cac", "TaxSubtotal")
    _monto(subtotal, "TaxableAmount", base, moneda)
    _monto(subtotal, "TaxAmount", valor, moneda)
    categoria = _sub(subtotal, "cac", "TaxCategory")
    _sub(categoria, "cbc", "Percent", f"{porcentaje:.2f}")
    _esquema_iva(categoria)


def _total_impuestos(raiz: etree._Element, factura: Factura) -> None:
    totales = factura.totales
    total = _sub(raiz, "cac", "TaxTotal")
    _monto(total, "TaxAmount", totales.total_iva, factura.moneda)
    for impuesto in totales.impuestos_iva:
        _subtotal_iva(total, impuesto.base, impuesto.valor, impuesto.porcentaje, factura.moneda)


def _totales(raiz: etree._Element, factura: Factura) -> None:
    totales = factura.totales
    monetario = _sub(raiz, "cac", "LegalMonetaryTotal")
    _monto(monetario, "LineExtensionAmount", totales.subtotal, factura.moneda)
    _monto(monetario, "TaxExclusiveAmount", totales.subtotal, factura.moneda)
    _monto(monetario, "TaxInclusiveAmount", totales.total_a_pagar, factura.moneda)
    _monto(monetario, "PayableAmount", totales.total_a_pagar, factura.moneda)


def _linea(raiz: etree._Element, indice: int, linea: LineaFactura, moneda: str) -> None:
    elemento = _sub(raiz, "cac", "InvoiceLine")
    _sub(elemento, "cbc", "ID", str(indice))
    _sub(elemento, "cbc", "InvoicedQuantity", f"{linea.cantidad:f}", unitCode=linea.unidad_medida)
    _monto(elemento, "LineExtensionAmount", linea.subtotal, moneda)
    impuesto = _sub(elemento, "cac", "TaxTotal")
    _monto(impuesto, "TaxAmount", linea.valor_iva, moneda)
    _subtotal_iva(impuesto, linea.subtotal, linea.valor_iva, linea.porcentaje_iva, moneda)
    item = _sub(elemento, "cac", "Item")
    _sub(item, "cbc", "Description", linea.descripcion)
    if linea.codigo:
        _sub(
            _sub(item, "cac", "StandardItemIdentification"),
            "cbc",
            "ID",
            linea.codigo,
            schemeID="999",
        )
    precio = _sub(elemento, "cac", "Price")
    _monto(precio, "PriceAmount", linea.precio_unitario, moneda)
    _sub(precio, "cbc", "BaseQuantity", "1", unitCode=linea.unidad_medida)
