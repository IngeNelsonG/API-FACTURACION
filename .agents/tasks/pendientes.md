# Trabajo pendiente

## Required (antes de habilitación real)
- Descargar XSD del Anexo 1.9 a `recursos/xsd/` y validar el XML generado en los tests.
- Probar contra `vpfe-hab` con credenciales reales; ajustar firma XAdES / WS-Security según respuestas.

## Recommended
- `AttachedDocument` para el correo al adquiriente (hoy: XML firmado + ApplicationResponse sueltos).
- Notas crédito/débito (CUDE con PIN) y eventos RADIAN.
- Limitador de login en Redis para varias réplicas; refresh tokens / revocación de JWT.
- Logs estructurados JSON y trazas (OpenTelemetry).
- Reintento programado de facturas `error_envio` y consulta periódica de `en_proceso`.

## Optional
- Varios emisores (multi-tenant).
- INC/ICA y otros tributos (hoy solo IVA 0/5/19 %).
