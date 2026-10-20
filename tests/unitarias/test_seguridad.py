from __future__ import annotations

import pytest

from facturacion.configuracion import Configuracion, Entorno
from facturacion.seguridad import contrasenas
from facturacion.seguridad.limitador import LimitadorIntentos
from facturacion.seguridad.tokens import TokenInvalido, emitir_token, validar_token

SECRETO = "secreto-de-pruebas-con-longitud-suficiente-1234"


def test_hash_argon2id_y_verificacion():
    hash_guardado = contrasenas.generar_hash("Una-Clave-Larga-1")
    assert hash_guardado.startswith("$argon2id$")
    assert contrasenas.verificar(hash_guardado, "Una-Clave-Larga-1")
    assert not contrasenas.verificar(hash_guardado, "otra")
    assert not contrasenas.verificar(None, "Una-Clave-Larga-1")
    assert not contrasenas.verificar("hash-corrupto", "x")
    assert not contrasenas.requiere_rehash(hash_guardado)


@pytest.mark.parametrize("clave", ["corta", "a" * 129, "aaaaaaaaaaaaaa", " espacios-al-inicio1"])
def test_politica_de_contrasenas(clave):
    with pytest.raises(ValueError):
        contrasenas.validar_politica(clave)


def test_token_ida_y_vuelta():
    config = Configuracion(_env_file=None, jwt_secreto=SECRETO)
    token, vigencia = emitir_token("u1", "facturador", config)
    datos = validar_token(token, config)
    assert datos.usuario_id == "u1"
    assert datos.rol == "facturador"
    assert vigencia == config.jwt_minutos_expiracion * 60


def test_token_con_otro_emisor_es_invalido():
    config = Configuracion(_env_file=None, jwt_secreto=SECRETO)
    otro = Configuracion(_env_file=None, jwt_secreto=SECRETO, jwt_emisor="otro")
    token, _ = emitir_token("u1", "facturador", otro)
    with pytest.raises(TokenInvalido):
        validar_token(token, config)


def test_limitador():
    limitador = LimitadorIntentos(2, 60)
    assert not limitador.bloqueado("k")
    limitador.registrar_fallo("k")
    limitador.registrar_fallo("k")
    assert limitador.bloqueado("k")
    assert not limitador.bloqueado("otra")
    limitador.reiniciar("k")
    assert not limitador.bloqueado("k")


def test_produccion_exige_secreto_jwt_propio():
    with pytest.raises(ValueError):
        Configuracion(_env_file=None, entorno=Entorno.PRODUCCION)
    with pytest.raises(ValueError):
        Configuracion(_env_file=None, jwt_secreto="corto")
    with pytest.raises(ValueError):
        Configuracion(
            _env_file=None,
            entorno=Entorno.PRODUCCION,
            jwt_secreto="CAMBIAR-por-un-secreto-aleatorio-de-al-menos-32-caracteres",
        )
    Configuracion(_env_file=None, entorno=Entorno.PRODUCCION, jwt_secreto=SECRETO)


def test_configuracion_coherente():
    with pytest.raises(ValueError):
        Configuracion(_env_file=None, numeracion_desde=10, numeracion_hasta=1)
    with pytest.raises(ValueError):
        Configuracion(_env_file=None, smtp_ssl=True, smtp_starttls=True)
    config = Configuracion(_env_file=None, cors_origenes="https://a.com, https://b.com")
    assert config.cors_origenes == ["https://a.com", "https://b.com"]
    assert "DIAN_SOFTWARE_ID" in config.faltantes_para_habilitacion()


def test_limitador_no_acumula_claves_vencidas(monkeypatch):
    reloj = [1000.0]
    monkeypatch.setattr("facturacion.seguridad.limitador.time.monotonic", lambda: reloj[0])
    limitador = LimitadorIntentos(max_intentos=2, ventana_segundos=10)
    for indice in range(100):
        assert not limitador.bloqueado(f"10.0.0.1|usuario{indice}@example.com")
    limitador.registrar_fallo("clave")
    assert len(limitador._intentos) == 1
    reloj[0] += 11
    assert not limitador.bloqueado("clave")
    assert limitador._intentos == {}


def test_smtp_con_credenciales_exige_tls():
    with pytest.raises(ValueError, match="SMTP_SSL o SMTP_STARTTLS"):
        Configuracion(
            _env_file=None, smtp_usuario="u@example.com", smtp_starttls=False, smtp_ssl=False
        )
    # Sin credenciales (p. ej. Mailpit local) se permite sin TLS.
    Configuracion(_env_file=None, smtp_starttls=False, smtp_ssl=False)
