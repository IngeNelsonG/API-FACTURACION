"""Pruebas de los adaptadores de correo (simulado y SMTP con un servidor falso)."""

from __future__ import annotations

import email
import smtplib
import ssl
from email import policy
from pathlib import Path
from typing import ClassVar

import pytest

from facturacion.correo import smtp as modulo_smtp
from facturacion.correo.mensaje import TAMANO_MAXIMO_ADJUNTOS, construir_mensaje
from facturacion.correo.puertos import Adjunto, ErrorCorreo, MensajeCorreo
from facturacion.correo.simulado import ServicioCorreoSimulado
from facturacion.correo.smtp import ServicioCorreoSmtp

REMITENTE = "facturacion@example.com"


def _mensaje(destinatario: str = "cliente@example.com", **cambios) -> MensajeCorreo:
    datos = {
        "destinatario": destinatario,
        "asunto": "Factura SETP990000001",
        "cuerpo_texto": "Adjuntamos su factura electrónica.",
        "adjuntos": [
            Adjunto("SETP990000001.pdf", b"%PDF-1.4 contenido", "application/pdf"),
            Adjunto("SETP990000001.xml", b"<Invoice/>", "application/xml"),
        ],
    }
    datos.update(cambios)
    return MensajeCorreo(**datos)


def test_simulado_escribe_eml_con_adjuntos(tmp_path: Path) -> None:
    directorio = tmp_path / "correos"
    servicio = ServicioCorreoSimulado(directorio, REMITENTE)
    servicio.enviar(_mensaje())

    archivos = list(directorio.glob("*.eml"))
    assert len(archivos) == 1
    assert len(servicio.enviados) == 1
    leido = email.message_from_bytes(archivos[0].read_bytes(), policy=policy.default)
    assert leido["To"] == "cliente@example.com"
    assert leido["From"] == REMITENTE
    assert leido["Message-ID"]
    assert leido["Date"]
    adjuntos = {parte.get_filename(): parte for parte in leido.iter_attachments()}
    assert set(adjuntos) == {"SETP990000001.pdf", "SETP990000001.xml"}
    assert adjuntos["SETP990000001.pdf"].get_content_type() == "application/pdf"
    assert adjuntos["SETP990000001.pdf"].get_content() == b"%PDF-1.4 contenido"


@pytest.mark.parametrize(
    "destinatario",
    ["a@b.com\r\nBcc: x@y.com", "a@b.com\nBcc: x@y.com", "no-es-correo", "a@", ""],
)
def test_rechaza_destinatario_invalido(tmp_path: Path, destinatario: str) -> None:
    servicio = ServicioCorreoSimulado(tmp_path, REMITENTE)
    with pytest.raises(ErrorCorreo):
        servicio.enviar(_mensaje(destinatario))
    assert servicio.enviados == []
    assert list(tmp_path.iterdir()) == []


def test_rechaza_remitente_invalido(tmp_path: Path) -> None:
    servicio = ServicioCorreoSimulado(tmp_path, "x@example.com\r\nBcc: y@example.com")
    with pytest.raises(ErrorCorreo):
        servicio.enviar(_mensaje())


def test_rechaza_salto_de_linea_en_asunto() -> None:
    with pytest.raises(ErrorCorreo):
        construir_mensaje(_mensaje(asunto="Hola\r\nBcc: x@y.com"), REMITENTE)


def test_rechaza_adjuntos_demasiado_grandes() -> None:
    grande = Adjunto("grande.bin", b"0" * (TAMANO_MAXIMO_ADJUNTOS + 1), "application/octet-stream")
    with pytest.raises(ErrorCorreo):
        construir_mensaje(_mensaje(adjuntos=[grande]), REMITENTE)


def test_rechaza_tipo_mime_invalido() -> None:
    with pytest.raises(ErrorCorreo):
        construir_mensaje(_mensaje(adjuntos=[Adjunto("a.pdf", b"x", "pdf")]), REMITENTE)


class _SmtpFalso:
    """Registra las llamadas que haría ``smtplib`` sin abrir conexiones."""

    instancias: ClassVar[list[_SmtpFalso]] = []
    fallar_con: ClassVar[Exception | None] = None

    def __init__(self, host: str, puerto: int, timeout: float, context=None) -> None:
        self.host = host
        self.puerto = puerto
        self.timeout = timeout
        self.context = context
        self.llamadas: list[tuple] = []
        _SmtpFalso.instancias.append(self)

    def __enter__(self) -> _SmtpFalso:
        return self

    def __exit__(self, *args: object) -> None:
        self.llamadas.append(("quit",))

    def starttls(self, context=None) -> None:
        self.llamadas.append(("starttls", context))

    def login(self, usuario: str, clave: str) -> None:
        self.llamadas.append(("login", usuario, clave))

    def send_message(self, mensaje) -> None:
        if _SmtpFalso.fallar_con is not None:
            raise _SmtpFalso.fallar_con
        self.llamadas.append(("send_message", mensaje))


@pytest.fixture
def smtp_falso(monkeypatch: pytest.MonkeyPatch) -> type[_SmtpFalso]:
    _SmtpFalso.instancias = []
    _SmtpFalso.fallar_con = None
    monkeypatch.setattr(modulo_smtp.smtplib, "SMTP", _SmtpFalso)
    monkeypatch.setattr(modulo_smtp.smtplib, "SMTP_SSL", _SmtpFalso)
    return _SmtpFalso


def _servicio(**cambios) -> ServicioCorreoSmtp:
    datos = {
        "host": "smtp.example.com",
        "puerto": 587,
        "usuario": "usuario",
        "clave": "clave-secreta",
        "remitente": REMITENTE,
        "usar_starttls": True,
        "usar_ssl": False,
        "timeout": 5.0,
    }
    datos.update(cambios)
    return ServicioCorreoSmtp(**datos)


def test_smtp_starttls_login_y_envio(smtp_falso: type[_SmtpFalso]) -> None:
    _servicio().enviar(_mensaje())
    (conexion,) = smtp_falso.instancias
    assert (conexion.host, conexion.puerto, conexion.timeout) == ("smtp.example.com", 587, 5.0)
    nombres = [llamada[0] for llamada in conexion.llamadas]
    assert nombres == ["starttls", "login", "send_message", "quit"]
    assert isinstance(conexion.llamadas[0][1], ssl.SSLContext)
    assert conexion.llamadas[0][1].verify_mode == ssl.CERT_REQUIRED
    assert conexion.llamadas[1] == ("login", "usuario", "clave-secreta")
    assert conexion.llamadas[2][1]["To"] == "cliente@example.com"


def test_smtp_sin_usuario_no_hace_login(smtp_falso: type[_SmtpFalso]) -> None:
    _servicio(usuario="", clave="").enviar(_mensaje())
    nombres = [llamada[0] for llamada in smtp_falso.instancias[0].llamadas]
    assert "login" not in nombres
    assert "send_message" in nombres


def test_smtp_ssl_implicito(smtp_falso: type[_SmtpFalso]) -> None:
    _servicio(puerto=465, usar_starttls=False, usar_ssl=True).enviar(_mensaje())
    (conexion,) = smtp_falso.instancias
    assert isinstance(conexion.context, ssl.SSLContext)
    assert conexion.context.check_hostname is True
    assert "starttls" not in [llamada[0] for llamada in conexion.llamadas]


@pytest.mark.parametrize(
    "error",
    [smtplib.SMTPException("fallo"), smtplib.SMTPAuthenticationError(535, b"no"), OSError("red")],
)
def test_smtp_traduce_errores(
    smtp_falso: type[_SmtpFalso], error: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    smtp_falso.fallar_con = error
    with pytest.raises(ErrorCorreo, match="No fue posible enviar el correo"):
        _servicio().enviar(_mensaje())
    assert "clave-secreta" not in caplog.text


def test_smtp_valida_antes_de_conectar(smtp_falso: type[_SmtpFalso]) -> None:
    with pytest.raises(ErrorCorreo):
        _servicio().enviar(_mensaje("a@b.com\r\nBcc: x@y.com"))
    assert smtp_falso.instancias == []


def test_smtp_ssl_y_starttls_son_excluyentes() -> None:
    with pytest.raises(ValueError):
        _servicio(usar_ssl=True, usar_starttls=True)
