# Trabajo pendiente

## Required (antes de habilitación real)
- Descargar XSD del Anexo 1.9 a `recursos/xsd/` y validar el XML generado en los tests.
- Probar contra `vpfe-hab` con credenciales reales; ajustar firma XAdES / WS-Security según respuestas.
- Probar `FACTURACION_MODO=factus` en vivo contra el sandbox (nunca probado; credenciales por solicitar a Factus).

## Recommended
- `AttachedDocument` para el correo al adquiriente (hoy: XML firmado + ApplicationResponse sueltos).
- Notas crédito/débito (CUDE con PIN) y eventos RADIAN.
- Limitador de login en Redis para varias réplicas; refresh tokens / revocación de JWT.
- Logs estructurados JSON y trazas (OpenTelemetry).
- Reintento programado de facturas `error_envio` y consulta periódica de `en_proceso`.
- Antes de `reintentar-envio` en modo directo, consultar `GetStatus` por CUFE (evita
  "documento procesado anteriormente" tras un timeout).
- Conciliación automática de facturas Factus en `error_envio` por `reference_code`.

## Optional
- Varios emisores (multi-tenant).
- INC/ICA y otros tributos (hoy solo IVA 0/5/19 %).
