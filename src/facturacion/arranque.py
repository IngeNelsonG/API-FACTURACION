"""Composición de la aplicación: elige los adaptadores según la configuración."""

from __future__ import annotations

import logging

from facturacion.api.dependencias import Contenedor
from facturacion.configuracion import (
    Configuracion,
    Entorno,
    ModoCorreo,
    ModoDian,
    ModoFacturacion,
)
from facturacion.correo.puertos import ServicioCorreo
from facturacion.correo.simulado import ServicioCorreoSimulado
from facturacion.correo.smtp import ServicioCorreoSmtp
from facturacion.dian.puertos import ClienteDian
from facturacion.dian.simulado import ClienteDianSimulado
from facturacion.dian.soap import ClienteDianSoap
from facturacion.firma.xades import FirmadorXades
from facturacion.persistencia.base_datos import Base, crear_fabrica_sesiones, crear_motor
from facturacion.proveedor.factus import ClienteFactus
from facturacion.proveedor.puertos import ProveedorFacturacion
from facturacion.seguridad.limitador import LimitadorIntentos
from facturacion.servicios.facturacion import ServicioFacturacion

registro_log = logging.getLogger(__name__)


class ConfiguracionIncompleta(RuntimeError):
    pass


def _firmador(config: Configuracion) -> FirmadorXades:
    if config.dian_certificado_ruta is not None:
        return FirmadorXades.desde_pkcs12(
            config.dian_certificado_ruta, config.dian_certificado_clave.get_secret_value()
        )
    if config.dian_modo is ModoDian.HABILITACION:
        raise ConfiguracionIncompleta("Falta DIAN_CERTIFICADO_RUTA")
    registro_log.warning("Usando certificado autofirmado de desarrollo (no válido ante la DIAN)")
    return FirmadorXades.autofirmado_para_desarrollo()


def _cliente_dian(config: Configuracion, firmador: FirmadorXades) -> ClienteDian:
    if config.dian_modo is ModoDian.SIMULADO:
        return ClienteDianSimulado()
    faltantes = config.faltantes_para_habilitacion()
    # TestSetId solo es obligatorio mientras se ejecuta el set de pruebas.
    faltantes = [variable for variable in faltantes if variable != "DIAN_TEST_SET_ID"]
    if faltantes:
        raise ConfiguracionIncompleta(f"Faltan variables para habilitación: {', '.join(faltantes)}")
    return ClienteDianSoap(
        url=config.dian_url,
        firmador_ws=firmador,
        test_set_id=config.dian_test_set_id,
        timeout=config.dian_timeout_segundos,
    )


def _correo(config: Configuracion) -> ServicioCorreo:
    if config.correo_modo is ModoCorreo.SIMULADO:
        return ServicioCorreoSimulado(config.directorio_datos / "correos", config.correo_remitente)
    return ServicioCorreoSmtp(
        host=config.smtp_host,
        puerto=config.smtp_puerto,
        usuario=config.smtp_usuario,
        clave=config.smtp_clave.get_secret_value(),
        remitente=config.correo_remitente,
        usar_starttls=config.smtp_starttls,
        usar_ssl=config.smtp_ssl,
        timeout=config.smtp_timeout_segundos,
    )


def _proveedor(config: Configuracion) -> ProveedorFacturacion | None:
    if config.facturacion_modo is ModoFacturacion.DIRECTO:
        return None
    faltantes = config.faltantes_para_factus()
    if faltantes:
        raise ConfiguracionIncompleta(f"Faltan variables para Factus: {', '.join(faltantes)}")
    return ClienteFactus(
        url=config.factus_url,
        client_id=config.factus_client_id,
        client_secret=config.factus_client_secret.get_secret_value(),
        usuario=config.factus_usuario,
        clave=config.factus_clave.get_secret_value(),
        rango_numeracion_id=config.factus_rango_numeracion_id,
        timeout=config.factus_timeout_segundos,
    )


def construir_contenedor(config: Configuracion) -> Contenedor:
    motor = crear_motor(config.database_url)
    if config.entorno is not Entorno.PRODUCCION:
        # En producción el esquema se gestiona solo con migraciones (alembic upgrade head).
        if config.database_url.startswith("sqlite:///./"):
            config.directorio_datos.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(motor)
    firmador = _firmador(config)
    servicio = ServicioFacturacion(
        config, firmador, _cliente_dian(config, firmador), _correo(config), _proveedor(config)
    )
    return Contenedor(
        config=config,
        fabrica_sesiones=crear_fabrica_sesiones(motor),
        facturacion=servicio,
        limitador_login=LimitadorIntentos(config.login_max_intentos, config.login_ventana_segundos),
    )
