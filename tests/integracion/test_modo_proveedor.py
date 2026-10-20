"""Emisión a través de un proveedor tecnológico (Factus) con un proveedor falso."""

from __future__ import annotations

from datetime import date

import pytest

from facturacion.arranque import ConfiguracionIncompleta, construir_contenedor
from facturacion.configuracion import Configuracion, ModoFacturacion
from facturacion.dominio.factura import Factura, Numeracion
from facturacion.proveedor.puertos import ErrorProveedor, RechazoProveedor, ResultadoEmision
from tests.conftest import factura_valida

CUFE = "c" * 96
URL_QR = f"https://catalogo-vpfe-hab.dian.gov.co/document/searchqr?documentkey={CUFE}"


class ProveedorFalso:
    nombre = "Factus"

    def __init__(self) -> None:
        self.error: Exception | None = None
        self.xml: bytes | None = b"<Invoice/>"
        self.recibidas: list[tuple[Factura, str]] = []

    def emitir(self, factura: Factura, referencia: str) -> ResultadoEmision:
        self.recibidas.append((factura, referencia))
        if self.error:
            raise self.error
        return ResultadoEmision(
            numeracion=Numeracion(
                "SETP",
                990000123,
                "18760000001",
                date(2019, 1, 19),
                date(2030, 1, 19),
                990000000,
                995000000,
            ),
            cufe=CUFE,
            url_qr=URL_QR,
            mensajes=["Documento validado por la DIAN"],
            xml=self.xml,
            identificador_externo="SETP990000123",
        )


@pytest.fixture
def proveedor(cliente) -> ProveedorFalso:
    falso = ProveedorFalso()
    cliente.app.state.contenedor.facturacion._proveedor = falso
    return falso


def test_emite_con_numero_cufe_y_qr_del_proveedor(cliente, auth_facturador, proveedor):
    respuesta = cliente.post("/api/v1/facturas", json=factura_valida(), headers=auth_facturador)

    assert respuesta.status_code == 201, respuesta.text
    factura = respuesta.json()
    assert factura["numero"] == "SETP990000123"
    assert factura["cufe"] == CUFE
    assert factura["estado"] == "aceptada"
    assert factura["url_verificacion"] == URL_QR
    enviada, referencia = proveedor.recibidas[0]
    assert enviada.cufe == ""
    assert referencia.startswith("API-")

    ruta = f"/api/v1/facturas/{factura['id']}"
    assert cliente.get(f"{ruta}/xml", headers=auth_facturador).content == b"<Invoice/>"
    assert cliente.get(f"{ruta}/pdf", headers=auth_facturador).content.startswith(b"%PDF")
    assert cliente.post(f"{ruta}/correo", headers=auth_facturador).status_code == 200


def test_rechazo_del_proveedor_no_guarda_la_factura(cliente, auth_facturador, proveedor):
    proveedor.error = RechazoProveedor(["El campo identificación es inválido"])
    respuesta = cliente.post("/api/v1/facturas", json=factura_valida(), headers=auth_facturador)

    assert respuesta.status_code == 422
    assert respuesta.json()["detalle"][0]["mensaje"] == "El campo identificación es inválido"
    assert cliente.get("/api/v1/facturas", headers=auth_facturador).json()["total"] == 0


def test_proveedor_caido_deja_la_referencia_para_conciliar(cliente, auth_facturador, proveedor):
    proveedor.error = ErrorProveedor("timeout")
    respuesta = cliente.post("/api/v1/facturas", json=factura_valida(), headers=auth_facturador)

    assert respuesta.status_code == 502
    assert "timeout" not in respuesta.text
    _, referencia = proveedor.recibidas[0]
    resumen = cliente.get("/api/v1/facturas", headers=auth_facturador).json()["elementos"][0]
    ruta = f"/api/v1/facturas/{resumen['id']}"
    pendiente = cliente.get(ruta, headers=auth_facturador).json()
    assert pendiente["estado"] == "error_envio"
    assert referencia in pendiente["respuesta_dian"]["descripcion"]
    # Reenviar podría duplicar una factura que el proveedor sí emitió.
    reintento = cliente.post(f"{ruta}/reintentar-envio", headers=auth_facturador)
    assert reintento.status_code == 409


def test_numero_repetido_no_pierde_la_factura_emitida(cliente, auth_facturador, proveedor):
    primera = cliente.post("/api/v1/facturas", json=factura_valida(), headers=auth_facturador)
    assert primera.status_code == 201
    proveedor.recibidas.clear()

    respuesta = cliente.post("/api/v1/facturas", json=factura_valida(), headers=auth_facturador)

    assert respuesta.status_code == 422
    assert "SETP990000123" in str(respuesta.json()["detalle"])
    listado = cliente.get("/api/v1/facturas", headers=auth_facturador).json()
    assert listado["total"] == 2
    assert {item["estado"] for item in listado["elementos"]} == {"aceptada", "error_envio"}


def test_xml_no_disponible(cliente, auth_facturador, proveedor):
    proveedor.xml = None
    factura = cliente.post(
        "/api/v1/facturas", json=factura_valida(), headers=auth_facturador
    ).json()
    respuesta = cliente.get(f"/api/v1/facturas/{factura['id']}/xml", headers=auth_facturador)
    assert respuesta.status_code == 404


def test_modo_factus_sin_credenciales_no_arranca(tmp_path):
    config = Configuracion(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
        facturacion_modo=ModoFacturacion.FACTUS,
    )
    with pytest.raises(ConfiguracionIncompleta, match="FACTUS_CLIENT_ID"):
        construir_contenedor(config)
