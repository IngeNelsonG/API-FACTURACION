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
        Configuracion(_env_file=None, mail_ssl=True, mail_starttls=True)
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


def test_smtp_con_autenticacion_exige_credenciales_y_tls():
    with pytest.raises(ValueError, match="MAIL_STARTTLS o MAIL_SSL"):
        Configuracion(
            _env_file=None,
            correo_modo="smtp",
            mail_smtp_auth=True,
            mail_user="u@example.com",
            mail_password="clave-de-prueba",
            mail_starttls=False,
            mail_ssl=False,
        )
    with pytest.raises(ValueError, match="MAIL_USER y MAIL_PASSWORD"):
        Configuracion(
            _env_file=None, correo_modo="smtp", mail_smtp_auth=True, mail_user="u@example.com"
        )
    # En modo simulado no se exigen credenciales aunque MAIL_SMTP_AUTH esté activo.
    Configuracion(_env_file=None, mail_smtp_auth=True)
    # Sin autenticación (p. ej. Mailpit local) se permite sin TLS.
    Configuracion(_env_file=None, mail_starttls=False, mail_ssl=False)


def test_variables_mail_y_remitente_por_defecto(monkeypatch):
    monkeypatch.setenv("MAIL_HOST", "smtp.gmail.com")
    monkeypatch.setenv("MAIL_PORT", "587")
    monkeypatch.setenv("MAIL_USER", "cuenta@example.com")
    monkeypatch.setenv("MAIL_PASSWORD", "clave-de-prueba")
    monkeypatch.setenv("MAIL_SMTP_AUTH", "true")
    monkeypatch.setenv("MAIL_STARTTLS", "true")
    config = Configuracion(_env_file=None)
    assert (config.mail_host, config.mail_port, config.mail_smtp_auth) == (
        "smtp.gmail.com",
        587,
        True,
    )
    assert config.remitente_correo == "cuenta@example.com"


def test_logs_incluyen_el_contexto_sin_secretos():
    import logging

    from facturacion.main import FormatoConContexto

    registro = logging.makeLogRecord(
        {"msg": "login_fallido", "levelname": "WARNING", "name": "x", "ip": "1.2.3.4"}
    )
    assert FormatoConContexto("%(message)s").format(registro) == "login_fallido ip='1.2.3.4'"


@pytest.mark.parametrize(("autenticar", "usuario_esperado"), [(True, "u@example.com"), (False, "")])
def test_mail_smtp_auth_decide_si_inicia_sesion(tmp_path, autenticar, usuario_esperado):
    from facturacion.arranque import _correo
    from facturacion.configuracion import ModoCorreo

    config = Configuracion(
        _env_file=None,
        correo_modo=ModoCorreo.SMTP,
        mail_smtp_auth=autenticar,
        mail_user="u@example.com",
        mail_password="clave-de-prueba",
    )
    correo = _correo(config)
    assert correo._usuario == usuario_esperado
    assert correo._remitente == "u@example.com"
