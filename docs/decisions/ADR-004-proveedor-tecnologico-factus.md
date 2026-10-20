# ADR-004: Modo proveedor tecnológico con Factus

## Status

Accepted

## Context

Conectarse directo a la DIAN (software propio) exige RUT como facturador electrónico,
un certificado de firma pagado y superar el set de pruebas. Para un proyecto
académico o una empresa que empieza, lo habitual en Colombia es usar un
**proveedor tecnológico** autorizado por la DIAN, que firma y transmite en nombre del
facturador. Factus ofrece una API REST con un ambiente *sandbox* gratuito.

## Decision

- Nuevo puerto `ProveedorFacturacion` (`proveedor/puertos.py`) con un adaptador
  `ClienteFactus` (`proveedor/factus.py`): OAuth2 *password grant* y `POST /v1/bills/validate`.
- `FACTURACION_MODO=directo|factus`. En `factus` el proveedor asigna número, CUFE y
  QR; la API sigue validando la entrada, calculando totales, guardando la factura,
  generando el PDF y enviando el correo.
- Si el proveedor rechaza o no responde, **no se guarda nada** (422 o 502): no hay
  numeración propia consumida, a diferencia del modo directo.
- El QR usa la URL de consulta que devuelve el proveedor (catálogo DIAN).
- `FACTUS_URL` apunta al sandbox por defecto.

## Alternatives Considered

- Reemplazar el modo directo: se pierde el valor didáctico y la independencia futura.
- Que el adaptador Factus implemente `ClienteDian`: ese puerto recibe XML ya firmado,
  pero Factus recibe datos de negocio; los contratos no encajan.

## Consequences

- Se puede probar con un sistema real de facturación sin certificado ni RUT propio.
- Los catálogos de Factus (tipos de documento, municipios, tributos) usan ids propios;
  el adaptador los traduce y debe revisarse si Factus los cambia.
- No se ha probado en vivo desde la nube porque el entorno bloquea el dominio de Factus;
  las pruebas automáticas usan respuestas simuladas.

## Security Considerations

- `FACTUS_CLIENT_SECRET` y `FACTUS_CLAVE` son `SecretStr`, nunca se registran ni se
  devuelven; el token OAuth vive solo en memoria.
- TLS siempre verificado; la URL debe ser `https`.
- Los mensajes de rechazo se filtran y acortan antes de mostrarse al cliente.

## Date

2026-10-20
