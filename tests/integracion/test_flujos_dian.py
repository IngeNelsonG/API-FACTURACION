"""Flujos con la DIAN: caída del servicio, set de pruebas asíncrono y rechazo."""

from __future__ import annotations

import pytest

from facturacion.arranque import ConfiguracionIncompleta, construir_contenedor
from facturacion.configuracion import Configuracion, ModoDian
from facturacion.dian.puertos import ErrorDian, RespuestaDian
from tests.conftest import factura_valida


class ClienteDianFalso:
    def __init__(self) -> None:
        self.caido = False
        self.respuesta_sync = RespuestaDian(True, "00", "Procesado Correctamente")
        self.respuesta_estado = RespuestaDian(
            True, "00", "Procesado Correctamente", application_response=b"<ApplicationResponse/>"
        )

    def _verificar(self) -> None:
        if self.caido:
            raise ErrorDian("sin conexión")

    def enviar_factura(self, nombre_zip: str, contenido_zip: bytes) -> RespuestaDian:
        self._verificar()
        return self.respuesta_sync

    def enviar_set_pruebas(self, nombre_zip: str, contenido_zip: bytes) -> RespuestaDian:
        self._verificar()
        return RespuestaDian(True, "RECIBIDO", "Recibido", track_id="track-123")

    def consultar_estado_zip(self, track_id: str) -> RespuestaDian:
        self._verificar()
        return self.respuesta_estado


@pytest.fixture
def dian(cliente) -> ClienteDianFalso:
    falso = ClienteDianFalso()
    cliente.app.state.contenedor.facturacion._dian = falso
    return falso


def _emitir(cliente, auth) -> dict:
    respuesta = cliente.post("/api/v1/facturas", json=factura_valida(), headers=auth)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def test_dian_caida_deja_error_envio_y_permite_reintentar(cliente, auth_facturador, dian):
    dian.caido = True
    factura = _emitir(cliente, auth_facturador)
    assert factura["estado"] == "error_envio"
    ruta = f"/api/v1/facturas/{factura['id']}"
    # No se puede enviar al adquiriente una factura no validada.
    assert cliente.post(f"{ruta}/correo", headers=auth_facturador).status_code == 409

    dian.caido = False
    reintento = cliente.post(f"{ruta}/reintentar-envio", headers=auth_facturador)
    assert reintento.status_code == 200
    assert reintento.json()["estado"] == "aceptada"


def test_rechazo_de_la_dian(cliente, auth_facturador, dian):
    dian.respuesta_sync = RespuestaDian(
        False,
        "99",
        "Validación contiene errores",
        mensajes=["Regla: FAD06, Rechazo: CUFE inválido"],
    )
    factura = _emitir(cliente, auth_facturador)
    assert factura["estado"] == "rechazada"
    assert factura["respuesta_dian"]["mensajes"] == ["Regla: FAD06, Rechazo: CUFE inválido"]


def test_set_de_pruebas_queda_en_proceso_hasta_consultar(cliente, auth_facturador, dian):
    cliente.app.state.contenedor.facturacion._config.dian_test_set_id = "set-1"
    factura = _emitir(cliente, auth_facturador)
    assert factura["estado"] == "en_proceso"
    assert factura["track_id"] == "track-123"

    ruta = f"/api/v1/facturas/{factura['id']}/consultar-estado"
    dian.caido = True
    assert cliente.post(ruta, headers=auth_facturador).status_code == 422
    dian.caido = False
    actualizada = cliente.post(ruta, headers=auth_facturador)
    assert actualizada.json()["estado"] == "aceptada"
    assert cliente.post(ruta, headers=auth_facturador).status_code == 409


def test_rango_de_numeracion_agotado(cliente, auth_facturador):
    config = cliente.app.state.contenedor.facturacion._config
    config.numeracion_hasta = config.numeracion_desde
    _emitir(cliente, auth_facturador)
    respuesta = cliente.post("/api/v1/facturas", json=factura_valida(), headers=auth_facturador)
    assert respuesta.status_code == 422
    assert "agotado" in respuesta.json()["detalle"]


def test_habilitacion_sin_credenciales_no_arranca(tmp_path):
    config = Configuracion(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
        dian_modo=ModoDian.HABILITACION,
    )
    with pytest.raises(ConfiguracionIncompleta):
        construir_contenedor(config)
