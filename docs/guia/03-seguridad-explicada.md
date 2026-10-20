# 3. Seguridad explicada

> Objetivo: entender **qué ataque evita cada control, cómo lo implementa el código y qué
> riesgo queda**. Complementa el [modelo de amenazas STRIDE](../security/modelo-de-amenazas.md)
> y las reglas de [`.agents/security.md`](../../.agents/security.md).

## 3.1 Panorama: fronteras de confianza

```mermaid
flowchart LR
    N["Navegador / cliente<br/>(no confiable)"] -->|HTTPS + JWT| A["API FastAPI"]
    P["Público con el QR<br/>(sin login)"] -->|GET /verificar/{cufe}| A
    A -->|SOAP + WS-Security, TLS| D["DIAN"]
    A -->|REST OAuth2, TLS| F["Factus"]
    A -->|SMTP STARTTLS/SSL| M["Servidor de correo"]
    A --> B[("Base de datos")]
    S["Secretos: .env, certificados/"] -.-> A
```

Regla de oro: **todo lo que cruza una flecha hacia la API es no confiable** (incluidas las
respuestas de la DIAN y de Factus).

## 3.2 Contraseñas con Argon2id

**Problema:** si roban la base de datos, el atacante no debe poder recuperar contraseñas.
Por eso no se guardan, se guarda un **hash lento con sal**.

**Por qué Argon2id y no bcrypt** ([ADR-002](../decisions/ADR-002-autenticacion-jwt-argon2id.md)):

| | bcrypt | Argon2id |
|---|---|---|
| Ganó la Password Hashing Competition (2015) | No | **Sí** |
| Resistente a GPU/ASIC (usa mucha memoria) | Poco (4 KiB) | **Sí** (64 MiB por hash aquí) |
| Límite de longitud | Trunca a 72 bytes | Sin truncar |
| Recomendación OWASP | Alternativa | **Primera opción** |

Implementación (`src/facturacion/seguridad/contrasenas.py`): `PasswordHasher()` de
`argon2-cffi` con sus parámetros por defecto (perfil RFC 9106 *low memory*: t=3, m=64 MiB, p=4).

Detalles que suman puntos:

- **Política:** 12 a 128 caracteres, sin espacios al inicio/fin, al menos 4 caracteres distintos (`validar_politica`).
  El máximo de 128 evita que alguien mande contraseñas gigantes para agotar CPU/RAM.
- **Rehash transparente:** si cambian los parámetros, en el siguiente login se recalcula (`requiere_rehash`).
- **Hash señuelo:** si el correo no existe se verifica igual contra `_HASH_SEÑUELO`, para que el
  **tiempo de respuesta** no revele qué correos están registrados.

```python
def verificar(hash_guardado: str | None, contrasena: str) -> bool:
    try:
        return _hasher.verify(hash_guardado or _HASH_SEÑUELO, contrasena) and bool(hash_guardado)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
```

## 3.3 JWT: emisión y validación

Tras el login (`POST /api/v1/auth/login`, flujo OAuth2 *password* con formulario) la API
entrega un **JWT firmado con HS256** (`src/facturacion/seguridad/tokens.py`).

| Reclamo (*claim*) | Para qué | Valor |
|---|---|---|
| `sub` | Quién es | id del usuario |
| `rol` | Informativo (no se usa para autorizar) | `administrador` / `facturador` |
| `iss` | Quién lo emitió | `api-facturacion` |
| `aud` | Para quién es | `api-facturacion-clientes` |
| `iat`, `nbf` | Emitido / no válido antes de | ahora |
| `exp` | Expira | ahora + `JWT_MINUTOS_EXPIRACION` (30 por defecto) |
| `jti` | Identificador único | UUID4 |

Validación:

```python
reclamos = jwt.decode(
    token, config.jwt_secreto.get_secret_value(),
    algorithms=[ALGORITMO],                 # lista fija: bloquea "alg": "none" y confusión RS/HS
    audience=config.jwt_audiencia,
    issuer=config.jwt_emisor,
    options={"require": RECLAMOS_OBLIGATORIOS},
    leeway=5,
)
```

- **El rol se lee de la base de datos en cada petición** (`api/dependencias.py:usuario_actual`),
  no del token. Así, desactivar a un usuario o cambiarle el rol surte efecto de inmediato, y
  manipular el token no sirve (además está firmado).
- `JWT_SECRETO` debe tener ≥ 32 caracteres; con `ENTORNO=produccion` se rechaza el valor por
  defecto y el marcador `CAMBIAR…` de `.env.example` (`configuracion.py:_validar_coherencia`).

## 3.4 Limitador de intentos de login (rate limiting)

**Problema:** fuerza bruta de contraseñas.
**Control:** `src/facturacion/seguridad/limitador.py:LimitadorIntentos`, ventana deslizante en
memoria, con **dos contadores** (`api/rutas/autenticacion.py:iniciar_sesion`):

| Contador | Clave | Límite por defecto | Frena |
|---|---|---|---|
| `limitador_login` | `IP\|correo` | `LOGIN_MAX_INTENTOS` = 5 | Adivinar la clave de **una** cuenta |
| `limitador_login_ip` | `IP` | `LOGIN_MAX_INTENTOS_IP` = 30 | Probar muchas cuentas desde una IP (*credential stuffing*) |

Ambos usan la ventana `LOGIN_VENTANA_SEGUNDOS` (300). Si cualquiera se llena, la API responde
**429** con `Retry-After`. Un login exitoso reinicia el contador `IP|correo`. Las claves sin
intentos vigentes se borran (`_purgar`), para que la memoria no crezca con cada correo o IP
probada. El mensaje de error es siempre el mismo ("Correo o contraseña incorrectos") para no
revelar si el correo existe.

## 3.5 Control de acceso e IDOR

**IDOR** (*Insecure Direct Object Reference*): cambiar el id en la URL para ver la factura de
otro. Control en `api/rutas/facturas.py:_cargar`:

```python
# Un administrador ve todas las facturas; un facturador solo las suyas (evita IDOR).
dueno = None if usuario.rol == Rol.ADMINISTRADOR else usuario
registro = repositorios.obtener_factura(sesion, factura_id, dueno)
if registro is None:
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Factura no encontrada")
```

El filtro va **en la consulta SQL** (`WHERE usuario_id = …`) y se responde **404** (no 403)
para no confirmar que la factura existe. Además los ids son UUID4, no secuenciales.
Probado en `tests/integracion/test_api_facturas.py::test_facturador_no_ve_facturas_de_otro`.

Roles: `administrador` (crea usuarios, ve todo) y `facturador` (solo lo suyo). El primer
administrador solo se crea por CLI (`python -m facturacion.cli crear-admin`).

## 3.6 Asignación masiva (*mass assignment*)

**Problema:** enviar campos extra como `"rol": "administrador"` o `"activo": true` o
`"total": 1` esperando que el servidor los copie al modelo.
**Control:** todos los esquemas de entrada heredan de `EsquemaEntrada`:

```python
class EsquemaEntrada(BaseModel):
    # Rechazar campos desconocidos evita la asignación masiva de atributos.
    model_config = ConfigDict(extra="forbid")
```

Además, el total y el IVA **no existen** en `FacturaEntrada`: siempre los calcula el servidor.
En `RegistroUsuario` el campo `rol` sí existe, pero `registrar_usuario` solo permite crear
administradores a un administrador; con `REGISTRO_PUBLICO=true` un anónimo solo puede crear
`facturador`.

## 3.7 Validación estricta de entrada e inyección

| Ataque | Control | Dónde |
|---|---|---|
| Datos mal formados | Pydantic con patrones y longitudes (`numero_documento` `^[0-9A-Za-z-]{3,20}$`, IVA ∈ {0,5,19}, 1–500 líneas, 2 decimales en precio) | `api/esquemas.py` |
| Caracteres de control (`\x00`, `\r\n`…) en textos | Patrones `SIN_CONTROL` (y `SIN_CONTROL_MULTILINEA` para `notas`, que admite saltos de línea) → 422 | `api/esquemas.py` |
| Inyección SQL | Solo el constructor de consultas de SQLAlchemy (parametrizado) | `persistencia/repositorios.py` |
| Inyección de marcado en el PDF | `xml.sax.saxutils.escape` antes de `Paragraph` | `representacion/pdf.py:_p` |
| Inyección de cabeceras de correo (`\r\nBcc:`) | Rechazo de CR/LF + `email-validator` | `correo/mensaje.py` |
| Recorrido de rutas | `StaticFiles` (no sale del directorio); nombres de `.eml` generados con UUID; CUFE validado con regex `^[0-9a-f]{96}$` | `web/rutas.py`, `correo/simulado.py`, `api/rutas/publico.py` |
| Cuerpos enormes | Middleware ASGI `LimiteCuerpo`: revisa `Content-Length` **y cuenta los bytes** recibidos (cubre `Transfer-Encoding: chunked`); > 1 MiB → 413 | `api/middleware.py` |
| Eco de datos sensibles en errores | Los 422 devuelven `campo` y `mensaje`, nunca el valor recibido | `api/errores.py` |

## 3.8 CSP y por qué la interfaz nunca usa `innerHTML`

**XSS** (*Cross-Site Scripting*): lograr que el navegador ejecute JavaScript del atacante, por
ejemplo guardando como nombre del cliente `<img src=x onerror=robarToken()>`. Si la interfaz
insertara ese texto con `innerHTML`, el navegador lo interpretaría como HTML.

Dos capas de defensa:

1. **Nunca interpretar texto como HTML.** Todo el DOM se construye con `createElement` y
   `textContent` (`web/static/js/utils.js:el`), que trata cualquier cadena como texto plano.
   La función `el` incluso prohíbe atributos `on*` y `style`. Un test lo garantiza:
   `tests/integracion/test_web.py::test_javascript_sin_sumideros_peligrosos` falla si aparece
   `innerHTML` u otros sumideros peligrosos en el JS; otro revisa que el HTML no tenga scripts,
   estilos ni manejadores en línea.
2. **Content-Security-Policy** (`api/middleware.py`). Aunque se colara un `<script>`, el
   navegador no lo ejecutaría:

```python
_CSP_WEB = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; "
    "connect-src 'self'; font-src 'self'; base-uri 'none'; form-action 'self'; "
    "frame-ancestors 'none'"
)
```

`script-src 'self'` sin `'unsafe-inline'` bloquea scripts en línea e inyectados;
`connect-src 'self'` impide enviar datos a otro dominio; `frame-ancestors 'none'` evita el
*clickjacking*. Las rutas de la API llevan una CSP aún más estricta
(`default-src 'none'; frame-ancestors 'none'`). Solo Swagger (`/docs`, `/redoc`, `/openapi.json`)
queda sin CSP, y está **desactivado en producción**.

Otras cabeceras en todas las respuestas: `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy`,
`Permissions-Policy`, `Cache-Control: no-store` (el HTML de la SPA tampoco se cachea) y HSTS en
producción.

Defensas extra en el JS: `js/api.js` usa `credentials: 'omit'`, `redirect: 'error'` y rechaza
rutas fuera de `/api/v1/` (no puede filtrar el token a otro origen); `utils.js:urlSegura` solo
acepta enlaces `http(s)`. El token se guarda en `sessionStorage` (se borra al cerrar la
pestaña), nunca en `localStorage` ni en cookies, así que no hay CSRF.

## 3.9 XXE y XML no confiable

**XXE** (*XML External Entity*): un XML con `<!ENTITY x SYSTEM "file:///etc/passwd">` puede
hacer que el parser lea archivos o haga peticiones de red. Todos los parsers del proyecto
(`firma/xades.py`, `dian/simulado.py`, `dian/soap.py`) se crean así:

```python
_PARSER_SEGURO = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
```

`huge_tree=False` además frena el "billion laughs". El simulador limita el ZIP (máx. 10
entradas, 10 MiB por XML) contra *zip bombs*, y el cliente de Factus corta respuestas de más
de 10 MiB mientras las lee (`ClienteFactus._enviar`).

## 3.10 TLS en todas las conexiones salientes

| Conexión | Control |
|---|---|
| DIAN | `httpx.Client(verify=True)` en `dian/soap.py`; no existe opción para desactivarlo |
| Factus | `verify=True` y la URL **debe** ser `https://` (si no, `ValueError` al construir `ClienteFactus`) |
| SMTP | `ssl.create_default_context()` con STARTTLS (587) o SSL implícito (465), excluyentes; con `SMTP_USUARIO` y sin ninguno de los dos la app **no arranca** (la clave viajaría en claro) |
| Navegador → API | Se termina TLS en un proxy (Nginx, Caddy, balanceador); HSTS en producción; uvicorn con `--proxy-headers` en el `Dockerfile` |

## 3.11 Manejo de secretos

- Secretos solo en `.env` y `certificados/`, ambos en `.gitignore` (también `*.p12`, `*.pfx`, `*.pem`, `*.key`).
- En `configuracion.py` son `SecretStr` (`JWT_SECRETO`, `DIAN_PIN`, `DIAN_CERTIFICADO_CLAVE`,
  `NUMERACION_CLAVE_TECNICA`, `SMTP_CLAVE`, `FACTUS_CLIENT_SECRET`, `FACTUS_CLAVE`): al
  imprimirse muestran `**********`.
- `__repr__` personalizados en `FirmadorXades`, `ServicioCorreoSmtp` y `ClienteFactus` para que
  una traza nunca muestre llaves ni claves.
- Los errores al cargar el `.p12` descartan la excepción original (podría contener detalles).
- El token OAuth de Factus vive solo en memoria y `ClienteFactus._redactar` borra cualquier
  secreto que Factus refleje en un mensaje de error.
- La CLI pide la contraseña sin eco (`getpass`) o la lee de `ADMIN_CONTRASENA`; nunca por argumento.

## 3.12 Qué expone la página de verificación pública

`GET /verificar/{cufe}` (HTML) y `GET /api/v1/verificacion/{cufe}` (JSON) **no piden login**,
porque cualquiera con el PDF debe poder comprobar la factura. Devuelven solo
(`api/esquemas.py:VerificacionPublica`):

| Se muestra | No se muestra |
|---|---|
| número, CUFE, fecha de emisión, NIT y razón social del **emisor**, total, estado | nombre, documento, correo, dirección o teléfono del **adquiriente**; líneas; XML |

El CUFE es un SHA-384 (2³⁸⁴ valores posibles): no se puede enumerar. Test:
`test_api_facturas.py::test_verificacion_publica_no_expone_adquiriente`.

## 3.13 Mapa al OWASP Top 10 (2021)

| OWASP | Riesgo | Controles en el proyecto |
|---|---|---|
| **A01** Broken Access Control | Ver facturas ajenas, escalar a admin | Filtro por dueño en SQL + 404 (IDOR); rol desde BD; `requerir_rol`; registro de admins solo por admin/CLI; CORS cerrado por defecto |
| **A02** Cryptographic Failures | Contraseñas o datos en claro | Argon2id; JWT HS256 con secreto ≥ 32; TLS verificado; firma XAdES RSA-SHA256; CUFE SHA-384 |
| **A03** Injection | SQL, XSS, cabeceras, marcado PDF | SQLAlchemy parametrizado; `textContent` + CSP; caracteres de control rechazados (`SIN_CONTROL`); `escape` en PDF; validación Pydantic |
| **A04** Insecure Design | Totales manipulados, numeración duplicada | Totales en servidor; consecutivo atómico; modo producción deshabilitado por diseño (ADR-003); puertos con simulados |
| **A05** Security Misconfiguration | Swagger expuesto, cabeceras, CORS `*` | Swagger off en producción; cabeceras defensivas; `*` prohibido en producción; la app no arranca con config incompleta |
| **A06** Vulnerable Components | Dependencias con CVE | `pip-audit` en CI; rangos de versión acotados en `pyproject.toml` |
| **A07** Identification & Authentication Failures | Fuerza bruta, enumeración | Limitador 429 por IP + correo y por IP; mensaje único; hash señuelo; política de contraseñas; expiración corta del JWT |
| **A08** Software & Data Integrity Failures | Factura alterada | Firma digital XAdES; CUFE; `alg` fijo en JWT; parsers seguros |
| **A09** Logging & Monitoring Failures | No detectar ataques; filtrar secretos | Logs de login fallido/exitoso y emisión, sin secretos; errores 500 genéricos con traza solo en el log |
| **A10** SSRF | Que la API haga peticiones a URLs del atacante | Ninguna URL saliente viene del usuario (DIAN/Factus/SMTP salen de la configuración); `no_network=True` en XML; el JS usa `redirect: 'error'` |

## 3.14 Riesgos residuales conocidos

Ser honesto con esto da credibilidad en la sustentación:

| Riesgo | Por qué existe | Mitigación propuesta |
|---|---|---|
| Limitador en memoria | Con varias réplicas cada una cuenta aparte; se pierde al reiniciar | Redis |
| Limitador por IP | Un atacante con muchas IPs (botnet) evade ambos contadores; detrás de un proxy sin `--proxy-headers` todos comparten la IP del proxy | Límite global, CAPTCHA tras fallos, WAF |
| Sin revocación de JWT ni *refresh tokens* | El `jti` existe pero no hay lista negra | Lista de revocación en Redis; tokens de refresco rotativos |
| Token en `sessionStorage` | Un XSS podría leerlo | Ya mitigado por CSP + no `innerHTML`; alternativa: cookie `HttpOnly` + `SameSite` (exige protección CSRF) |
| Reintento tras *timeout* en modo directo | Si la DIAN procesó el primer envío pero la respuesta se perdió, `reintentar-envio` puede recibir "documento procesado anteriormente" | Consultar `GetStatus` por CUFE antes de reenviar (pendiente) |
| Conciliación manual en modo Factus | Si Factus no responde, la factura queda `error_envio` con la referencia `API-…`; puede que Factus sí la haya emitido | Consultar en Factus por `reference_code` (pendiente de automatizar) |
| Sin cifrado en reposo | `facturas.datos` y el XML contienen datos personales del adquiriente | Cifrado de disco/BD gestionada |
| TLS depende del proxy | uvicorn no termina TLS | Desplegar detrás de Nginx/Caddy/balanceador |
| Logs no estructurados | El formato de `logging.basicConfig` (`main.py`) no imprime los campos `extra` (p. ej. la IP de `login_fallido`) | Logs JSON + OpenTelemetry/Sentry |
| Verificación pública sin limitador | Abuso de recursos (no enumeración) | Rate limit en el proxy |
| Sin *lockfile* con hashes | `pyproject.toml` usa rangos | `pip-tools`/`uv lock` con `--require-hashes` |
