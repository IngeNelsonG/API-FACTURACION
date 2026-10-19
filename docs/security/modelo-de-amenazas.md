# Modelo de amenazas y controles de seguridad

## Fronteras de confianza

1. **Cliente → API** (internet): toda entrada es no confiable.
2. **API → DIAN** (SOAP sobre TLS): las respuestas se analizan como XML no confiable.
3. **API → SMTP**: los destinatarios provienen del usuario.
4. **Público → `/api/v1/verificacion/{cufe}`**: sin autenticación.
5. **Secretos** (certificado, PIN, JWT, SMTP): solo en entorno/archivos fuera de git.

## STRIDE

| Amenaza | Escenario | Control |
|---|---|---|
| **S**poofing | Robo o fuerza bruta de credenciales | Argon2id; limitador por IP+correo (429); mensaje de error único; verificación señuelo contra enumeración por tiempo. |
| S | Token falsificado / `alg: none` | HS256 fijo, `iss`/`aud`/`exp`/`nbf`/`jti` obligatorios, secreto ≥ 32 caracteres. |
| **T**ampering | Modificar totales o XML | Totales calculados en el servidor; XML firmado XAdES; CUFE SHA-384. |
| T | Asignación masiva (`rol`, `activo`) | `extra="forbid"` en todos los esquemas de entrada. |
| T | Inyección SQL | Solo consultas parametrizadas de SQLAlchemy. |
| T | Inyección de marcado en el PDF | Texto del usuario escapado antes de `Paragraph`. |
| T | Inyección de cabeceras de correo | Rechazo de CR/LF y validación con `email-validator`. |
| **R**epudiation | Negar la emisión | Firma digital, `ApplicationResponse` de la DIAN guardado, logs de login y emisión. |
| **I**nformation disclosure | IDOR entre facturadores | Consultas filtradas por dueño; 404 para recursos ajenos. |
| I | Datos personales en la verificación pública | Solo datos del emisor y del documento. |
| I | Trazas internas / eco de contraseñas | Manejador genérico 500; errores 422 sin el valor recibido. |
| I | Secretos en repositorio o logs | `.gitignore` para certificados y `.env`; `SecretStr`; logs sin claves. |
| I | XXE / SSRF por XML | Parsers lxml con `resolve_entities=False`, `no_network=True`. |
| **D**enial of service | Cuerpos enormes / zip bomb / Argon2 | 1 MiB máx. por petición; 500 líneas máx.; límites en el ZIP simulado; contraseña ≤ 128. |
| **E**levation of privilege | Rol en el token manipulado | Rol leído de la BD en cada petición; registro de administradores solo por administrador o CLI. |

## Cabeceras HTTP

`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`,
`Content-Security-Policy: default-src 'none'` (excepto Swagger), `Cache-Control: no-store`,
HSTS en producción. CORS desactivado salvo `CORS_ORIGENES` explícitos (nunca `*` en producción).

## Riesgos residuales (Recommended)

- Limitador en memoria: usar Redis con varias réplicas.
- Sin refresh tokens ni lista de revocación de JWT.
- Sin cifrado en reposo de los XML (contienen datos personales del adquiriente):
  usar cifrado del volumen/BD gestionada.
- TLS debe terminarse en un proxy (Nginx/Caddy/balanceador); la app confía en
  `--proxy-headers` para la IP del cliente.
- Logs estructurados en JSON y monitoreo de errores (Sentry/OpenTelemetry) pendientes.
