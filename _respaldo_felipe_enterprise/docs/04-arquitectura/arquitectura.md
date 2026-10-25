# Arquitectura

Monolito modular con **puertos y adaptadores** (ver [ADR-001](../decisions/ADR-001-stack-tecnologico.md)).

```mermaid
flowchart LR
    Navegador -->|/app/, /verificar/{cufe}| Web[web/rutas.py + static]
    Web -->|fetch /api/v1 + JWT| API
    Cliente -->|HTTPS + JWT| API[api/rutas]
    API --> Servicio[servicios/facturacion.py]
    Servicio --> Dominio[dominio: Factura, totales, CUFE]
    Servicio --> UBL[ubl: XML UBL 2.1 + ZIP]
    Servicio --> Firma{{FirmadorXml}}
    Servicio --> DIAN{{ClienteDian}}
    Servicio --> Correo{{ServicioCorreo}}
    Servicio --> Prov{{ProveedorFacturacion}}
    Prov --> Factus[proveedor/factus.py → Factus API v2]
    Servicio --> Repr[representacion: PDF + QR]
    Servicio --> BD[(persistencia: SQLAlchemy)]
    Firma --> Xades[firma/xades.py]
    DIAN --> Sim[dian/simulado.py]
    DIAN --> Soap[dian/soap.py → vpfe-hab]
    Correo --> SimC[correo/simulado.py]
    Correo --> Smtp[correo/smtp.py]
```

## Módulos (`src/facturacion/`)

| Módulo | Responsabilidad | Depende de |
|---|---|---|
| `dominio/` | Factura, líneas, totales con `Decimal`, CUFE, contenido del QR | nada |
| `ubl/` | XML UBL 2.1 con extensiones DIAN; nombres de archivo y ZIP | dominio |
| `firma/` | Puerto `FirmadorXml` y XAdES-EPES (Política de Firma v2) | lxml, signxml |
| `dian/` | Puerto `ClienteDian`; adaptador SOAP 1.2 + WS-Security y simulado | httpx, cryptography |
| `proveedor/` | Puerto `ProveedorFacturacion`; adaptador REST `ClienteFactus` (OAuth2, `/v2/bills/validate`) | httpx, dominio |
| `representacion/` | PDF (reportlab) y QR (segno) | dominio |
| `correo/` | Puerto `ServicioCorreo`; SMTP (TLS) y simulado (`.eml`) | stdlib |
| `persistencia/` | Modelos ORM y repositorios | SQLAlchemy |
| `seguridad/` | Argon2id, JWT, limitador de intentos | argon2-cffi, PyJWT |
| `servicios/` | Caso de uso de emisión y derivados | todos los puertos |
| `api/` | Rutas FastAPI, esquemas, errores, middleware (`LimiteCuerpo`, cabeceras, CSP) | servicios |
| `web/` | Rutas `/`, `/app/`, `/verificar/{cufe}` y archivos estáticos (HTML/CSS/JS sin build) | FastAPI `StaticFiles` |
| `arranque.py` | Raíz de composición: elige adaptadores según configuración | todo |

## Flujo de emisión (`POST /api/v1/facturas`), modo `directo`

1. Validación del cuerpo (Pydantic, `extra="forbid"`, límites de tamaño y formato).
2. Verificación de vigencia de la resolución y **consecutivo atómico** (`UPDATE … RETURNING`).
3. Cálculo de totales (ROUND_HALF_UP a 2 decimales) y **CUFE** SHA-384.
4. Generación del XML UBL con `DianExtensions` (resolución, SoftwareID,
   SoftwareSecurityCode, QR) y `UBLExtension[2]` vacío.
5. **Firma XAdES-EPES** dentro de `UBLExtension[2]`.
6. Se guarda la factura en `error_envio` y se hace `commit` **antes** de transmitir (libera el
   bloqueo del consecutivo; si el proceso cae, queda para reintentar).
7. ZIP con nombre `fv{NIT}{000}{AA}{consecutivo hex}.xml` y envío a la DIAN.
8. Se actualizan estado, respuesta y `ApplicationResponse`, y segundo `commit`.

## Flujo de emisión, modo `factus` (`FACTURACION_MODO=factus`, [ADR-004](../decisions/ADR-004-proveedor-tecnologico-factus.md))

1. Validación del cuerpo y cálculo de totales igual que en modo directo (sin numeración propia).
2. Registro **pendiente** (`en_proceso`, número `PEND-…`, `datos.proveedor.referencia`) y `commit`.
3. `ClienteFactus.emitir`: token OAuth2 (password grant, renovación con `refresh_token`,
   reintento único ante 401) → `POST /v2/bills/validate` → descarga del XML (mejor esfuerzo).
4. Éxito: el pendiente pasa a `aceptada` con número, CUFE y URL del QR de Factus.
   `RechazoProveedor`: se borra el pendiente → 422. `ErrorProveedor`: queda `error_envio`
   con la referencia para conciliar → 502. Número/CUFE duplicado en la BD: `error_envio` → 422.
5. `reintentar-envio` no aplica a estas facturas (409).

Detalle didáctico: [guía, recorrido del código](../guia/02-recorrido-del-codigo.md).

Estados: `aceptada`, `rechazada`, `en_proceso` (set de pruebas, o pendiente del proveedor),
`error_envio` (reintentable).

## Derivados

- **PDF**: se regenera bajo demanda desde la instantánea JSON guardada (emisor y
  numeración vigentes al emitir), con QR en todas las páginas.
- **QR**: contenido del anexo + URL de verificación: propia (`{URL_PUBLICA_BASE}/verificar/{cufe}`,
  página HTML que consulta `GET /api/v1/verificacion/{cufe}`), catálogo DIAN
  (`QR_URL_MODO=dian`) o la que entrega Factus.
- **Correo**: solo facturas `aceptada`; adjunta un ZIP con PDF, XML firmado y
  `ApplicationResponse`; asunto `NIT;Razón social;Número;01;Razón social`.

## Interfaz web

SPA estática en `src/facturacion/web/static/` servida en `/app/` (`/` redirige allí), con
enrutamiento por hash (`#/facturas`, `#/facturas/nueva`, `#/facturas/{id}`, `#/usuarios`). Solo
consume la API pública `/api/v1`; el token JWT vive en memoria y `sessionStorage`. Todo el
DOM se construye con `textContent` (nunca `innerHTML`) y una CSP estricta lo refuerza.
