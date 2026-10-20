# ADR-001: Stack tecnológico y arquitectura de puertos y adaptadores

## Status

Accepted

## Context

La API debe generar XML UBL 2.1, firmarlo con XAdES-EPES, hablar SOAP 1.2 con
WS-Security con la DIAN, producir PDF con QR y enviar correos. El README inicial
pedía un lenguaje con buen soporte de XML-DSig/XAdES y SOAP. El proyecto es
académico/pequeño, pero se exige calidad de producción: seguridad, pruebas y
documentación.

## Decision

- **Python 3.12 + FastAPI** para la API REST (validación con Pydantic v2 y OpenAPI automático).
- **lxml** para el XML (parser seguro sin entidades externas) y **signxml** para XAdES-EPES.
- **Cliente SOAP propio** sobre `httpx` + `cryptography` en lugar de `zeep`: el servicio
  WCF de la DIAN exige una firma WS-Security muy específica (solo sobre `wsa:To`) que
  es más fácil de controlar y probar construyendo el sobre directamente.
- **SQLAlchemy 2 + Alembic**: SQLite en desarrollo y PostgreSQL en despliegue.
- **reportlab** (PDF) y **segno** (QR), ambas sin dependencias nativas.
- **Arquitectura de puertos y adaptadores (hexagonal ligera)**: el dominio
  (`dominio/`, `ubl/`) es código puro; DIAN, firma y correo se definen como
  protocolos (`*/puertos.py`) con un adaptador real y uno simulado. La composición
  ocurre solo en `arranque.py`.

## Alternatives Considered

- **Java + Spring + xades4j/DSS**: el soporte XAdES más maduro, pero mucho más pesado
  para el tamaño del proyecto.
- **Node.js + xml-crypto**: XAdES requiere implementar las propiedades firmadas a mano.
- **zeep** para SOAP: su soporte de WS-Security firma el Body por defecto y requiere
  `xmlsec` (dependencia nativa).
- **Microservicios**: innecesarios para un único emisor; el monolito modular permite
  separar después si hace falta.

## Consequences

- El dominio y la generación de XML se prueban sin red ni base de datos.
- Cambiar de proveedor de correo o pasar de modo simulado a habilitación es solo configuración.
- La firma XAdES depende de detalles de `signxml` (subclase `_FirmadorSignxmlDian`):
  actualizar esa librería exige correr las pruebas de firma.

## Security Considerations

- Todo XML externo se analiza con `resolve_entities=False, no_network=True` (XXE).
- `httpx` verifica TLS siempre; no hay opción para desactivarlo.
- Se audita la cadena de dependencias con `pip-audit` en CI.

## Date

2026-10-19
