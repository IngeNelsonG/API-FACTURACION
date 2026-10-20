from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt

from facturacion.persistencia.modelos import Rol
from tests.conftest import CONTRASENA, crear_usuario, token_para

RUTA_LOGIN = "/api/v1/auth/login"


def test_rutas_protegidas_exigen_token(cliente):
    for metodo, ruta in [
        ("get", "/api/v1/facturas"),
        ("post", "/api/v1/facturas"),
        ("get", "/api/v1/auth/yo"),
    ]:
        respuesta = getattr(cliente, metodo)(ruta)
        assert respuesta.status_code == 401
        assert respuesta.headers["www-authenticate"] == "Bearer"


def test_login_correcto_y_perfil(cliente):
    crear_usuario(cliente, "ana@example.com", Rol.FACTURADOR)
    auth = token_para(cliente, "ANA@example.com")
    perfil = cliente.get("/api/v1/auth/yo", headers=auth).json()
    assert perfil["email"] == "ana@example.com"
    assert perfil["rol"] == "facturador"
    assert "hash_contrasena" not in perfil


def test_login_fallido_no_revela_si_el_usuario_existe(cliente):
    crear_usuario(cliente, "ana@example.com", Rol.FACTURADOR)
    clave_mala = cliente.post(RUTA_LOGIN, data={"username": "ana@example.com", "password": "x"})
    inexistente = cliente.post(
        RUTA_LOGIN, data={"username": "nadie@example.com", "password": CONTRASENA}
    )
    assert clave_mala.status_code == inexistente.status_code == 401
    assert clave_mala.json() == inexistente.json()


def test_login_bloquea_por_fuerza_bruta(cliente, config):
    crear_usuario(cliente, "ana@example.com", Rol.FACTURADOR)
    for _ in range(config.login_max_intentos):
        cliente.post(RUTA_LOGIN, data={"username": "ana@example.com", "password": "mala"})
    bloqueado = cliente.post(
        RUTA_LOGIN, data={"username": "ana@example.com", "password": CONTRASENA}
    )
    assert bloqueado.status_code == 429
    assert "retry-after" in bloqueado.headers


def test_login_bloquea_rociado_de_contrasenas_por_ip(cliente, config):
    for indice in range(config.login_max_intentos_ip):
        cliente.post(RUTA_LOGIN, data={"username": f"u{indice}@example.com", "password": "mala"})
    crear_usuario(cliente, "ana@example.com", Rol.FACTURADOR)
    bloqueado = cliente.post(
        RUTA_LOGIN, data={"username": "ana@example.com", "password": CONTRASENA}
    )
    assert bloqueado.status_code == 429


def _token(config, **cambios):
    ahora = datetime.now(UTC)
    reclamos = {
        "sub": "x",
        "rol": "administrador",
        "iss": config.jwt_emisor,
        "aud": config.jwt_audiencia,
        "iat": ahora,
        "nbf": ahora,
        "exp": ahora + timedelta(minutes=5),
        "jti": "1",
    }
    reclamos.update(cambios)
    return reclamos


def test_rechaza_tokens_manipulados(cliente, config):
    usuario = crear_usuario(cliente, "ana@example.com", Rol.FACTURADOR)
    secreto = config.jwt_secreto.get_secret_value()
    invalidos = [
        jwt.encode(
            _token(config, sub=usuario.id),
            "otro-secreto-de-longitud-suficiente-xx",
            algorithm="HS256",
        ),
        jwt.encode(_token(config, sub=usuario.id), None, algorithm="none"),
        jwt.encode(
            _token(config, sub=usuario.id, exp=datetime.now(UTC) - timedelta(minutes=10)),
            secreto,
            algorithm="HS256",
        ),
        jwt.encode(
            _token(config, sub=usuario.id, aud="otra-audiencia"), secreto, algorithm="HS256"
        ),
        jwt.encode(_token(config, sub="usuario-inexistente"), secreto, algorithm="HS256"),
        "no-es-un-jwt",
    ]
    for token in invalidos:
        respuesta = cliente.get("/api/v1/auth/yo", headers={"Authorization": f"Bearer {token}"})
        assert respuesta.status_code == 401, token


def test_el_rol_se_toma_de_la_base_de_datos(cliente, config):
    usuario = crear_usuario(cliente, "ana@example.com", Rol.FACTURADOR)
    # Un token que dice "administrador" no eleva privilegios.
    token = jwt.encode(
        _token(config, sub=usuario.id), config.jwt_secreto.get_secret_value(), algorithm="HS256"
    )
    auth = {"Authorization": f"Bearer {token}"}
    respuesta = cliente.post(
        "/api/v1/auth/registro",
        json={"email": "nuevo@example.com", "nombre": "N", "contrasena": CONTRASENA},
        headers=auth,
    )
    assert respuesta.status_code == 403


def test_registro_requiere_administrador(cliente, auth_admin):
    nuevo = {"email": "nuevo@example.com", "nombre": "Nuevo", "contrasena": CONTRASENA}
    assert cliente.post("/api/v1/auth/registro", json=nuevo).status_code == 403

    creado = cliente.post("/api/v1/auth/registro", json=nuevo, headers=auth_admin)
    assert creado.status_code == 201
    assert creado.json()["rol"] == "facturador"
    duplicado = cliente.post("/api/v1/auth/registro", json=nuevo, headers=auth_admin)
    assert duplicado.status_code == 409


def test_registro_aplica_politica_de_contrasenas(cliente, auth_admin):
    for clave in ["corta", "aaaaaaaaaaaaaaaa", " " + CONTRASENA]:
        respuesta = cliente.post(
            "/api/v1/auth/registro",
            json={"email": "n@example.com", "nombre": "N", "contrasena": clave},
            headers=auth_admin,
        )
        assert respuesta.status_code == 422
        assert clave not in respuesta.text


def test_registro_rechaza_asignacion_masiva(cliente, auth_admin):
    respuesta = cliente.post(
        "/api/v1/auth/registro",
        json={
            "email": "n@example.com",
            "nombre": "N",
            "contrasena": CONTRASENA,
            "activo": False,
            "hash_contrasena": "x",
        },
        headers=auth_admin,
    )
    assert respuesta.status_code == 422


def test_cabeceras_de_seguridad(cliente):
    respuesta = cliente.get("/salud")
    assert respuesta.status_code == 200
    assert respuesta.headers["x-content-type-options"] == "nosniff"
    assert respuesta.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in respuesta.headers["content-security-policy"]
    assert respuesta.headers["cache-control"] == "no-store"


def test_cuerpo_demasiado_grande(cliente, auth_facturador):
    respuesta = cliente.post(
        "/api/v1/facturas",
        content=b"x" * (1024 * 1024 + 1),
        headers={**auth_facturador, "Content-Type": "application/json"},
    )
    assert respuesta.status_code == 413


def test_cuerpo_grande_sin_content_length(cliente, auth_facturador):
    def trozos():
        for _ in range(3):
            yield b"x" * (1024 * 1024)

    respuesta = cliente.post(
        "/api/v1/facturas",
        content=trozos(),
        headers={**auth_facturador, "Content-Type": "application/json"},
    )
    assert respuesta.status_code == 413
    assert respuesta.headers["x-content-type-options"] == "nosniff"
