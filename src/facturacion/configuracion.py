"""Configuración de la aplicación leída desde variables de entorno (12-factor).

Ningún secreto tiene valor por defecto utilizable fuera de desarrollo: en
``ENTORNO=produccion`` la aplicación se niega a arrancar si faltan.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

URL_HABILITACION_DIAN = "https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc"
URL_CATALOGO_HABILITACION = "https://catalogo-vpfe-hab.dian.gov.co/document/searchqr?documentkey="
URL_SANDBOX_FACTUS = "https://api-sandbox.factus.com.co"

# Valor de desarrollo explícitamente inseguro: se rechaza en producción.
_SECRETO_DESARROLLO = "desarrollo-inseguro-cambiar-este-secreto-jwt-0000"


class Entorno(StrEnum):
    DESARROLLO = "desarrollo"
    PRUEBAS = "pruebas"
    PRODUCCION = "produccion"


class ModoDian(StrEnum):
    """``simulado`` no sale a internet; ``habilitacion`` usa el ambiente de pruebas DIAN.

    El ambiente de producción de la DIAN no está soportado a propósito
    (ver ``docs/decisions/ADR-003-integracion-dian.md``).
    """

    SIMULADO = "simulado"
    HABILITACION = "habilitacion"


class ModoCorreo(StrEnum):
    SIMULADO = "simulado"
    SMTP = "smtp"


class ModoFacturacion(StrEnum):
    """``directo``: la API firma y transmite a la DIAN (software propio).

    ``factus``: delega numeración, CUFE, firma y transmisión a Factus
    (proveedor tecnológico; ver ADR-004).
    """

    DIRECTO = "directo"
    FACTUS = "factus"


class ModoUrlQr(StrEnum):
    """A dónde apunta la URL del QR: catálogo DIAN o verificación propia de la API."""

    DIAN = "dian"
    PROPIA = "propia"


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    entorno: Entorno = Entorno.DESARROLLO
    database_url: str = "sqlite:///./var/facturacion.db"
    directorio_datos: Path = Path("var")
    url_publica_base: str = "http://localhost:8000"
    # NoDecode: se acepta una lista separada por comas en lugar de JSON.
    cors_origenes: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # --- Autenticación ---
    jwt_secreto: SecretStr = SecretStr(_SECRETO_DESARROLLO)
    jwt_emisor: str = "api-facturacion"
    jwt_audiencia: str = "api-facturacion-clientes"
    jwt_minutos_expiracion: int = Field(default=30, ge=1, le=24 * 60)
    login_max_intentos: int = Field(default=5, ge=1)
    login_max_intentos_ip: int = Field(default=30, ge=1)
    login_ventana_segundos: int = Field(default=300, ge=1)
    registro_publico: bool = False

    # --- DIAN ---
    dian_modo: ModoDian = ModoDian.SIMULADO
    dian_url: str = URL_HABILITACION_DIAN
    dian_timeout_segundos: float = Field(default=60, gt=0)
    dian_software_id: str = "00000000-0000-0000-0000-000000000000"
    dian_pin: SecretStr = SecretStr("00000")
    dian_test_set_id: str = ""
    dian_certificado_ruta: Path | None = None
    dian_certificado_clave: SecretStr = SecretStr("")

    # --- Emisor (debe coincidir exactamente con el RUT) ---
    emisor_nit: str = "900000000"
    emisor_dv: str = "0"
    emisor_razon_social: str = "EMPRESA DE PRUEBAS S.A.S."
    emisor_nombre_comercial: str = "EMPRESA DE PRUEBAS"
    emisor_tipo_organizacion: str = Field(default="1", pattern=r"^[12]$")
    emisor_responsabilidades: str = "R-99-PN"
    emisor_direccion: str = "CALLE 1 # 1-1"
    emisor_ciudad: str = "Bogotá, D.C."
    emisor_codigo_municipio: str = "11001"
    emisor_departamento: str = "Bogotá"
    emisor_codigo_departamento: str = "11"
    emisor_email: str = "facturacion@example.com"
    emisor_telefono: str = "6010000000"

    # --- Numeración (por defecto: rango de pruebas típico de habilitación) ---
    numeracion_prefijo: str = Field(default="SETP", pattern=r"^[A-Z0-9]{0,4}$")
    numeracion_desde: int = Field(default=990000000, ge=0)
    numeracion_hasta: int = Field(default=995000000, ge=0)
    numeracion_resolucion: str = "18760000001"
    numeracion_fecha_desde: date = date(2019, 1, 19)
    numeracion_fecha_hasta: date = date(2030, 1, 19)
    numeracion_clave_tecnica: SecretStr = SecretStr("fc8eac422eba16e22ffd8c6f94b3f40a6e38162c")

    # --- Correo ---
    correo_modo: ModoCorreo = ModoCorreo.SIMULADO
    correo_remitente: str = "facturacion@example.com"
    smtp_host: str = "localhost"
    smtp_puerto: int = Field(default=587, ge=1, le=65535)
    smtp_usuario: str = ""
    smtp_clave: SecretStr = SecretStr("")
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    smtp_timeout_segundos: float = Field(default=30, gt=0)

    # --- Proveedor tecnológico (Factus) ---
    facturacion_modo: ModoFacturacion = ModoFacturacion.DIRECTO
    factus_url: str = URL_SANDBOX_FACTUS
    factus_client_id: str = ""
    factus_client_secret: SecretStr = SecretStr("")
    factus_usuario: str = ""
    factus_clave: SecretStr = SecretStr("")
    factus_rango_numeracion_id: int | None = Field(default=None, ge=1)
    factus_timeout_segundos: float = Field(default=60, gt=0)

    # --- QR ---
    qr_url_modo: ModoUrlQr = ModoUrlQr.PROPIA

    @field_validator("cors_origenes", mode="before")
    @classmethod
    def _separar_origenes(cls, valor: object) -> object:
        if isinstance(valor, str):
            return [origen.strip() for origen in valor.split(",") if origen.strip()]
        return valor

    @model_validator(mode="after")
    def _validar_coherencia(self) -> Configuracion:
        if self.numeracion_desde > self.numeracion_hasta:
            raise ValueError("NUMERACION_DESDE no puede ser mayor que NUMERACION_HASTA")
        if self.smtp_ssl and self.smtp_starttls:
            raise ValueError("SMTP_SSL y SMTP_STARTTLS son excluyentes")
        if self.smtp_usuario and not (self.smtp_ssl or self.smtp_starttls):
            # Sin TLS, la clave SMTP viajaría en texto plano.
            raise ValueError("SMTP con usuario y clave requiere SMTP_SSL o SMTP_STARTTLS")
        if self.entorno is Entorno.PRODUCCION:
            secreto = self.jwt_secreto.get_secret_value()
            # También se rechaza el marcador de .env.example ("CAMBIAR-...").
            if secreto == _SECRETO_DESARROLLO or secreto.startswith("CAMBIAR") or len(secreto) < 32:
                raise ValueError("JWT_SECRETO debe definirse con al menos 32 caracteres")
            if "*" in self.cors_origenes:
                raise ValueError("CORS_ORIGENES no puede contener '*' en producción")
        elif len(self.jwt_secreto.get_secret_value()) < 32:
            raise ValueError("JWT_SECRETO debe tener al menos 32 caracteres")
        return self

    @property
    def tipo_ambiente_dian(self) -> str:
        """Código ``TipoAmbiente`` del anexo técnico: 1 producción, 2 pruebas."""
        return "2"

    def faltantes_para_factus(self) -> list[str]:
        faltantes = []
        if not self.factus_client_id:
            faltantes.append("FACTUS_CLIENT_ID")
        if not self.factus_client_secret.get_secret_value():
            faltantes.append("FACTUS_CLIENT_SECRET")
        if not self.factus_usuario:
            faltantes.append("FACTUS_USUARIO")
        if not self.factus_clave.get_secret_value():
            faltantes.append("FACTUS_CLAVE")
        return faltantes

    def faltantes_para_habilitacion(self) -> list[str]:
        """Variables obligatorias para hablar con el ambiente de habilitación de la DIAN."""
        faltantes: list[str] = []
        if self.dian_software_id == "00000000-0000-0000-0000-000000000000":
            faltantes.append("DIAN_SOFTWARE_ID")
        if self.dian_pin.get_secret_value() in ("", "00000"):
            faltantes.append("DIAN_PIN")
        if not self.dian_test_set_id:
            faltantes.append("DIAN_TEST_SET_ID")
        if self.dian_certificado_ruta is None or not self.dian_certificado_ruta.is_file():
            faltantes.append("DIAN_CERTIFICADO_RUTA")
        if not self.dian_certificado_clave.get_secret_value():
            faltantes.append("DIAN_CERTIFICADO_CLAVE")
        return faltantes


@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()
