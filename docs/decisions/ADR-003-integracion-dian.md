# ADR-003: Integración con la DIAN solo en simulado y habilitación; QR verificable

## Status

Accepted

## Context

Las credenciales reales (certificado ONAC, SoftwareID, PIN, TestSetId) no están
disponibles todavía, y el proyecto no debe emitir facturas con validez tributaria
mientras está en construcción. Además se pidió un QR que "evidencie" la factura.

## Decision

- `DIAN_MODO` admite solo `simulado` (sin red, valida estructura, firma y CUFE) y
  `habilitacion` (servicio `vpfe-hab`). `TipoAmbiente` queda fijo en `2`.
  **Producción no está soportada a propósito**; habilitarla requiere un nuevo ADR.
- Con `DIAN_TEST_SET_ID` definido se usa `SendTestSetAsync` y la factura queda
  `en_proceso` hasta consultar `GetStatusZip`; sin él se usa `SendBillSync`.
- Si la DIAN no responde, la factura queda `error_envio` (número ya consumido, XML ya
  firmado) y se puede reintentar.
- En modo simulado se firma con un certificado autofirmado generado en memoria.
- El QR lleva los datos del anexo (`NumFac`, `FecFac`, …, `CUFE`) y una URL:
  `QR_URL_MODO=propia` → página `/verificar/{cufe}` (respaldada por `GET /api/v1/verificacion/{cufe}`) (funciona sin DIAN);
  `QR_URL_MODO=dian` → catálogo de habilitación de la DIAN.

## Alternatives Considered

- Permitir producción con una bandera: demasiado fácil de activar por error.
- Usar solo el catálogo DIAN en el QR: en modo simulado el enlace no mostraría nada.

## Consequences

- Todo el flujo se puede demostrar sin credenciales.
- El PDF muestra siempre la leyenda "AMBIENTE DE PRUEBAS / HABILITACIÓN - SIN VALIDEZ TRIBUTARIA".
- No se ha probado contra el servicio real de habilitación (ver `docs/03-habilitacion/`).

## Security Considerations

- La verificación pública solo expone datos del emisor y del documento, nunca del
  adquiriente; el CUFE (SHA-384) no es enumerable y se valida con regex.
- El certificado y su clave se leen de archivo/variables de entorno y nunca se registran.

## Date

2026-10-19
