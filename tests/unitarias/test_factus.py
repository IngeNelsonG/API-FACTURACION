from __future__ import annotations

import base64
import json
import logging
from datetime import date, time, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qs

import httpx
import pytest

from facturacion.dominio.factura import (
    Adquiriente,
    Emisor,
    Factura,
    FormaPago,
    LineaFactura,
    Numeracion,
    TipoDocumentoIdentidad,
)
from facturacion.proveedor import factus as modulo
from facturacion.proveedor.factus import ClienteFactus, construir_payload, extraer_mensajes
from facturacion.proveedor.puertos import ErrorProveedor, RechazoProveedor

URL = "https://api-sandbox.factus.com.co"
CLIENT_ID = "id-cliente-prueba"
CLIENT_SECRET = "secreto-cliente-NO-LOGUEAR"
USUARIO = "usuario@example.com"
CLAVE = "clave-usuario-NO-LOGUEAR"
CUFE = "a1" * 48
XML = b"<Invoice>ok</Invoice>"

COT = timezone(timedelta(hours=-5))
EMISOR = Emisor(
    nit="700085371",
    dv="1",
    razon_social="EMISOR",
    nombre_comercial="EMISOR",
    tipo_organizacion="1",
    responsabilidades="O-13",
    direccion="Calle 1",
    ciudad="Bogotá",
    codigo_municipio="11001",
    departamento="Bogotá",
    codigo_departamento="11",
    email="e@example.com",
    telefono="1",
)
EMPRESA = Adquiriente(
    tipo_documento=TipoDocumentoIdentidad.NIT,
    numero_documento="800199436",
    dv="1",
    nombre="ADQUIRIENTE S.A.S.",
    email="a@example.com",
    direccion="Cra 7 # 1-1",
    telefono="3000000000",
    codigo_municipio="68679",
)
PERSONA = Adquiriente(
    tipo_documento=TipoDocumentoIdentidad.CEDULA_CIUDADANIA,
    numero_documento="1020304050",
    nombre="Ana Pérez",
    email="ana@example.com",
)


def _factura(
    adquiriente: Adquiriente = EMPRESA,
    lineas: list[LineaFactura] | None = None,
    **extra: object,
) -> Factura:
    return Factura(
        emisor=EMISOR,
        adquiriente=adquiriente,
        lineas=lineas or [LineaFactura("Producto", Decimal("2"), Decimal("1000.00"))],
        numeracion=Numeracion("", 0, "", date(2026, 1, 1), date(2026, 1, 1), 0, 0),
        fecha_emision=date(2026, 10, 20),
        hora_emision=time(10, 0, 0, tzinfo=COT),
        **extra,  # type: ignore[arg-type]
    )


def _token(n: int = 1, expira: int = 3600) -> dict[str, object]:
    return {
        "token_type": "Bearer",
        "expires_in": expira,
        "access_token": f"token-acceso-{n}",
        "refresh_token": f"token-renovacion-{n}",
    }


def _respuesta_validada(**cambios: object) -> dict[str, object]:
    datos: dict[str, object] = {
        "reference_code": "REF-1",
        "number": "SETP990000550",
        "is_validated": True,
        "validated_at": "20-10-2026 10:00:05 AM",
        "errors": {"RUT01": "Regla: RUT01, Notificación: el adquiriente no está en el RUT"},
        "cufe": CUFE,
        "numbering_range": {
            "prefix": "SETP",
            "from": 990000000,
            "to": "995000000",
            "resolution_number": "18760000001",
            "start_date": "2019-01-19",
            "end_date": "19-01-2030",
            "months": 132,
        },
        "links": {
            "qr": "https://catalogo-vpfe-hab.dian.gov.co/document/searchqr?documentkey=" + CUFE,
            "public_url": "https://sandbox.factus.com.co/x",
        },
    }
    datos.update(cambios)
    return {"status": "Created", "message": "Documento con validación previa", "data": datos}


class Servidor:
    """Simula Factus y registra las peticiones."""

    def __init__(self) -> None:
        self.peticiones: list[httpx.Request] = []
        self.tokens_emitidos = 0
        self.respuestas_validar: list[httpx.Response] = []
        self.respuesta_token: httpx.Response | None = None
        self.respuesta_refresh: httpx.Response | None = None
        self.respuesta_xml: httpx.Response | Exception | None = None
        self.expira_en = 3600

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones.append(peticion)
        ruta = peticion.url.path
        if ruta == "/oauth/token":
            formulario = parse_qs(peticion.content.decode())
            if formulario["grant_type"] == ["refresh_token"] and self.respuesta_refresh:
                return self.respuesta_refresh
            if formulario["grant_type"] == ["password"] and self.respuesta_token:
                return self.respuesta_token
            self.tokens_emitidos += 1
            return httpx.Response(200, json=_token(self.tokens_emitidos, self.expira_en))
        if ruta == "/v2/bills/validate":
            if self.respuestas_validar:
                return self.respuestas_validar.pop(0)
            return httpx.Response(201, json=_respuesta_validada())
        if ruta == "/v2/bills/SETP990000550/download-xml":
            if isinstance(self.respuesta_xml, Exception):
                raise self.respuesta_xml
            if self.respuesta_xml is not None:
                return self.respuesta_xml
            codificado = base64.b64encode(XML).decode()
            return httpx.Response(
                200,
                json={
                    "status": "OK",
                    "data": {"file_name": "fv.xml", "xml_base_64_encoded": codificado},
                },
            )
        return httpx.Response(404, json={"message": "no encontrado"})

    def de_ruta(self, ruta: str) -> list[httpx.Request]:
        return [p for p in self.peticiones if p.url.path == ruta]


@pytest.fixture
def servidor() -> Servidor:
    return Servidor()


def _cliente(servidor: Servidor, rango: int | None = 389) -> ClienteFactus:
    http = httpx.Client(transport=httpx.MockTransport(servidor))
    return ClienteFactus(
        url=URL,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        usuario=USUARIO,
        clave=CLAVE,
        rango_numeracion_id=rango,
        timeout=5,
        http_client=http,
    )


# --------------------------------------------------------------------------- #
# Autenticación
# --------------------------------------------------------------------------- #


def test_autenticacion_envia_formulario_y_reutiliza_el_token(servidor):
    cliente = _cliente(servidor)
    cliente.emitir(_factura(), "REF-1")
    cliente.emitir(_factura(), "REF-2")

    tokens = servidor.de_ruta("/oauth/token")
    assert len(tokens) == 1
    assert tokens[0].method == "POST"
    assert tokens[0].headers["content-type"] == "application/x-www-form-urlencoded"
    assert parse_qs(tokens[0].content.decode()) == {
        "grant_type": ["password"],
        "username": [USUARIO],
        "password": [CLAVE],
        "client_id": [CLIENT_ID],
        "client_secret": [CLIENT_SECRET],
    }
    validaciones = servidor.de_ruta("/v2/bills/validate")
    assert len(validaciones) == 2
    assert all(p.headers["authorization"] == "Bearer token-acceso-1" for p in validaciones)
    assert all(p.url.scheme == "https" for p in servidor.peticiones)


class Reloj:
    def __init__(self) -> None:
        self.ahora = 1000.0

    def monotonic(self) -> float:
        return self.ahora


@pytest.fixture
def reloj(monkeypatch) -> Reloj:
    falso = Reloj()
    monkeypatch.setattr(modulo, "time", falso)
    return falso


def test_token_vencido_se_renueva_con_refresh_token(servidor, reloj):
    cliente = _cliente(servidor)
    cliente.emitir(_factura(), "REF-1")
    reloj.ahora += 3600 - modulo.MARGEN_EXPIRACION_SEGUNDOS - 1
    cliente.emitir(_factura(), "REF-2")
    assert len(servidor.de_ruta("/oauth/token")) == 1  # aún vigente (con margen)
    reloj.ahora += 2
    cliente.emitir(_factura(), "REF-3")

    tokens = [parse_qs(p.content.decode()) for p in servidor.de_ruta("/oauth/token")]
    assert [t["grant_type"] for t in tokens] == [["password"], ["refresh_token"]]
    assert tokens[1]["refresh_token"] == ["token-renovacion-1"]
    assert tokens[1]["client_secret"] == [CLIENT_SECRET]
    validaciones = servidor.de_ruta("/v2/bills/validate")
    assert validaciones[2].headers["authorization"] == "Bearer token-acceso-2"


def test_refresh_rechazado_vuelve_a_iniciar_sesion(servidor, reloj):
    servidor.respuesta_refresh = httpx.Response(401, json={"message": "invalid_grant"})
    cliente = _cliente(servidor)
    cliente.emitir(_factura(), "REF-1")
    reloj.ahora += 3600
    cliente.emitir(_factura(), "REF-2")

    concesiones = [
        parse_qs(p.content.decode())["grant_type"][0] for p in servidor.de_ruta("/oauth/token")
    ]
    assert concesiones == ["password", "refresh_token", "password"]


def test_401_en_validate_reautentica_y_reintenta_una_vez(servidor):
    servidor.respuestas_validar = [httpx.Response(401, json={"message": "Unauthenticated."})]
    resultado = _cliente(servidor).emitir(_factura(), "REF-1")

    assert resultado.cufe == CUFE
    validaciones = servidor.de_ruta("/v2/bills/validate")
    assert [p.headers["authorization"] for p in validaciones] == [
        "Bearer token-acceso-1",
        "Bearer token-acceso-2",
    ]


def test_401_persistente_es_error_de_proveedor(servidor):
    servidor.respuestas_validar = [httpx.Response(401), httpx.Response(401)]
    with pytest.raises(ErrorProveedor, match="autenticarse"):
        _cliente(servidor).emitir(_factura(), "REF-1")
    assert len(servidor.de_ruta("/v2/bills/validate")) == 2


def test_credenciales_rechazadas_es_error_de_proveedor(servidor):
    servidor.respuesta_token = httpx.Response(401, json={"message": "invalid_client"})
    with pytest.raises(ErrorProveedor, match="autenticarse"):
        _cliente(servidor).emitir(_factura(), "REF-1")
    assert servidor.de_ruta("/v2/bills/validate") == []


# --------------------------------------------------------------------------- #
# Construcción del JSON
# --------------------------------------------------------------------------- #


def test_payload_persona_juridica_con_nit_y_dv():
    payload = construir_payload(_factura(EMPRESA, notas="Pedido 45"), "REF-1", 389)

    assert payload["reference_code"] == "REF-1"
    assert payload["numbering_range_id"] == 389
    assert payload["document"] == "01"
    assert payload["operation_type"] == "10"
    assert payload["observation"] == "Pedido 45"
    assert payload["customer"] == {
        "identification_document_code": "31",
        "identification": "800199436",
        "dv": "1",
        "legal_organization_code": "1",
        "tribute_code": "ZZ",
        "company": "ADQUIRIENTE S.A.S.",
        "trade_name": "ADQUIRIENTE S.A.S.",
        "address": "Cra 7 # 1-1",
        "email": "a@example.com",
        "phone": "3000000000",
        "municipality_code": "68679",
    }
    assert payload["payment_details"] == [
        {"payment_form": "1", "payment_method_code": "10", "amount": "2380.00"}
    ]
    json.dumps(payload)  # serializable


def test_payload_persona_natural_con_cedula():
    cliente = construir_payload(_factura(PERSONA), "REF-1", None)["customer"]

    assert cliente["identification_document_code"] == "13"
    assert cliente["legal_organization_code"] == "2"
    assert cliente["names"] == "Ana Pérez"
    assert "company" not in cliente
    assert "dv" not in cliente
    assert cliente["municipality_code"] == "11001"


def test_payload_sin_rango_omite_numbering_range_id_y_observacion_vacia():
    payload = construir_payload(_factura(), "REF-1", None)
    assert "numbering_range_id" not in payload
    assert "observation" not in payload


def test_payload_cliente_extranjero_no_lleva_municipio():
    extranjero = Adquiriente(
        tipo_documento=TipoDocumentoIdentidad.NIT_OTRO_PAIS,
        numero_documento="X123",
        nombre="Foreign Inc",
        email="f@example.com",
    )
    cliente = construir_payload(_factura(extranjero), "R", None)["customer"]
    assert "municipality_code" not in cliente
    assert cliente["legal_organization_code"] == "1"
    assert cliente["identification_document_code"] == "50"


def test_payload_items_con_iva_0_5_y_19():
    lineas = [
        LineaFactura("A", Decimal("1"), Decimal("100.00"), Decimal("0"), codigo="A1"),
        LineaFactura("B", Decimal("2.5"), Decimal("10.50"), Decimal("5")),
        LineaFactura("C", Decimal("3"), Decimal("33.33"), Decimal("19"), unidad_medida="KGM"),
    ]
    factura = _factura(lineas=lineas)
    payload = construir_payload(factura, "R", None)

    items = payload["items"]
    assert [i["taxes"] for i in items] == [
        [{"code": "01", "rate": "0.00"}],
        [{"code": "01", "rate": "5.00"}],
        [{"code": "01", "rate": "19.00"}],
    ]
    assert items[0] == {
        "code_reference": "A1",
        "name": "A",
        "quantity": "1.00",
        "discount_rate": "0.00",
        "price": "100.00",
        "unit_measure_code": "94",
        "standard_code": "999",
        "taxes": [{"code": "01", "rate": "0.00"}],
    }
    assert items[1]["code_reference"] == "ITEM-2"
    assert items[1]["quantity"] == "2.50"
    assert items[2]["unit_measure_code"] == "KGM"
    assert payload["payment_details"][0]["amount"] == f"{factura.totales.total_a_pagar:.2f}"


def test_payload_credito_lleva_fecha_de_vencimiento():
    factura = _factura(
        forma_pago=FormaPago.CREDITO, medio_pago="47", fecha_vencimiento=date(2026, 11, 19)
    )
    assert construir_payload(factura, "R", None)["payment_details"] == [
        {
            "payment_form": "2",
            "payment_method_code": "47",
            "amount": "2380.00",
            "due_date": "2026-11-19",
        }
    ]


def test_payload_credito_sin_vencimiento_es_rechazo(servidor):
    factura = _factura(forma_pago=FormaPago.CREDITO)
    with pytest.raises(ValueError, match="vencimiento"):
        construir_payload(factura, "R", None)
    with pytest.raises(RechazoProveedor):
        _cliente(servidor).emitir(factura, "R")
    assert servidor.peticiones == []


def test_payload_rechaza_mas_de_dos_decimales():
    factura = _factura(lineas=[LineaFactura("A", Decimal("1.555"), Decimal("1"))])
    with pytest.raises(ValueError, match="dos decimales"):
        construir_payload(factura, "R", None)


def test_payload_trunca_observacion_y_quita_saltos():
    payload = construir_payload(_factura(notas="línea\r\n" + "x" * 900), "R", None)
    assert len(payload["observation"]) == 500
    assert "\n" not in payload["observation"]


# --------------------------------------------------------------------------- #
# Respuesta exitosa
# --------------------------------------------------------------------------- #


def test_exito_interpreta_numeracion_cufe_qr_y_xml(servidor):
    resultado = _cliente(servidor).emitir(_factura(), "REF-1")

    assert resultado.numeracion == Numeracion(
        prefijo="SETP",
        numero=990000550,
        resolucion="18760000001",
        fecha_desde=date(2019, 1, 19),
        fecha_hasta=date(2030, 1, 19),
        rango_desde=990000000,
        rango_hasta=995000000,
    )
    assert resultado.numeracion.numero_completo == "SETP990000550"
    assert resultado.cufe == CUFE
    assert resultado.url_qr.startswith("https://catalogo-vpfe-hab.dian.gov.co/")
    assert resultado.identificador_externo == "SETP990000550"
    assert resultado.xml == XML
    assert resultado.mensajes[0] == "Documento con validación previa"
    assert any("RUT01" in m for m in resultado.mensajes)
    descarga = servidor.de_ruta("/v2/bills/SETP990000550/download-xml")[0]
    assert descarga.method == "GET"
    assert descarga.headers["authorization"] == "Bearer token-acceso-1"


def test_exito_con_datos_faltantes_usa_respaldos(servidor):
    servidor.respuestas_validar = [
        httpx.Response(
            200,
            json=_respuesta_validada(number="FE77", numbering_range=None, links=None, errors=[]),
        )
    ]
    resultado = _cliente(servidor).emitir(_factura(), "REF-1")
    assert resultado.numeracion == Numeracion(
        "FE", 77, "", date(2026, 10, 20), date(2026, 10, 20), 77, 77
    )
    assert resultado.url_qr == ""


@pytest.mark.parametrize(
    "respuesta_xml",
    [
        httpx.Response(500),
        httpx.Response(200, json={"data": {"xml_base_64_encoded": "%%no-base64%%"}}),
        httpx.Response(200, content=b"no json"),
        httpx.ConnectError("caido"),
    ],
)
def test_fallo_al_descargar_xml_se_tolera(servidor, caplog, respuesta_xml):
    servidor.respuesta_xml = respuesta_xml
    with caplog.at_level(logging.WARNING, logger=modulo.__name__):
        resultado = _cliente(servidor).emitir(_factura(), "REF-1")
    assert resultado.xml is None
    assert resultado.cufe == CUFE
    assert "XML" in caplog.text


@pytest.mark.parametrize("cufe", ["", "abc", "z" * 96, "a" * 95])
def test_cufe_invalido_es_error_de_proveedor(servidor, cufe):
    servidor.respuestas_validar = [httpx.Response(201, json=_respuesta_validada(cufe=cufe))]
    with pytest.raises(ErrorProveedor, match="CUFE"):
        _cliente(servidor).emitir(_factura(), "REF-1")


def test_no_validada_con_rechazo_dian_es_rechazo(servidor):
    servidor.respuestas_validar = [
        httpx.Response(
            201,
            json=_respuesta_validada(
                is_validated=False,
                errors={
                    "FAJ43b": "Regla: FAJ43b, Rechazo: Nombre informado no corresponde al RUT",
                    "RUT01": "Regla: RUT01, Notificación: x",
                },
            ),
        )
    ]
    with pytest.raises(RechazoProveedor) as error:
        _cliente(servidor).emitir(_factura(), "REF-1")
    assert error.value.mensajes == [
        "Regla: FAJ43b, Rechazo: Nombre informado no corresponde al RUT"
    ]


def test_no_validada_sin_rechazo_es_error_transitorio(servidor):
    servidor.respuestas_validar = [
        httpx.Response(201, json=_respuesta_validada(is_validated=False, errors={}))
    ]
    with pytest.raises(ErrorProveedor, match="no ha validado"):
        _cliente(servidor).emitir(_factura(), "REF-1")


# --------------------------------------------------------------------------- #
# Errores
# --------------------------------------------------------------------------- #


def test_422_con_errores_anidados_es_rechazo_con_mensajes(servidor):
    servidor.respuestas_validar = [
        httpx.Response(
            422,
            json={
                "status": "Validation error",
                "message": "Error de validación",
                "data": {
                    "errors": {
                        "customer.identification": ["El campo identificación es obligatorio."],
                        "items": {"0": {"price": ["El precio debe ser numérico.\nOtra"]}},
                    }
                },
            },
        )
    ]
    with pytest.raises(RechazoProveedor) as error:
        _cliente(servidor).emitir(_factura(), "REF-1")
    assert error.value.mensajes == [
        "Error de validación",
        "customer.identification: El campo identificación es obligatorio.",
        "items.0.price: El precio debe ser numérico. Otra",
    ]


def test_409_factura_pendiente_es_rechazo(servidor):
    mensaje = "Se encontró una factura pendiente por enviar a la DIAN"
    servidor.respuestas_validar = [httpx.Response(409, json={"message": mensaje})]
    with pytest.raises(RechazoProveedor) as error:
        _cliente(servidor).emitir(_factura(), "REF-1")
    assert error.value.mensajes == [mensaje]


def test_400_sin_cuerpo_es_rechazo_generico(servidor):
    servidor.respuestas_validar = [httpx.Response(400, content=b"<html>")]
    with pytest.raises(RechazoProveedor) as error:
        _cliente(servidor).emitir(_factura(), "REF-1")
    assert error.value.mensajes == ["Factus rechazó la factura (HTTP 400)"]


def test_extraer_mensajes_limita_cantidad_largo_y_formato_detail():
    cuerpo = {"errors": {f"campo{i}": ["x" * 1000] for i in range(50)}}
    mensajes = extraer_mensajes(cuerpo)
    assert len(mensajes) == modulo.MAX_MENSAJES
    assert all(len(m) <= modulo.MAX_LARGO_MENSAJE for m in mensajes)
    detalle = {"detail": [{"loc": ["body", "customer", "email"], "msg": "field required"}]}
    assert extraer_mensajes(detalle) == ["customer.email: field required"]
    assert extraer_mensajes("texto") == []


def test_mensajes_de_rechazo_no_reflejan_secretos(servidor):
    servidor.respuestas_validar = [
        httpx.Response(422, json={"message": f"token token-acceso-1 y {CLIENT_SECRET}"})
    ]
    with pytest.raises(RechazoProveedor) as error:
        _cliente(servidor).emitir(_factura(), "REF-1")
    assert "token-acceso-1" not in str(error.value)
    assert CLIENT_SECRET not in str(error.value)


@pytest.mark.parametrize(
    "respuesta",
    [
        httpx.Response(500, json={"message": "Server Error"}),
        httpx.Response(503),
        httpx.Response(429, json={"message": "Too Many Attempts."}),
        httpx.Response(201, content=b"{no es json"),
        httpx.Response(201, json=["lista"]),
        httpx.Response(201, json={"status": "Created", "data": {"cufe": CUFE}}),
    ],
)
def test_errores_de_servidor_o_formato_son_error_de_proveedor(servidor, respuesta):
    servidor.respuestas_validar = [respuesta]
    with pytest.raises(ErrorProveedor):
        _cliente(servidor).emitir(_factura(), "REF-1")


@pytest.mark.parametrize(
    ("excepcion", "texto"),
    [
        (httpx.ReadTimeout("lento"), "Tiempo de espera"),
        (httpx.ConnectError("sin red"), "comunicación"),
    ],
)
def test_timeout_y_error_de_red_son_error_de_proveedor(excepcion, texto):
    def transporte(peticion: httpx.Request) -> httpx.Response:
        raise excepcion

    cliente = ClienteFactus(
        URL,
        CLIENT_ID,
        CLIENT_SECRET,
        USUARIO,
        CLAVE,
        None,
        5,
        http_client=httpx.Client(transport=httpx.MockTransport(transporte)),
    )
    with pytest.raises(ErrorProveedor, match=texto):
        cliente.emitir(_factura(), "REF-1")


def test_respuesta_demasiado_grande_es_error(servidor, monkeypatch):
    monkeypatch.setattr(modulo, "MAX_BYTES_RESPUESTA", 100)
    servidor.respuestas_validar = [httpx.Response(201, content=b"x" * 500)]
    with pytest.raises(ErrorProveedor, match="demasiado grande"):
        _cliente(servidor).emitir(_factura(), "REF-1")


# --------------------------------------------------------------------------- #
# Seguridad
# --------------------------------------------------------------------------- #


def test_url_http_se_rechaza():
    with pytest.raises(ValueError, match="HTTPS"):
        ClienteFactus("http://api-sandbox.factus.com.co", "a", "b", "c", "d", None, 5)


def test_cliente_propio_verifica_tls():
    cliente = ClienteFactus(URL, CLIENT_ID, CLIENT_SECRET, USUARIO, CLAVE, None, 5)
    try:
        assert cliente._http._transport._pool._ssl_context.verify_mode.name == "CERT_REQUIRED"
    finally:
        cliente.close()


def test_secretos_no_aparecen_en_repr_ni_en_logs(servidor, caplog):
    servidor.expira_en = 10
    servidor.respuestas_validar = [
        httpx.Response(401),
        httpx.Response(201, json=_respuesta_validada()),
        httpx.Response(422, json={"message": "mal"}),
        httpx.Response(500),
    ]
    servidor.respuesta_xml = httpx.Response(500)
    cliente = _cliente(servidor)
    with caplog.at_level(logging.DEBUG):
        cliente.emitir(_factura(), "REF-1")
        for _ in range(2):
            with pytest.raises((RechazoProveedor, ErrorProveedor)):
                cliente.emitir(_factura(), "REF-2")

    texto = repr(cliente) + caplog.text
    assert "ClienteFactus(" in repr(cliente)
    assert caplog.records  # sí hubo registros
    for secreto in (CLIENT_SECRET, CLAVE, "token-acceso-", "token-renovacion-"):
        assert secreto not in texto
