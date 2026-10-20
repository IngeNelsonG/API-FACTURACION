# 4. Cómo usarlo: tutorial práctico

> Objetivo: en ~30 minutos tener la API corriendo, emitir una factura desde la interfaz web,
> descargar su PDF y XML, enviarla por correo y escanear el QR. Todo en **modo simulado**, sin
> credenciales de la DIAN.

## 1. Requisitos

- **Python 3.12 o superior** (`python3 --version`).
- Git.
- Opcional: Docker y Docker Compose (sección 10).
- Opcional: una cuenta de Gmail con verificación en dos pasos (para correo real).

## 2. Instalación

```bash
git clone <url-del-repositorio> API-FACTURACION
cd API-FACTURACION
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"            # instala la app y las herramientas de desarrollo
```

`-e` (editable) significa que los cambios en `src/` se ven sin reinstalar.

## 3. Configurar el `.env`

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # copie el resultado
```

### 3.1 Mínimo obligatorio

Abra `.env` y reemplace el valor de `JWT_SECRETO` por el secreto generado:

```ini
JWT_SECRETO=pegue-aqui-el-valor-generado
```

Con eso basta: por defecto `DIAN_MODO=simulado`, `CORREO_MODO=simulado`,
`FACTURACION_MODO=directo` y la base de datos es SQLite en `var/facturacion.db` (la carpeta
`var/` se crea sola). Todas las variables se validan en `src/facturacion/configuracion.py`.

> **Nunca** suba el `.env` a git (ya está en `.gitignore`).

### 3.2 Opcional: correo real con Gmail

1. Active la **verificación en dos pasos** en su cuenta de Google.
2. Cree una **contraseña de aplicación** en <https://myaccount.google.com/apppasswords> (16 caracteres).
3. En `.env`:

```ini
CORREO_MODO=smtp
MAIL_HOST=smtp.gmail.com
MAIL_PORT=587
MAIL_USER=sucorreo@gmail.com
MAIL_PASSWORD=la-contraseña-de-aplicación
MAIL_SMTP_AUTH=true
MAIL_STARTTLS=true
```

Use la contraseña de aplicación, **no** su contraseña normal de Google. El remitente será
`MAIL_USER` salvo que defina `CORREO_REMITENTE`. `MAIL_SSL` (por defecto `false`) solo se usa
con el puerto 465.

### 3.3 Opcional: Factus sandbox

Si ya tiene credenciales del sandbox de Factus (ver [guía 5](05-factus-sandbox.md)):

```ini
FACTURACION_MODO=factus
FACTUS_URL=https://api-sandbox.factus.com.co
FACTUS_CLIENT_ID=...
FACTUS_CLIENT_SECRET=...
FACTUS_USUARIO=...
FACTUS_CLAVE=...
# FACTUS_RANGO_NUMERACION_ID=   # opcional
```

Si falta alguna de las cuatro credenciales, la API **no arranca** y dice cuál falta.

### 3.4 Otras variables útiles

| Variable | Defecto | Para qué |
|---|---|---|
| `URL_PUBLICA_BASE` | `http://localhost:8000` | Base de la URL que va en el QR (`/verificar/{cufe}`) |
| `QR_URL_MODO` | `propia` | `propia` = página de este sistema; `dian` = catálogo de habilitación |
| `JWT_MINUTOS_EXPIRACION` | `30` | Vida del token |
| `LOGIN_MAX_INTENTOS` / `LOGIN_MAX_INTENTOS_IP` / `LOGIN_VENTANA_SEGUNDOS` | `5` / `30` / `300` | Limitador de login (por IP + correo y por IP) |
| `REGISTRO_PUBLICO` | `false` | Permitir que cualquiera cree usuarios `facturador` |
| `EMISOR_*`, `NUMERACION_*` | datos de prueba | Emisor y rango de numeración (habilitación: [guía](../03-habilitacion/paso-a-paso-credenciales.md)) |
| `DATABASE_URL` | SQLite | `postgresql+psycopg://…` para PostgreSQL (instale `pip install -e ".[postgres]"`) |

## 4. Crear el administrador

```bash
python -m facturacion.cli crear-admin --email admin@example.com --nombre "Admin"
# Contraseña: (no se ve al escribir)
```

La contraseña debe tener **12 a 128 caracteres**, sin espacios al inicio o al final y al menos
4 caracteres distintos. Para scripts puede usar la variable `ADMIN_CONTRASENA` en vez del
prompt (nunca como argumento: quedaría en el historial).

## 5. Ejecutar

```bash
uvicorn facturacion.asgi:app --reload
```

| URL | Qué es |
|---|---|
| <http://localhost:8000/> | Redirige a la interfaz web |
| <http://localhost:8000/app/> | **Interfaz web** |
| <http://localhost:8000/docs> | Swagger UI (no disponible con `ENTORNO=produccion`) |
| <http://localhost:8000/salud> | Comprobación de vida: `{"estado":"ok"}` |

En la consola verá `Usando certificado autofirmado de desarrollo (no válido ante la DIAN)`:
es normal en modo simulado.

## 6. Usar la interfaz web paso a paso

### 6.1 Iniciar sesión

Abra <http://localhost:8000/app/> e ingrese el correo y la contraseña del administrador. La
franja superior recuerda que es un **ambiente de pruebas**. Tras 5 intentos fallidos verá
"Demasiados intentos fallidos. Intente de nuevo en 5 minutos".

### 6.2 Crear una factura

1. Pulse **Nueva factura** (ruta `#/facturas/nueva`).
2. **Adquiriente:** tipo de documento (p. ej. *Cédula de ciudadanía*), número sin puntos,
   nombre, correo (recibirá el PDF/XML), dirección, ciudad y códigos DANE (Bogotá `11001`,
   departamento `11`; Medellín `05001` / `05`). Si elige **NIT**, el **DV** es obligatorio.
3. **Ítems:** descripción, cantidad, precio unitario **sin IVA** (máx. 2 decimales) y tarifa de
   IVA (19 %, 5 % o 0 % exento). Con **Agregar ítem** suma líneas; el panel **Resumen** calcula
   subtotal, IVA y total en vivo con la misma regla de redondeo que el servidor.
4. **Pago:** contado o crédito (crédito exige fecha de vencimiento), medio de pago y notas.
5. Pulse **Emitir factura**. Si algo está mal, el campo se marca en rojo con el mensaje del servidor.

Al terminar, la app lo lleva al **detalle** de la factura.

### 6.3 Ver el detalle

En `#/facturas/{id}` verá:

- Total, número (`SETP990000000`…), fecha, **estado** (en simulado: *Aceptada*), Track ID si aplica.
- Datos del adquiriente.
- **Respuesta de la DIAN**: código `00` y mensaje "…ha sido autorizada (simulado)".
- **Código QR** y el **CUFE** (botón para copiarlo).
- Enlace **Ver página de verificación**.
- Botones **PDF**, **XML**, **Enviar por correo** y, según el estado, **Reintentar envío**
  (`error_envio`) o **Consultar estado** (`en_proceso`).

### 6.4 Descargar PDF y XML

Pulse **PDF** o **XML**. Abra el XML con un editor: busque `cbc:UUID` (el CUFE),
`sts:DianExtensions` y `ds:Signature` (la firma XAdES). En el PDF verá el QR en la esquina
inferior derecha de cada página y la leyenda de ambiente de pruebas.

### 6.5 Enviar por correo

Pulse **Enviar por correo**. Puede dejar el destinatario vacío (va al correo del adquiriente)
o escribir otro. Solo funciona con facturas **aceptadas**.

- `CORREO_MODO=simulado`: el mensaje queda en `var/correos/*.eml`. Ábralo con Thunderbird u
  Outlook, o con un editor de texto; trae un ZIP con el PDF, el XML firmado y el `ApplicationResponse`.
- `CORREO_MODO=smtp` con Gmail: llega a la bandeja real.

### 6.6 Escanear el QR

El QR contiene `QRCode=http://localhost:8000/verificar/{cufe}`. Desde el **mismo computador**
abra el enlace **Ver página de verificación**. Para escanearlo con el **celular**, que no
conoce su `localhost`:

1. Averigüe la IP local del computador (p. ej. `192.168.1.10`).
2. En `.env`: `URL_PUBLICA_BASE=http://192.168.1.10:8000`.
3. Arranque con `uvicorn facturacion.asgi:app --host 0.0.0.0 --port 8000`.
4. Recargue el detalle (el QR del PDF y de la pantalla se regenera con la URL nueva) y escanéelo
   con el celular en la misma red Wi-Fi.

La página muestra "Factura verificada" con número, fecha, emisor, NIT, total y CUFE, **sin
datos del adquiriente**.

### 6.7 Crear más usuarios

Como administrador, en **Usuarios** (`#/usuarios`) cree cuentas `facturador`. Un facturador
solo ve sus propias facturas; el administrador ve todas.

## 7. Usar Swagger

1. Abra <http://localhost:8000/docs>.
2. Pulse **Authorize**, escriba el correo en `username` y la contraseña en `password` (deje
   `client_id`/`client_secret` vacíos) y pulse **Authorize**.
3. Expanda `POST /api/v1/facturas` → **Try it out** → pegue el JSON de la sección 8 → **Execute**.
4. Copie el `id` de la respuesta y pruebe `GET /api/v1/facturas/{factura_id}/pdf`.

## 8. Usar `curl`

```bash
# 1) Login: formulario OAuth2 (username = correo)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d 'username=admin@example.com&password=SU-CLAVE' | jq -r .access_token)

# 2) Emitir
curl -s -X POST http://localhost:8000/api/v1/facturas \
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
}' | tee factura.json

ID=$(jq -r .id factura.json); CUFE=$(jq -r .cufe factura.json)

# 3) Derivados
curl -s -H "Authorization: Bearer $TOKEN" -o factura.pdf http://localhost:8000/api/v1/facturas/$ID/pdf
curl -s -H "Authorization: Bearer $TOKEN" -o factura.xml http://localhost:8000/api/v1/facturas/$ID/xml
curl -s -H "Authorization: Bearer $TOKEN" -o qr.png      http://localhost:8000/api/v1/facturas/$ID/qr
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{}' http://localhost:8000/api/v1/facturas/$ID/correo

# 4) Verificación pública (sin token)
curl -s http://localhost:8000/api/v1/verificacion/$CUFE
```

Resultado esperado del paso 2: `"total": "571200.00"` (480 000 + 19 % de IVA) y `"estado": "aceptada"`.
Lista completa de endpoints: [contrato de la API](../06-contrato-api/endpoints.md).

## 9. Pruebas, lint y calidad

```bash
pytest --cov                                      # unitarias + integración, sin red
ruff check src tests migraciones                  # lint (incluye reglas de seguridad "S")
ruff format --check src tests migraciones         # formato
pip-audit --skip-editable                         # CVE en dependencias
DATABASE_URL=sqlite:///./var/x.db alembic upgrade head   # validar migraciones
```

La CI (`.github/workflows/ci.yml`) corre todo esto y exige cobertura ≥ 85 %.

## 10. Docker Compose (API + PostgreSQL + Mailpit)

```bash
cp .env.example .env                                   # y cambie JWT_SECRETO
export POSTGRES_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(24))")
docker compose up --build
docker compose exec api python -m facturacion.cli crear-admin --email admin@example.com --nombre Admin
```

- Interfaz: <http://localhost:8000/app/> · Correos de prueba (Mailpit): <http://localhost:8025>.
- El contenedor aplica `alembic upgrade head` al iniciar y corre como usuario sin privilegios.
- `docker-compose.yml` **fuerza** `CORREO_MODO=smtp` hacia Mailpit y la `DATABASE_URL` de
  PostgreSQL, por encima de lo que diga el `.env`.
- Los puertos se publican solo en `127.0.0.1`.

## 11. Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| Al arrancar: `JWT_SECRETO debe tener al menos 32 caracteres` | Secreto corto | Genere uno con `secrets.token_urlsafe(48)` |
| Al arrancar: `Faltan variables para Factus: …` | `FACTURACION_MODO=factus` sin credenciales | Complete `FACTUS_*` o vuelva a `directo` |
| Al arrancar: `Faltan variables para habilitación: …` / `Falta DIAN_CERTIFICADO_RUTA` | `DIAN_MODO=habilitacion` incompleto | Vea la [guía de habilitación](../03-habilitacion/guia-habilitacion.md) o vuelva a `simulado` |
| `MAIL_SSL y MAIL_STARTTLS son excluyentes` | Ambos en `true` | 587 → `STARTTLS=true, SSL=false`; 465 → al revés |
| `MAIL_SMTP_AUTH=true requiere MAIL_STARTTLS o MAIL_SSL` | Autenticación activa con ambos en `false` | Active uno de los dos (la clave no puede viajar en claro) |
| `MAIL_SMTP_AUTH=true requiere MAIL_USER y MAIL_PASSWORD` | Falta el usuario o la contraseña | Complételos en `.env` |
| `ModuleNotFoundError: facturacion` | Entorno virtual no activado o sin instalar | `source .venv/bin/activate && pip install -e ".[dev]"` |
| `crear-admin`: "El correo ya está registrado" | Ya existe | Use otro correo o borre `var/facturacion.db` (solo en desarrollo) |
| `crear-admin`: "La contraseña debe tener entre 12 y 128 caracteres" | Política | Use una frase más larga |
| Login: "Correo o contraseña incorrectos" | Credenciales | Revise mayúsculas; el correo se normaliza a minúsculas |
| Login: 429 "Demasiados intentos fallidos" | Limitador (5 por correo o 30 por IP en 5 min) | Espere 5 minutos o reinicie el servidor (el contador está en memoria) |
| La interfaz vuelve al login sola | Token expirado (30 min) o servidor reiniciado con otro `JWT_SECRETO` | Inicie sesión de nuevo |
| 422 "La resolución de numeración no está vigente" / "rango … agotado" | `NUMERACION_FECHA_*` o `NUMERACION_HASTA` | Ajuste el rango en `.env` |
| "Enviar por correo" deshabilitado o 409 | La factura no está `aceptada` | Solo se envían facturas aceptadas |
| Correo: 502 "No fue posible enviar el correo" | Gmail rechazó (clave normal, sin 2FA, puerto) | Use contraseña de aplicación, `smtp.gmail.com:587`, STARTTLS; revise el log |
| El celular no abre el QR | El QR apunta a `localhost` | Sección 6.6: `URL_PUBLICA_BASE` con la IP y `--host 0.0.0.0` |
| 422 en un campo de texto que "se ve bien" | Contiene caracteres de control (p. ej. un tabulador pegado) | Limpie el texto; solo `notas` admite saltos de línea |
| Modo Factus: 502 "El proveedor de facturación no está disponible" | Red, credenciales, Factus caído, timeout | Revise el log (`proveedor_no_disponible`, "Factus rechazó la autenticación"). La factura queda `error_envio` con la referencia `API-…`: verifique en el portal de Factus si se emitió antes de volver a crearla |
| Modo Factus: "Reintentar envío" responde 409 | Por diseño: reenviar podría duplicar una factura que Factus sí emitió | Concilie con la referencia guardada en la respuesta DIAN del detalle |
| Modo Factus: 422 con `"campo": "proveedor"` | Factus o la DIAN rechazaron los datos | Lea los mensajes; p. ej. cantidades con más de 2 decimales |
| Modo Factus: `GET …/xml` responde 404 | Factus no entregó el XML (descarga de mejor esfuerzo) | Descárguelo desde el panel de Factus |
| `docker compose`: "defina POSTGRES_PASSWORD" | Variable no exportada | `export POSTGRES_PASSWORD=…` antes de `up` |
| Puerto 8000 ocupado | Otro proceso | `uvicorn facturacion.asgi:app --port 8001` (y ajuste `URL_PUBLICA_BASE`) |
| `/docs` responde 404 | `ENTORNO=produccion` desactiva Swagger | Use `ENTORNO=desarrollo` localmente |
