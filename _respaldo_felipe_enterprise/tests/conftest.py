from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from facturacion.configuracion import Configuracion
from facturacion.main import crear_app
from facturacion.persistencia.modelos import Rol, Usuario
from facturacion.seguridad import contrasenas

CONTRASENA = "Contraseña-Segura-2026!"


@pytest.fixture
def config(tmp_path: Path) -> Configuracion:
    return Configuracion(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'pruebas.db'}",
        directorio_datos=tmp_path,
        jwt_secreto="secreto-de-pruebas-con-longitud-suficiente-1234",
        url_publica_base="http://pruebas.local",
    )


@pytest.fixture
def cliente(config: Configuracion) -> Iterator[TestClient]:
    app = crear_app(config)
    with TestClient(app) as cliente_http:
        yield cliente_http


def crear_usuario(cliente: TestClient, email: str, rol: Rol) -> Usuario:
    contenedor = cliente.app.state.contenedor
    with contenedor.fabrica_sesiones() as sesion:
        usuario = Usuario(
            email=email,
            nombre=email.split("@")[0],
            rol=rol,
            hash_contrasena=contrasenas.generar_hash(CONTRASENA),
        )
        sesion.add(usuario)
        sesion.commit()
        return usuario


def token_para(cliente: TestClient, email: str) -> dict[str, str]:
    respuesta = cliente.post("/api/v1/auth/login", data={"username": email, "password": CONTRASENA})
    assert respuesta.status_code == 200, respuesta.text
    return {"Authorization": f"Bearer {respuesta.json()['access_token']}"}


@pytest.fixture
def auth_facturador(cliente: TestClient) -> dict[str, str]:
    crear_usuario(cliente, "facturador@example.com", Rol.FACTURADOR)
    return token_para(cliente, "facturador@example.com")


@pytest.fixture
def auth_admin(cliente: TestClient) -> dict[str, str]:
    crear_usuario(cliente, "admin@example.com", Rol.ADMINISTRADOR)
    return token_para(cliente, "admin@example.com")


def factura_valida(**cambios: object) -> dict[str, object]:
    datos: dict[str, object] = {
        "adquiriente": {
            "tipo_documento": "31",
            "numero_documento": "900123456",
            "dv": "7",
            "nombre": "Cliente Ejemplo S.A.S.",
            "email": "cliente@example.com",
            "direccion": "Carrera 7 # 71-21",
            "ciudad": "Bogotá, D.C.",
        },
        "lineas": [
            {
                "descripcion": "Servicio de consultoría",
                "cantidad": "2",
                "precio_unitario": "150000.00",
                "porcentaje_iva": "19",
                "codigo": "SRV-01",
            },
            {
                "descripcion": "Libro técnico",
                "cantidad": "1",
                "precio_unitario": "45000.50",
                "porcentaje_iva": "0",
            },
        ],
        "notas": "Gracias por su compra",
    }
    datos.update(cambios)
    return datos
