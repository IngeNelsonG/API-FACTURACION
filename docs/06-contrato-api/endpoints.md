# Contrato de la API (v1)

La especificación OpenAPI completa está en `/docs` (Swagger) y `/openapi.json`
cuando `ENTORNO` no es `produccion`.

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| GET | `/salud` | — | Comprobación de vida. |
| POST | `/api/v1/auth/login` | — | Formulario `username`, `password` → `access_token` JWT. |
| POST | `/api/v1/auth/registro` | administrador¹ | Crea un usuario. |
| GET | `/api/v1/auth/yo` | JWT | Perfil del usuario autenticado. |
| POST | `/api/v1/facturas` | JWT | Emite la factura: en modo `directo` la firma y envía a la DIAN; en modo `factus` la delega al proveedor. |
| GET | `/api/v1/facturas?limite&desplazamiento` | JWT | Lista paginada (máx. 100). |
| GET | `/api/v1/facturas/{id}` | JWT | Detalle y respuesta DIAN. |
| GET | `/api/v1/facturas/{id}/pdf` | JWT | Descarga la representación gráfica. |
| GET | `/api/v1/facturas/{id}/xml` | JWT | Descarga el XML firmado (404 si no está disponible, p. ej. Factus no lo entregó). |
| GET | `/api/v1/facturas/{id}/qr` | JWT | Imagen PNG del QR. |
| POST | `/api/v1/facturas/{id}/correo` | JWT | Envía ZIP (PDF + XML) al adquiriente o a `destinatario`. |
| POST | `/api/v1/facturas/{id}/reintentar-envio` | JWT | Reenvía a la DIAN una factura en `error_envio` (409 si pasó por el proveedor tecnológico: debe conciliarse). |
| POST | `/api/v1/facturas/{id}/consultar-estado` | JWT | `GetStatusZip` para facturas `en_proceso`. |
| GET | `/api/v1/verificacion/{cufe}` | — | Evidencia pública en JSON (sin datos del adquiriente); la consume `/verificar/{cufe}`. |

### Rutas web (fuera de OpenAPI)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Redirige (307) a `/app/`. |
| GET | `/app/` | Interfaz web (SPA estática, enrutamiento por hash). `/app` redirige a `/app/`. |
| GET | `/verificar/{cufe}` | Página pública de verificación, **destino del QR** con `QR_URL_MODO=propia`. CUFE validado con `^[0-9a-f]{96}$` (si no, 422). |

Estas rutas llevan una CSP propia (`script-src 'self'`, sin scripts en línea); el resto de la
API usa `default-src 'none'`.

### Modos de emisión

`FACTURACION_MODO=directo` (defecto): la API numera, calcula el CUFE, firma XAdES y envía a la
DIAN (`DIAN_MODO=simulado|habilitacion`). `FACTURACION_MODO=factus`: Factus numera, calcula el
CUFE, firma y transmite; la respuesta tiene la misma forma, con el número, el CUFE y la URL del
QR que asigna Factus. Antes de llamar a Factus se guarda un registro pendiente
(`en_proceso`, número `PEND-…`) que se actualiza o se borra según el resultado
([detalle](../guia/05-factus-sandbox.md#55-mapeo-de-errores)).

¹ Con `REGISTRO_PUBLICO=true` cualquiera puede crear usuarios `facturador`.
Un facturador solo ve sus propias facturas (las ajenas responden 404).

## Ejemplo

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login \
  -d 'username=admin@example.com&password=SU-CLAVE' | jq -r .access_token)

curl -s -X POST localhost:8000/api/v1/facturas \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{
  "adquiriente": {
    "tipo_documento": "13", "numero_documento": "1020304050",
    "nombre": "María Pérez", "email": "maria@example.com",
    "ciudad": "Medellín", "codigo_municipio": "05001",
    "departamento": "Antioquia", "codigo_departamento": "05"
  },
  "lineas": [
    {"descripcion": "Hosting anual", "cantidad": "1",
     "precio_unitario": "480000.00", "porcentaje_iva": "19", "codigo": "HOST-1"}
  ],
  "forma_pago": "1", "medio_pago": "10"
}'
```

Reglas de validación principales: `porcentaje_iva` ∈ {0, 5, 19}; `precio_unitario`
con máximo 2 decimales; 1 a 500 líneas; `dv` obligatorio si `tipo_documento=31`
(NIT); `fecha_vencimiento` obligatoria si `forma_pago=2` (crédito); campos
desconocidos se rechazan; los textos no admiten caracteres de control (solo `notas`
admite saltos de línea). En modo `factus` la cantidad también debe tener máximo 2 decimales.

## Errores

Todas las respuestas de error tienen la forma `{"detalle": ...}`: una cadena, o una lista de
`{"campo", "mensaje"}` en los errores de validación (sin eco del valor recibido).

| Código | Cuándo |
|---|---|
| 401 | Token ausente, inválido o expirado; credenciales incorrectas. |
| 403 | Rol insuficiente. |
| 404 | Recurso inexistente o de otro usuario. |
| 409 | Estado no permite la acción (p. ej. correo de factura no aceptada, reintento de una factura del proveedor) o correo duplicado. |
| 413 | Cuerpo mayor a 1 MiB (por `Content-Length` o contando los bytes de un cuerpo *chunked*). |
| 422 | Validación de entrada o regla de negocio (rango agotado, resolución vencida); **rechazo del proveedor** (formato abajo); factura emitida por el proveedor con número/CUFE ya existente (queda `error_envio` para conciliar). |
| 429 | Demasiados intentos de login por IP + correo o por IP (`Retry-After`). |
| 502 | El servidor de correo rechazó el envío (`"No fue posible enviar el correo"`) o **el proveedor tecnológico no está disponible** (`"El proveedor de facturación no está disponible"`; la factura queda `error_envio` con la referencia para conciliar). |
| 500 | Error interno (sin detalles; ver logs). |

Rechazo del proveedor tecnológico (Factus o la DIAN a través de él), HTTP 422; no se guarda la factura:

```json
{"detalle": [
  {"campo": "proveedor", "mensaje": "customer.identification: El campo es obligatorio"}
]}
```
