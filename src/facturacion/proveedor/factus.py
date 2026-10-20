"""Adaptador REST del proveedor tecnológico Factus (API v2).

Factus asigna el número, calcula el CUFE, firma con su certificado y transmite
a la DIAN; aquí solo se traducen los datos de negocio de ``Factura`` al JSON de
``POST /v2/bills/validate`` y se interpreta la respuesta.

Contrato verificado contra https://developers.factus.com.co (octubre de 2026):

- Autenticación OAuth2 en ``POST /oauth/token`` (formulario): ``grant_type=password``
  con ``client_id``, ``client_secret``, ``username`` y ``password``; renovación con
  ``grant_type=refresh_token``. Respuesta: ``access_token``, ``refresh_token``,
  ``expires_in`` (segundos).
- En la v2 los catálogos usan **códigos** y no ids propios de Factus: el tipo de
  documento es el código DIAN (13, 31, ...), el municipio es el código DANE
  (DIVIPOLA, 5 dígitos), la unidad de medida es la de la DIAN (94 = unidad) y los
  impuestos van por ítem en ``taxes`` (``code`` 01 = IVA).
- Respuesta de validación: ``data.number``, ``data.cufe``, ``data.is_validated``,
  ``data.errors`` (reglas DIAN), ``data.numbering_range`` y ``data.links.qr``.
- XML: ``GET /v2/bills/{number}/download-xml`` con ``xml_base_64_encoded``.

Seguridad: TLS siempre verificado, URL ``https`` obligatoria; ``client_secret``,
la clave y los tokens nunca se registran ni aparecen en ``repr``; los mensajes de
rechazo se limpian y acortan antes de llegar al cliente.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import re
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, NoReturn
from urllib.parse import quote

import httpx

from facturacion.dominio.factura import (
    DOS_DECIMALES,
    Factura,
    FormaPago,
    LineaFactura,
    Numeracion,
    TipoDocumentoIdentidad,
)
from facturacion.proveedor.puertos import ErrorProveedor, RechazoProveedor, ResultadoEmision

logger = logging.getLogger(__name__)

RUTA_TOKEN = "/oauth/token"  # noqa: S105 - ruta, no secreto
RUTA_VALIDAR = "/v2/bills/validate"
RUTA_XML = "/v2/bills/{numero}/download-xml"

# --- Códigos de las tablas de referencia de Factus v2 ---
# https://developers.factus.com.co/tablas-de-referencia/tablas/
DOCUMENTO_FACTURA_VENTA = "01"
OPERACION_ESTANDAR = "10"
ORGANIZACION_JURIDICA = "1"
ORGANIZACION_NATURAL = "2"
TRIBUTO_CLIENTE_NO_APLICA = "ZZ"
IMPUESTO_IVA = "01"
ESTANDAR_CONTRIBUYENTE = "999"  # "Estándar de adopción del contribuyente"

# Tipos de documento con los que Factus permite identificar al cliente. Coinciden
# uno a uno con la lista 13.2.1 de la DIAN (``TipoDocumentoIdentidad``).
CODIGOS_DOCUMENTO_IDENTIDAD: dict[TipoDocumentoIdentidad, str] = {
    tipo: tipo.value for tipo in TipoDocumentoIdentidad
}
# Documentos de clientes del exterior: no llevan municipio colombiano.
_DOCUMENTOS_EXTRANJEROS = frozenset(
    {TipoDocumentoIdentidad.DOCUMENTO_EXTRANJERO, TipoDocumentoIdentidad.NIT_OTRO_PAIS}
)
_DOCUMENTOS_PERSONA_JURIDICA = frozenset(
    {TipoDocumentoIdentidad.NIT, TipoDocumentoIdentidad.NIT_OTRO_PAIS}
)

MAX_OBSERVACION = 500
MAX_MENSAJES = 20
MAX_LARGO_MENSAJE = 300
MAX_BYTES_RESPUESTA = 10 * 1024 * 1024
MARGEN_EXPIRACION_SEGUNDOS = 30.0
EXPIRACION_POR_DEFECTO_SEGUNDOS = 600.0

_PATRON_CUFE = re.compile(r"^[0-9a-fA-F]{96}$")
_PATRON_DANE = re.compile(r"^\d{5}$")
_PATRON_NUMERO = re.compile(r"^(?P<prefijo>\D*)(?P<numero>\d+)$")
_CARACTERES_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")
_FORMATOS_FECHA = ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y")


class _RespuestaDemasiadoGrande(Exception):
    pass


# --------------------------------------------------------------------------- #
# Construcción del JSON (funciones puras)
# --------------------------------------------------------------------------- #


def _decimal_2(valor: Decimal, campo: str) -> str:
    """``Decimal`` con exactamente 2 decimales; Factus no admite más."""
    redondeado = valor.quantize(DOS_DECIMALES)
    if redondeado != valor:
        raise ValueError(f"Factus admite máximo dos decimales en {campo}")
    return f"{redondeado:.2f}"


def _item(indice: int, linea: LineaFactura) -> dict[str, Any]:
    return {
        "code_reference": linea.codigo or f"ITEM-{indice}",
        "name": linea.descripcion,
        "quantity": _decimal_2(linea.cantidad, "la cantidad"),
        "discount_rate": "0.00",
        "price": _decimal_2(linea.precio_unitario, "el precio unitario"),  # neto, sin IVA
        "unit_measure_code": linea.unidad_medida,
        "standard_code": ESTANDAR_CONTRIBUYENTE,
        # IVA 0 % se envía como tarifa 0 (exento): el dominio no distingue "excluido".
        "taxes": [{"code": IMPUESTO_IVA, "rate": f"{linea.porcentaje_iva:.2f}"}],
    }


def _cliente(factura: Factura) -> dict[str, Any]:
    adquiriente = factura.adquiriente
    juridica = adquiriente.tipo_documento in _DOCUMENTOS_PERSONA_JURIDICA
    cliente: dict[str, Any] = {
        "identification_document_code": CODIGOS_DOCUMENTO_IDENTIDAD[adquiriente.tipo_documento],
        "identification": adquiriente.numero_documento,
        "legal_organization_code": ORGANIZACION_JURIDICA if juridica else ORGANIZACION_NATURAL,
        # El dominio no sabe si el adquiriente es responsable de IVA: "ZZ" (no aplica),
        # que es además el valor por defecto de Factus.
        "tribute_code": TRIBUTO_CLIENTE_NO_APLICA,
    }
    if juridica:
        cliente["company"] = adquiriente.nombre
        cliente["trade_name"] = adquiriente.nombre
    else:
        cliente["names"] = adquiriente.nombre
    if adquiriente.tipo_documento is TipoDocumentoIdentidad.NIT and adquiriente.dv:
        cliente["dv"] = adquiriente.dv
    for campo, valor in (
        ("address", adquiriente.direccion),
        ("email", adquiriente.email),
        ("phone", adquiriente.telefono),
    ):
        if valor:
            cliente[campo] = valor
    if adquiriente.tipo_documento not in _DOCUMENTOS_EXTRANJEROS and _PATRON_DANE.match(
        adquiriente.codigo_municipio
    ):
        cliente["municipality_code"] = adquiriente.codigo_municipio
    return cliente


def construir_payload(
    factura: Factura, referencia: str, rango_numeracion_id: int | None
) -> dict[str, Any]:
    """JSON de ``POST /v2/bills/validate``. Lanza ``ValueError`` si algo no es representable."""
    pago: dict[str, Any] = {
        "payment_form": factura.forma_pago.value,
        "payment_method_code": factura.medio_pago,
        "amount": f"{factura.totales.total_a_pagar:.2f}",
    }
    if factura.forma_pago is FormaPago.CREDITO:
        if factura.fecha_vencimiento is None:
            raise ValueError("La factura a crédito requiere fecha de vencimiento")
        pago["due_date"] = factura.fecha_vencimiento.isoformat()

    payload: dict[str, Any] = {
        "reference_code": referencia,
        "document": DOCUMENTO_FACTURA_VENTA,
        "operation_type": OPERACION_ESTANDAR,
        # La API envía su propio correo con el PDF; se evita el duplicado de Factus.
        "send_email": False,
        "payment_details": [pago],
        "cash_rounding_amount": "0.00",
        "customer": _cliente(factura),
        "items": [_item(i, linea) for i, linea in enumerate(factura.lineas, start=1)],
    }
    if rango_numeracion_id is not None:
        payload["numbering_range_id"] = rango_numeracion_id
    notas = _CARACTERES_CONTROL.sub(" ", factura.notas).strip()
    if notas:
        payload["observation"] = notas[:MAX_OBSERVACION]
    return payload


# --------------------------------------------------------------------------- #
# Interpretación de respuestas (funciones puras)
# --------------------------------------------------------------------------- #


def _limpiar(texto: str) -> str:
    texto = _CARACTERES_CONTROL.sub(" ", texto).strip()
    if len(texto) > MAX_LARGO_MENSAJE:
        texto = texto[: MAX_LARGO_MENSAJE - 1] + "…"
    return texto


def _aplanar(valor: Any, ruta: str = "") -> Iterator[str]:
    """Recorre dicts/listas de errores y produce ``"campo: mensaje"``."""
    if isinstance(valor, dict):
        for clave, hijo in valor.items():
            yield from _aplanar(hijo, f"{ruta}.{clave}" if ruta else str(clave))
    elif isinstance(valor, list):
        if valor and all(isinstance(v, dict) and "msg" in v for v in valor):
            # Formato tipo FastAPI/pydantic: [{"loc": [...], "msg": "..."}]
            for v in valor:
                loc = ".".join(str(p) for p in v.get("loc", []) if p != "body")
                yield f"{loc}: {v['msg']}" if loc else str(v["msg"])
        else:
            for hijo in valor:
                yield from _aplanar(hijo, ruta)
    elif isinstance(valor, str | int | float) and not isinstance(valor, bool):
        texto = str(valor).strip()
        if texto:
            yield f"{ruta}: {texto}" if ruta and ruta not in texto else texto


def extraer_mensajes(cuerpo: Any) -> list[str]:
    """Mensajes legibles de un cuerpo de error de Factus (``message``/``errors``/``detail``)."""
    if not isinstance(cuerpo, dict):
        return []
    crudos: list[str] = []
    if isinstance(cuerpo.get("message"), str):
        crudos.append(cuerpo["message"])
    datos = cuerpo.get("data")
    for fuente in (
        cuerpo.get("errors"),
        datos.get("errors") if isinstance(datos, dict) else None,
        cuerpo.get("detail"),
    ):
        if fuente:
            crudos.extend(_aplanar(fuente))
    mensajes: list[str] = []
    for crudo in crudos:
        mensaje = _limpiar(crudo)
        if mensaje and mensaje not in mensajes:
            mensajes.append(mensaje)
        if len(mensajes) >= MAX_MENSAJES:
            break
    return mensajes


def _fecha(valor: Any, respaldo: date) -> date:
    if isinstance(valor, str):
        texto = valor.strip()[:10]
        for formato in _FORMATOS_FECHA:
            try:
                return datetime.strptime(texto, formato).date()
            except ValueError:
                continue
    return respaldo


def _entero(valor: Any, respaldo: int) -> int:
    if isinstance(valor, bool):
        return respaldo
    if isinstance(valor, int):
        return valor
    if isinstance(valor, str) and valor.strip().isdigit():
        return int(valor.strip())
    return respaldo


def interpretar_validacion(cuerpo: Any, factura: Factura) -> ResultadoEmision:
    """Convierte la respuesta 200/201 de ``bills/validate`` en ``ResultadoEmision``.

    Respaldos cuando falta un dato no esencial: prefijo = letras iniciales del
    número; rango desde/hasta = el propio número; vigencia = fecha de emisión;
    resolución y URL del QR = cadena vacía (con advertencia en el log).
    """
    if not isinstance(cuerpo, dict) or not isinstance(cuerpo.get("data"), dict):
        raise ErrorProveedor("Respuesta de Factus sin datos de la factura")
    datos: dict[str, Any] = cuerpo["data"]
    if isinstance(datos.get("bill"), dict):  # forma de la API v1
        datos = {**datos, **datos["bill"]}

    errores_dian = datos.get("errors")
    mensajes_dian = extraer_mensajes({"errors": errores_dian}) if errores_dian else []
    if datos.get("is_validated") is False:
        rechazos = [m for m in mensajes_dian if "rechazo" in m.lower()]
        if rechazos:
            raise RechazoProveedor(rechazos)
        logger.warning("Factus creó la factura pero la DIAN aún no la valida")
        raise ErrorProveedor("La DIAN no ha validado la factura; reintente más tarde")

    numero_completo = str(datos.get("number") or "").strip()
    rango = datos.get("numbering_range") if isinstance(datos.get("numbering_range"), dict) else {}
    coincidencia = _PATRON_NUMERO.match(numero_completo)
    if coincidencia is None:
        raise ErrorProveedor("Factus devolvió un número de factura inválido")
    prefijo = rango.get("prefix") if isinstance(rango.get("prefix"), str) else None
    if prefijo is None:
        prefijo = str(datos.get("prefix") or coincidencia["prefijo"])
    if numero_completo.startswith(prefijo) and numero_completo[len(prefijo) :].isdigit():
        numero = int(numero_completo[len(prefijo) :])
    else:
        prefijo, numero = coincidencia["prefijo"], int(coincidencia["numero"])

    cufe = str(datos.get("cufe") or "").strip().lower()
    if not _PATRON_CUFE.match(cufe):
        raise ErrorProveedor("Factus devolvió un CUFE inválido")

    enlaces = datos.get("links") if isinstance(datos.get("links"), dict) else {}
    url_qr = enlaces.get("qr") or datos.get("qr") or ""
    if not isinstance(url_qr, str) or not url_qr.startswith("https://"):
        logger.warning("Factus no devolvió una URL de QR válida para %s", numero_completo)
        url_qr = ""

    resolucion = rango.get("resolution_number")
    if not resolucion:
        logger.warning("Factus no devolvió la resolución de numeración de %s", numero_completo)
    numeracion = Numeracion(
        prefijo=prefijo,
        numero=numero,
        resolucion=str(resolucion or ""),
        fecha_desde=_fecha(rango.get("start_date"), factura.fecha_emision),
        fecha_hasta=_fecha(rango.get("end_date"), factura.fecha_emision),
        rango_desde=_entero(rango.get("from"), numero),
        rango_hasta=_entero(rango.get("to"), numero),
    )
    mensajes = [_limpiar(cuerpo["message"])] if isinstance(cuerpo.get("message"), str) else []
    mensajes.extend(m for m in mensajes_dian if m not in mensajes)
    return ResultadoEmision(
        numeracion=numeracion,
        cufe=cufe,
        url_qr=url_qr,
        mensajes=[m for m in mensajes if m][:MAX_MENSAJES],
        identificador_externo=numero_completo,
    )


def interpretar_xml(cuerpo: Any) -> bytes | None:
    """XML de ``download-xml`` (``xml_base_64_encoded``), o ``None`` si no viene."""
    if not isinstance(cuerpo, dict):
        return None
    datos = cuerpo.get("data") if isinstance(cuerpo.get("data"), dict) else cuerpo
    codificado = datos.get("xml_base_64_encoded")
    if not isinstance(codificado, str) or not codificado:
        return None
    try:
        return base64.b64decode(codificado, validate=True)
    except (binascii.Error, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Cliente
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class _Token:
    acceso: str
    renovacion: str
    expira: float  # time.monotonic()


class ClienteFactus:
    """Implementación de ``ProveedorFacturacion`` contra la API REST de Factus.

    El token OAuth se guarda en memoria con su expiración y se comparte entre
    hilos (protegido con un ``Lock``); al vencer se renueva con el
    ``refresh_token`` y, si eso falla, se vuelve a iniciar sesión. Un 401 en una
    llamada fuerza un nuevo inicio de sesión y un único reintento.

    Si se inyecta ``http_client`` (p. ej. ``httpx.MockTransport`` en pruebas), el
    llamador es responsable de su configuración y de cerrarlo.
    """

    nombre = "Factus"

    def __init__(
        self,
        url: str,
        client_id: str,
        client_secret: str,
        usuario: str,
        clave: str,
        rango_numeracion_id: int | None,
        timeout: float,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not url.lower().startswith("https://"):
            raise ValueError("La URL de Factus debe usar HTTPS")
        self._url = url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._usuario = usuario
        self._clave = clave
        self._rango_numeracion_id = rango_numeracion_id
        self._timeout = timeout
        self._propio = http_client is None
        self._http = http_client or httpx.Client(timeout=timeout, verify=True)
        self._token: _Token | None = None
        self._candado = threading.Lock()

    def __repr__(self) -> str:
        return (
            f"ClienteFactus(url={self._url!r}, rango_numeracion_id={self._rango_numeracion_id!r})"
        )

    def close(self) -> None:
        if self._propio:
            self._http.close()

    def __enter__(self) -> ClienteFactus:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # --- Operación del puerto ---

    def emitir(self, factura: Factura, referencia: str) -> ResultadoEmision:
        try:
            payload = construir_payload(factura, referencia, self._rango_numeracion_id)
        except ValueError as exc:
            raise RechazoProveedor([str(exc)]) from exc

        respuesta, contenido = self._llamar_api("POST", RUTA_VALIDAR, cuerpo_json=payload)
        if respuesta.status_code in (httpx.codes.OK, httpx.codes.CREATED):
            resultado = interpretar_validacion(self._json(contenido, "validate"), factura)
            logger.info("Factus validó la factura %s", resultado.identificador_externo)
            xml = self._descargar_xml(resultado.identificador_externo)
            return ResultadoEmision(
                numeracion=resultado.numeracion,
                cufe=resultado.cufe,
                url_qr=resultado.url_qr,
                mensajes=resultado.mensajes,
                xml=xml,
                identificador_externo=resultado.identificador_externo,
            )
        if respuesta.status_code in (
            httpx.codes.BAD_REQUEST,
            httpx.codes.CONFLICT,
            httpx.codes.UNPROCESSABLE_ENTITY,
        ):
            mensajes = self._redactar(extraer_mensajes(self._json_o_none(contenido)))
            logger.info(
                "Factus rechazó la factura (HTTP %s, %d mensajes)",
                respuesta.status_code,
                len(mensajes),
            )
            raise RechazoProveedor(
                mensajes or [f"Factus rechazó la factura (HTTP {respuesta.status_code})"]
            )
        self._fallo_http(respuesta.status_code, "validate")

    # --- Descarga del XML (mejor esfuerzo) ---

    def _descargar_xml(self, numero: str) -> bytes | None:
        ruta = RUTA_XML.format(numero=quote(numero, safe=""))
        try:
            respuesta, contenido = self._llamar_api("GET", ruta)
        except ErrorProveedor:
            logger.warning("No se pudo descargar de Factus el XML de %s", numero)
            return None
        xml = None
        if respuesta.status_code == httpx.codes.OK:
            xml = interpretar_xml(self._json_o_none(contenido))
        if xml is None:
            logger.warning(
                "Factus no entregó el XML de %s (HTTP %s)", numero, respuesta.status_code
            )
        return xml

    # --- Autenticación ---

    def _token_vigente(self, *, forzar_login: bool = False) -> str:
        with self._candado:
            if forzar_login:
                self._token = None
            token = self._token
            if token is not None and time.monotonic() < token.expira:
                return token.acceso
            if token is not None and token.renovacion:
                renovado = self._pedir_token(
                    {"grant_type": "refresh_token", "refresh_token": token.renovacion},
                    tolerar_rechazo=True,
                )
                if renovado is not None:
                    self._token = renovado
                    return renovado.acceso
                logger.info("Factus no aceptó el refresh_token; se inicia sesión de nuevo")
            nuevo = self._pedir_token(
                {"grant_type": "password", "username": self._usuario, "password": self._clave}
            )
            if nuevo is None:  # no ocurre sin ``tolerar_rechazo``; defensa en profundidad
                raise ErrorProveedor("No fue posible autenticarse con Factus")
            self._token = nuevo
            return nuevo.acceso

    def _pedir_token(
        self, campos: dict[str, str], *, tolerar_rechazo: bool = False
    ) -> _Token | None:
        formulario = {
            **campos,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        concesion = campos["grant_type"]
        respuesta, contenido = self._enviar(
            "POST", RUTA_TOKEN, data=formulario, headers={"Accept": "application/json"}
        )
        if respuesta.status_code != httpx.codes.OK:
            logger.warning(
                "Factus rechazó la autenticación (%s, HTTP %s)", concesion, respuesta.status_code
            )
            if tolerar_rechazo and respuesta.status_code < 500:
                return None
            raise ErrorProveedor("No fue posible autenticarse con Factus")
        cuerpo = self._json_o_none(contenido)
        acceso = cuerpo.get("access_token") if isinstance(cuerpo, dict) else None
        if not isinstance(acceso, str) or not acceso:
            logger.warning("Respuesta de autenticación de Factus sin access_token (%s)", concesion)
            raise ErrorProveedor("No fue posible autenticarse con Factus")
        renovacion = cuerpo.get("refresh_token")
        expira_en = cuerpo.get("expires_in")
        segundos = (
            float(expira_en)
            if isinstance(expira_en, int | float) and not isinstance(expira_en, bool)
            else EXPIRACION_POR_DEFECTO_SEGUNDOS
        )
        return _Token(
            acceso=acceso,
            renovacion=renovacion if isinstance(renovacion, str) else "",
            expira=time.monotonic() + max(segundos - MARGEN_EXPIRACION_SEGUNDOS, 0.0),
        )

    # --- Transporte ---

    def _llamar_api(
        self, metodo: str, ruta: str, *, cuerpo_json: dict[str, Any] | None = None
    ) -> tuple[httpx.Response, bytes]:
        """Llamada autenticada; ante un 401 inicia sesión de nuevo y reintenta una vez."""
        for intento in range(2):
            token = self._token_vigente(forzar_login=intento > 0)
            cabeceras = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
            respuesta, contenido = self._enviar(
                metodo, ruta, cuerpo_json=cuerpo_json, headers=cabeceras
            )
            if respuesta.status_code != httpx.codes.UNAUTHORIZED:
                return respuesta, contenido
            logger.info("Factus respondió 401 en %s; se renueva la sesión", ruta)
        logger.warning("Factus sigue respondiendo 401 en %s tras renovar la sesión", ruta)
        raise ErrorProveedor("No fue posible autenticarse con Factus")

    def _enviar(
        self,
        metodo: str,
        ruta: str,
        *,
        headers: dict[str, str],
        cuerpo_json: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
    ) -> tuple[httpx.Response, bytes]:
        try:
            with self._http.stream(
                metodo,
                self._url + ruta,
                json=cuerpo_json,
                data=data,
                headers=headers,
                timeout=self._timeout,
            ) as respuesta:
                partes: list[bytes] = []
                total = 0
                for parte in respuesta.iter_bytes():
                    total += len(parte)
                    if total > MAX_BYTES_RESPUESTA:
                        raise _RespuestaDemasiadoGrande
                    partes.append(parte)
                return respuesta, b"".join(partes)
        except httpx.TimeoutException as exc:
            logger.warning("Tiempo de espera agotado en %s %s contra Factus", metodo, ruta)
            raise ErrorProveedor("Tiempo de espera agotado al comunicarse con Factus") from exc
        except httpx.HTTPError as exc:
            logger.warning(
                "Error de transporte en %s %s contra Factus: %s", metodo, ruta, type(exc).__name__
            )
            raise ErrorProveedor("Error de comunicación con Factus") from exc
        except _RespuestaDemasiadoGrande as exc:
            logger.warning("Respuesta de Factus demasiado grande en %s %s", metodo, ruta)
            raise ErrorProveedor("Respuesta de Factus demasiado grande") from exc

    @staticmethod
    def _json_o_none(contenido: bytes) -> Any:
        try:
            return json.loads(contenido)
        except (ValueError, UnicodeDecodeError):
            return None

    def _json(self, contenido: bytes, operacion: str) -> Any:
        cuerpo = self._json_o_none(contenido)
        if cuerpo is None:
            logger.warning("Respuesta de Factus con JSON inválido en %s", operacion)
            raise ErrorProveedor("Respuesta de Factus con JSON inválido")
        return cuerpo

    def _fallo_http(self, estado: int, operacion: str) -> NoReturn:
        logger.warning("Factus respondió HTTP %s en %s", estado, operacion)
        raise ErrorProveedor(f"Factus respondió con error HTTP {estado}")

    def _redactar(self, mensajes: list[str]) -> list[str]:
        """Quita de los mensajes cualquier secreto que el servidor haya reflejado."""
        secretos = [s for s in (self._client_secret, self._clave) if s]
        if self._token is not None:
            secretos += [s for s in (self._token.acceso, self._token.renovacion) if s]
        limpios = []
        for mensaje in mensajes:
            for secreto in secretos:
                mensaje = mensaje.replace(secreto, "***")
            limpios.append(mensaje)
        return limpios
