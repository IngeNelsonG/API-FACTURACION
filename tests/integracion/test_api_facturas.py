from __future__ import annotations

import io
import zipfile
from decimal import Decimal

from fastapi.testclient import TestClient
from lxml import etree

from facturacion.persistencia.modelos import Rol
from tests.conftest import crear_usuario, factura_valida, token_para

NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"


def _emitir(cliente: TestClient, auth: dict[str, str], **cambios: object) -> dict:
    respuesta = cliente.post("/api/v1/facturas", json=factura_valida(**cambios), headers=auth)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def test_emitir_factura_calcula_totales_y_queda_aceptada(cliente, auth_facturador):
    factura = _emitir(cliente, auth_facturador)

    assert factura["estado"] == "aceptada"
    assert factura["numero"] == "SETP990000000"
    assert len(factura["cufe"]) == 96
    # 2 x 150.000 + 45.000,50 = 345.000,50; IVA 19% de 300.000 = 57.000
    assert Decimal(factura["total"]) == Decimal("402000.50")
    assert factura["url_verificacion"].endswith(f"/api/v1/verificacion/{factura['cufe']}")


def test_numeracion_es_consecutiva(cliente, auth_facturador):
    primera = _emitir(cliente, auth_facturador)
    segunda = _emitir(cliente, auth_facturador)
    assert primera["numero"] == "SETP990000000"
    assert segunda["numero"] == "SETP990000001"
    assert primera["cufe"] != segunda["cufe"]


def test_descargar_xml_firmado_con_cufe(cliente, auth_facturador):
    factura = _emitir(cliente, auth_facturador)
    respuesta = cliente.get(f"/api/v1/facturas/{factura['id']}/xml", headers=auth_facturador)

    assert respuesta.status_code == 200
    assert "attachment" in respuesta.headers["content-disposition"]
    documento = etree.fromstring(respuesta.content)
    assert documento.findtext(f"{{{NS_CBC}}}UUID") == factura["cufe"]
    assert documento.find(".//{http://www.w3.org/2000/09/xmldsig#}Signature") is not None


def test_descargar_pdf_y_qr(cliente, auth_facturador):
    factura = _emitir(cliente, auth_facturador)
    pdf = cliente.get(f"/api/v1/facturas/{factura['id']}/pdf", headers=auth_facturador)
    qr = cliente.get(f"/api/v1/facturas/{factura['id']}/qr", headers=auth_facturador)

    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert qr.status_code == 200
    assert qr.content.startswith(b"\x89PNG")


def test_enviar_correo_adjunta_zip_con_pdf_y_xml(cliente, auth_facturador):
    factura = _emitir(cliente, auth_facturador)
    respuesta = cliente.post(
        f"/api/v1/facturas/{factura['id']}/correo",
        json={"destinatario": "otro@example.com"},
        headers=auth_facturador,
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {"enviado_a": "otro@example.com"}
    correo = cliente.app.state.contenedor.facturacion._correo
    mensaje = correo.enviados[-1]
    adjunto = next(mensaje.iter_attachments())
    with zipfile.ZipFile(io.BytesIO(adjunto.get_content())) as archivo:
        nombres = archivo.namelist()
    assert any(nombre.endswith(".pdf") for nombre in nombres)
    assert any(nombre.endswith(".xml") for nombre in nombres)
    detalle = cliente.get(f"/api/v1/facturas/{factura['id']}", headers=auth_facturador).json()
    assert detalle["correo_enviado_en"] is not None


def test_correo_por_defecto_va_al_adquiriente(cliente, auth_facturador):
    factura = _emitir(cliente, auth_facturador)
    respuesta = cliente.post(f"/api/v1/facturas/{factura['id']}/correo", headers=auth_facturador)
    assert respuesta.json() == {"enviado_a": "cliente@example.com"}


def test_verificacion_publica_no_expone_adquiriente(cliente, auth_facturador):
    factura = _emitir(cliente, auth_facturador)
    respuesta = cliente.get(f"/api/v1/verificacion/{factura['cufe']}")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["numero"] == factura["numero"]
    assert "adquiriente_nombre" not in cuerpo
    assert "cliente@example.com" not in respuesta.text


def test_verificacion_rechaza_cufe_mal_formado(cliente):
    assert cliente.get("/api/v1/verificacion/../../etc/passwd").status_code == 404
    assert cliente.get("/api/v1/verificacion/abc").status_code == 422
    assert cliente.get(f"/api/v1/verificacion/{'a' * 96}").status_code == 404


def test_facturador_no_ve_facturas_de_otro(cliente, auth_facturador):
    factura = _emitir(cliente, auth_facturador)
    crear_usuario(cliente, "intruso@example.com", Rol.FACTURADOR)
    intruso = token_para(cliente, "intruso@example.com")

    assert cliente.get(f"/api/v1/facturas/{factura['id']}", headers=intruso).status_code == 404
    assert cliente.get(f"/api/v1/facturas/{factura['id']}/pdf", headers=intruso).status_code == 404
    assert cliente.get("/api/v1/facturas", headers=intruso).json()["total"] == 0


def test_administrador_ve_todas_las_facturas(cliente, auth_facturador, auth_admin):
    factura = _emitir(cliente, auth_facturador)
    assert cliente.get(f"/api/v1/facturas/{factura['id']}", headers=auth_admin).status_code == 200
    assert cliente.get("/api/v1/facturas", headers=auth_admin).json()["total"] == 1


def test_listado_paginado(cliente, auth_facturador):
    for _ in range(3):
        _emitir(cliente, auth_facturador)
    pagina = cliente.get("/api/v1/facturas?limite=2", headers=auth_facturador).json()
    assert pagina["total"] == 3
    assert len(pagina["elementos"]) == 2
    assert cliente.get("/api/v1/facturas?limite=1000", headers=auth_facturador).status_code == 422


def test_validaciones_de_entrada(cliente, auth_facturador):
    casos = [
        factura_valida(lineas=[]),
        factura_valida(lineas=[{"descripcion": "x", "cantidad": "0", "precio_unitario": "1"}]),
        factura_valida(lineas=[{"descripcion": "x", "cantidad": "1", "precio_unitario": "1.001"}]),
        factura_valida(
            lineas=[
                {
                    "descripcion": "x",
                    "cantidad": "1",
                    "precio_unitario": "1",
                    "porcentaje_iva": "16",
                }
            ]
        ),
        factura_valida(forma_pago="2"),  # crédito sin vencimiento
        factura_valida(campo_extra="no permitido"),
        factura_valida(
            adquiriente={
                "tipo_documento": "31",
                "numero_documento": "900123456",
                "nombre": "Sin DV",
                "email": "a@example.com",
            }
        ),
        factura_valida(
            adquiriente={
                "tipo_documento": "13",
                "numero_documento": "1'; DROP--",
                "nombre": "X",
                "email": "a@example.com",
            }
        ),
    ]
    for caso in casos:
        respuesta = cliente.post("/api/v1/facturas", json=caso, headers=auth_facturador)
        assert respuesta.status_code == 422, caso


def test_factura_inexistente(cliente, auth_facturador):
    respuesta = cliente.get("/api/v1/facturas/no-existe", headers=auth_facturador)
    assert respuesta.status_code == 404


def test_reintentar_envio_solo_con_error(cliente, auth_facturador):
    factura = _emitir(cliente, auth_facturador)
    respuesta = cliente.post(
        f"/api/v1/facturas/{factura['id']}/reintentar-envio", headers=auth_facturador
    )
    assert respuesta.status_code == 409
