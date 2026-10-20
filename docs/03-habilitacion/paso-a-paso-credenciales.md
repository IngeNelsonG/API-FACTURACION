# Paso a paso: conseguir y configurar las credenciales

Esta guía explica cómo obtener cada dato que la API necesita para salir del modo
simulado, y dónde configurarlo. **Nunca pegue claves, PIN ni el certificado en un
chat, un issue o un commit**: solo van en el archivo `.env` y en la carpeta
`certificados/`, que git ignora.

> **¿Es un proyecto académico?** El modo simulado (`DIAN_MODO=simulado`) ya muestra
> el flujo completo sin ningún trámite. Los pasos 1 y 2 solo son necesarios para
> hablar con la DIAN de verdad, y exigen una empresa o persona con RUT y un
> certificado pagado.

Los nombres de menús de los portales de la DIAN cambian con frecuencia: si algo no
coincide exactamente, busque la opción equivalente.

---

## 0. Requisito previo: RUT como facturador electrónico

1. Ingrese a <https://www.dian.gov.co> → **Usuario registrado** con su NIT (o cédula) y contraseña.
2. Descargue la **copia del RUT** (PDF) desde *RUT → Consultar/Imprimir RUT*.
3. En la casilla de responsabilidades debe aparecer **52 – Facturador electrónico**.
   Si no aparece, actualice el RUT (en línea o en un punto de atención DIAN) para agregarla.

## 1. Datos del emisor (RUT)

Copie estos datos **exactamente** como aparecen en el RUT; si no coinciden, la DIAN rechaza la factura.

| Dato en el RUT | Variable en `.env` |
|---|---|
| NIT (sin dígito de verificación) | `EMISOR_NIT` |
| Dígito de verificación (DV) | `EMISOR_DV` |
| Razón social (o nombres y apellidos) | `EMISOR_RAZON_SOCIAL` |
| Nombre comercial (si no tiene, repita la razón social) | `EMISOR_NOMBRE_COMERCIAL` |
| Tipo de contribuyente: persona jurídica = `1`, natural = `2` | `EMISOR_TIPO_ORGANIZACION` |
| Responsabilidades fiscales separadas por `;` (p. ej. `O-13;O-15`) o `R-99-PN` si no aplica | `EMISOR_RESPONSABILIDADES` |
| Dirección principal | `EMISOR_DIRECCION` (entre comillas si tiene `#`) |
| Municipio y su código DANE de 5 dígitos (Bogotá `11001`, Medellín `05001`, Cali `76001`) | `EMISOR_CIUDAD`, `EMISOR_CODIGO_MUNICIPIO` |
| Departamento y su código de 2 dígitos | `EMISOR_DEPARTAMENTO`, `EMISOR_CODIGO_DEPARTAMENTO` |
| Correo y teléfono | `EMISOR_EMAIL`, `EMISOR_TELEFONO` |

## 2. Certificado de firma digital (`.p12` / `.pfx`)

1. Elija una entidad de certificación **acreditada por ONAC** (por ejemplo Certicámara,
   GSE, Andes SCD o Camerfirma). La lista vigente está en <https://onac.org.co>.
2. Solicite un **certificado de firma digital para facturación electrónica** a nombre
   de la empresa (persona jurídica) o de la persona natural. Normalmente piden:
   RUT, certificado de existencia y representación legal (si es empresa) y la
   cédula del representante legal. Tiene costo y vigencia de 1 o 2 años.
3. Pida el certificado **en archivo** (`.p12` o `.pfx`), **no en token USB**: la API
   necesita leer el archivo.
4. La entidad le entrega el archivo y una **contraseña**. Guarde ambos en un lugar
   seguro (gestor de contraseñas).
5. Configure:
   - Copie el archivo a `certificados/firma.p12` (git lo ignora).
   - En `.env`: `DIAN_CERTIFICADO_RUTA=certificados/firma.p12` y `DIAN_CERTIFICADO_CLAVE=<la contraseña>`.

## 3. SoftwareID, PIN y TestSetId (portal de habilitación DIAN)

1. Entre a <https://www.dian.gov.co> → **Factura electrónica** → **Habilitación**
   (o directamente al catálogo de habilitación: <https://catalogo-vpfe-hab.dian.gov.co>).
2. Elija ingresar como **Empresa** (o persona natural), tipo de usuario
   *Representante legal*, su tipo y número de documento y el NIT.
   La DIAN envía un **enlace de acceso (token)** al correo registrado en el RUT; ábralo.
3. Si es la primera vez, regístrese como **facturador electrónico** y acepte los términos.
4. Vaya a **Configurar modos de operación** → seleccione **Software propio**.
5. Escriba un **nombre para el software** (p. ej. "API Facturación") y defina un
   **PIN** (un número de 5 dígitos que usted inventa). Guarde.
6. En la lista de modos de operación aparecerán:
   - **Identificador del software (SoftwareID)** → `DIAN_SOFTWARE_ID`
   - El **PIN** que usted escribió → `DIAN_PIN`
   - **TestSetId** (identificador del set de pruebas; puede estar en el detalle del
     software o en *Set de pruebas*) → `DIAN_TEST_SET_ID`
7. El portal también muestra el **rango de numeración de pruebas**. Si es distinto de los
   valores por defecto, configure `NUMERACION_PREFIJO`, `NUMERACION_DESDE`,
   `NUMERACION_HASTA`, `NUMERACION_RESOLUCION`, `NUMERACION_FECHA_DESDE`,
   `NUMERACION_FECHA_HASTA` y `NUMERACION_CLAVE_TECNICA`. Si no lo muestra, deje los
   valores por defecto (`SETP` 990000000–995000000), que son los del ambiente de pruebas.
8. Cambie `DIAN_MODO=habilitacion`.

> **Limitación actual:** el set de pruebas suele pedir también **notas crédito y
> débito**, que la API todavía no emite. Con la API actual puede enviar las facturas
> del set y ver la respuesta de la DIAN; completar el set requiere implementar las
> notas (está en la hoja de ruta).

## 4. Servidor de correo (SMTP)

Elija **una** opción.

### Opción A: pruebas locales con Mailpit (sin cuenta, recomendado para empezar)

`docker compose up` ya incluye Mailpit. Los correos no salen a internet; se ven en
<http://localhost:8025>. No necesita configurar nada más.

### Opción B: Gmail o Google Workspace

1. Active la **verificación en dos pasos** en su cuenta de Google.
2. Vaya a <https://myaccount.google.com/apppasswords>, cree una **contraseña de
   aplicación** llamada "API Facturación" y copie los 16 caracteres.
3. En `.env`:
   ```
   CORREO_MODO=smtp
   CORREO_REMITENTE=sucorreo@gmail.com
   SMTP_HOST=smtp.gmail.com
   SMTP_PUERTO=587
   SMTP_STARTTLS=true
   SMTP_SSL=false
   SMTP_USUARIO=sucorreo@gmail.com
   SMTP_CLAVE=<contraseña de aplicación>
   ```

### Opción C: proveedor transaccional (Brevo, SendGrid, Amazon SES…)

Cree la cuenta, verifique el dominio o el remitente y copie el host, puerto,
usuario y clave SMTP que le da el proveedor en las mismas variables `SMTP_*`.

## 5. Probar que todo quedó bien

1. Reinicie la API (`uvicorn facturacion.asgi:app --reload` o `docker compose up --build`).
   Si falta alguna variable para habilitación, la API **no arranca** y le dice cuáles faltan.
2. En <http://localhost:8000/docs>: inicie sesión, emita una factura y revise
   `estado` y `respuesta_dian`. Con `DIAN_TEST_SET_ID` definido quedará `en_proceso`;
   use **consultar-estado** hasta ver `aceptada` o `rechazada` con los mensajes de la DIAN.
3. Envíe el correo con `POST /api/v1/facturas/{id}/correo` y verifique que llegue.

Si la DIAN rechaza, copie solo los **mensajes de error** (`respuesta_dian.mensajes`),
nunca las claves, y compártalos para ajustar el XML o la firma.
