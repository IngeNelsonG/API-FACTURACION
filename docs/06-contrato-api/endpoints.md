# Contrato de la API (v1)

La especificación OpenAPI completa está en `/docs` (Swagger) y `/openapi.json`
cuando `ENTORNO` no es `produccion`.

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| GET | `/salud` | — | Comprobación de vida. |
| POST | `/api/v1/auth/login` | — | Formulario `username`, `password` → `access_token` JWT. |
| POST | `/api/v1/auth/registro` | administrador¹ | Crea un usuario. |
| GET | `/api/v1/auth/yo` | JWT | Perfil del usuario autenticado. |
| POST | `/api/v1/facturas` | JWT | Emite, firma y envía una factura. |
| GET | `/api/v1/facturas?limite&desplazamiento` | JWT | Lista paginada (máx. 100). |
| GET | `/api/v1/facturas/{id}` | JWT | Detalle y respuesta DIAN. |
| GET | `/api/v1/facturas/{id}/pdf` | JWT | Descarga la representación gráfica. |
| GET | `/api/v1/facturas/{id}/xml` | JWT | Descarga el XML firmado. |
| GET | `/api/v1/facturas/{id}/qr` | JWT | Imagen PNG del QR. |
| POST | `/api/v1/facturas/{id}/correo` | JWT | Envía ZIP (PDF + XML) al adquiriente o a `destinatario`. |
| POST | `/api/v1/facturas/{id}/reintentar-envio` | JWT | Reenvía una factura en `error_envio`. |
| POST | `/api/v1/facturas/{id}/consultar-estado` | JWT | `GetStatusZip` para facturas `en_proceso`. |
| GET | `/api/v1/verificacion/{cufe}` | — | Evidencia pública a la que apunta el QR. |

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
desconocidos se rechazan.

## Errores

Todas las respuestas de error tienen la forma `{"detalle": ...}`.

| Código | Cuándo |
|---|---|
| 401 | Token ausente, inválido o expirado; credenciales incorrectas. |
| 403 | Rol insuficiente. |
| 404 | Recurso inexistente o de otro usuario. |
| 409 | Estado no permite la acción (p. ej. correo de factura no aceptada) o correo duplicado. |
| 413 | Cuerpo mayor a 1 MiB. |
| 422 | Validación de entrada o regla de negocio (rango agotado, resolución vencida). |
| 429 | Demasiados intentos de login (`Retry-After`). |
| 502 | El servidor de correo rechazó el envío. |
| 500 | Error interno (sin detalles; ver logs). |
