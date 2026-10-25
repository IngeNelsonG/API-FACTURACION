# Guía de Sustentación - API Facturación DIAN (Grupo 5)

> **Materia:** Cloud Computing Para El Desarrollo De Software
> **Integrantes:** Nelson Felipe Gonzales Gordillo, Daniel Esteban Alarcón Rojas, Gabriel Felipe Bastidas Alvarado, Michelt Carolina Camargo Cobo
> **Proyecto:** API de Facturación Electrónica para Personas Naturales ante la DIAN  

---

## 1. Resumen del Proyecto y Cumplimiento de Criterios

| Criterio de Evaluación | Porcentaje | Cómo se cumple y demuestra en el código |
| :--- | :---: | :--- |
| **Base Común:** CRUD, JWT y Persistencia SQLite | **40%** | • Autenticación JWT en `POST /login` con decorador `@token_required`.<br>• CRUD completo del recurso `Persona Natural` (GET, POST, PUT, DELETE).<br>• Persistencia en SQLite (`facturacion.db`) con queries seguras parametrizadas (`?`).<br>• 10 pruebas automatizadas pasando al 100% en `pytest`. |
| **Funcionalidad Especial:** DIAN, PDF y Correo | **30%** | • `POST /facturas`: Liquidación 100% dinámica de impuestos colombianos (**IVA 19%** y **Gravamen Financiero 4x1000 = 0.4%**).<br>• Generación de **CUFE** (SHA-256) y numeración consecutiva `SETP-XXXX`.<br>• `GET /facturas/<id>/pdf`: Generación al vuelo de PDF profesional con ReportLab.<br>• `POST /facturas/<id>/enviar-correo`: Envío automático al adquiriente (**Burnice White**) vía **Gmail SMTP** con el PDF adjunto.<br>• `DELETE /facturas/<id>`: Anulación oficial de factura. |
| **Sustentación:** Preguntas de Código | **30%** | Respuestas claras y fundamentadas a las preguntas del profesor (ver Sección 4). |

---

## 2. Preparación Previa a la Sustentación

### Paso 1: Iniciar el servidor API
En la terminal del proyecto:
```powershell
python app.py
```
*El servidor arrancará en `http://localhost:5000` e inicializará automáticamente la base de datos `facturacion.db`.*

### Paso 2: Demostrar cobertura de pruebas automatizadas
Para impresionar al profesor antes de empezar:
```powershell
python -m pytest tests/test_api_facturacion.py -v
```
*(Demuestra 10 tests unitarios y de integración pasando en verde al 100% en menos de 3 segundos).*

---

## 3. Demostración en Vivo con Postman (Recomendado)

En la raíz del proyecto se encuentra el archivo **`API Facturación DIAN - Grupo 5 (Cloud).postman_collection.json`**.  
Esta colección ya viene configurada con **variables dinámicas (`{{token}}`, `{{persona_id}}`, `{{factura_id}}`)** y scripts automáticos para que no tengas que copiar ni pegar nada a mano.

### ¿Cómo importar la colección en Postman?
1. Abre **Postman**.
2. Haz clic en el botón superior **Import** (o `Ctrl + O`).
3. Arrastra o selecciona el archivo **`API Facturación DIAN - Grupo 5 (Cloud).postman_collection.json`**.
4. Verás la carpeta **"API Facturación DIAN - Grupo 5 (Cloud)"** con todas las peticiones organizadas secuencialmente.

---

### Secuencia de Sustentación en Postman (Paso a Paso)

#### Bloque 1: Presentación y Seguridad
1. **`01. Salud y Metadatos de la API` (`GET /`):**
   * Muestra el nombre del proyecto, la materia y los integrantes del Grupo 5.
2. **`04. Intentar Crear Persona SIN Token (Esperar 401)` (`POST /personas`):**
   * *Objetivo para el docente:* Demostrar que el decorador `@token_required` bloquea accesos no autorizados con código HTTP `401 Unauthorized`.
3. **`02. Login Exitoso` (`POST /login`):**
   * Envía `profe` y `cloud2026`.
   * Recibe el token JWT con vigencia de 2 horas.
   * *Magia de Postman:* El Test Script integrado guarda automáticamente el token en `{{token}}`.

#### Bloque 2: CRUD de Persona Natural (Cliente: Burnice White)
4. **`05. Crear Persona Natural (Burnice White)` (`POST /personas`):**
   * Crea a **Burnice White** con cédula `1098765432`, RUT `1098765432-1` y correo `burnice.white2305@gmail.com`.
   * Responde `201 Created` y guarda automáticamente el ID en `{{persona_id}}`.
5. **`06. Listar Todas las Personas Naturales` (`GET /personas`):**
   * Muestra la lista completa en SQLite demostrando persistencia.
6. **`07. Consultar Persona por ID` (`GET /personas/{{persona_id}}`):**
   * Consulta el registro puntual del cliente creado.
7. **`08. Actualizar Persona Natural` (`PUT /personas/{{persona_id}}`):**
   * Actualiza teléfono y dirección demostrando el verbo `PUT`.

#### Bloque 3: Facturación DIAN (Funcionalidad Especial)
8. **`09. Emitir Factura DIAN para Burnice White` (`POST /facturas`):**
   * Envía `persona_id`, concepto de servicios cloud y subtotal (`$ 3,500,000 COP`).
   * *Explicar al profesor:*
     * El cálculo es **100% dinámico** (no quemado):
       * **Subtotal:** `$ 3,500,000.00`
       * **IVA (19%):** `$ 665,000.00`
       * **Gravamen 4x1000 (0.4%):** `$ 14,000.00`
       * **TOTAL:** `$ 4,179,000.00 COP`
     * Genera automáticamente el consecutivo `SETP-XXXX`.
     * Genera el **CUFE** criptográfico único mediante **SHA-256**.
9. **`10. Listar Facturas con Adquiriente (JOIN)` (`GET /facturas`):**
   * Demuestra una consulta relacional SQL entre la tabla `facturas` y `personas`.
10. **`12. Descargar PDF Oficial de la Factura` (`GET /facturas/{{factura_id}}/pdf`):**
    * En Postman haz clic en la flecha al lado de *Send* y selecciona **"Send and Download"**, o abre la URL en tu navegador:
      `http://localhost:5000/facturas/1/pdf`
    * Verán el PDF con diseño profesional, tablas corporativas, desglose impositivo y código CUFE.
11. **`13. Enviar Factura al Correo de Burnice White` (`POST /facturas/{{factura_id}}/enviar-correo`):**
    * Despacha el correo con el PDF adjunto hacia `burnice.white2305@gmail.com` usando el servicio Gmail SMTP.
12. **`14. Anular Factura Electrónica` (`DELETE /facturas/{{factura_id}}`):**
    * Cambia el estado de la factura a `ANULADA` demostrando el verbo `DELETE`.

---

## 4. Preguntas de Código que Hará el Profesor y Cómo Responderlas

### Pregunta 1: "¿Por qué usaron Flask y no otro framework?"
> **Respuesta:**  
> "Usamos Flask porque es un microframework ligero, predecible y directo para construir APIs RESTful. Nos permite tener control total sobre el ciclo de vida de la petición (`request`), el manejo de respuestas JSON (`jsonify`) y la integración directa con SQLite sin capas innecesarias de abstracción que oscurezcan el funcionamiento de la red."

---

### Pregunta 2: "¿Cómo funciona el decorador `@token_required` que protege los endpoints?"
> **Respuesta:**  
> "En `app.py`, `@token_required` es una función decoradora de orden superior. Envuelve a las funciones de los endpoints (`create_persona`, `create_factura`, etc.).  
> Antes de ejecutar la lógica de negocio, extrae el encabezado `Authorization`. Si no existe o no tiene el formato `Bearer <token>`, rechaza inmediatamente con `401 Unauthorized`.  
> Luego, llama a `jwt.decode(token, SECRET_KEY, algorithms=['HS256'])` para verificar que la firma digital sea auténtica y que la fecha de expiración (`exp`) siga vigente. Si es válido, inyecta `request.usuario_actual` y permite la ejecución."

---

### Pregunta 3: "¿Cómo evitaron la Inyección SQL en las consultas a la base de datos?"
> **Respuesta:**  
> "Todas las consultas en `app.py` y `database.py` utilizan **consultas parametrizadas** con marcadores de posición `?`, por ejemplo:  
> `cursor.execute('SELECT * FROM personas WHERE id = ?', (persona_id,))`.  
> De esta forma, SQLite compila la estructura de la consulta antes de recibir los valores y trata cualquier entrada del usuario estrictamente como texto literal, neutralizando cualquier intento de inyección de código SQL."

---

### Pregunta 4: "¿Los cálculos de impuestos y la generación de facturas son dinámicos o están quemados?"
> **Respuesta:**  
> "Son **100% dinámicos**. En `facturacion_servicio.py`:
> 1. La función `calcular_impuestos(subtotal)` toma cualquier valor numérico recibido en el cuerpo JSON y aplica las fórmulas tributarias:
>    * `iva = round(subtotal * 0.19, 2)` (19%)
>    * `impuesto_4x1000 = round(subtotal * 0.004, 2)` (0.4%)
>    * `total = round(subtotal + iva + impuesto_4x1000, 2)`
> 2. El número consecutivo se calcula contando los registros existentes en SQLite (`SETP-{total:04d}`).
> 3. El **CUFE** se genera en tiempo real aplicando el algoritmo criptográfico **SHA-256** sobre la cadena concatenada de número, fecha, subtotal, IVA, total, NIT emisor y cédula del adquiriente. Si cambia un solo dígito del subtotal o del cliente, el CUFE resultante es totalmente distinto.
> 4. El PDF y el correo se arman al vuelo extrayendo los datos exactos del cliente y de la factura desde la base de datos."

---

### Pregunta 5: "¿Cómo se genera el PDF sin saturar el disco duro del servidor?"
> **Respuesta:**  
> "Utilizamos `io.BytesIO()` en memoria con la librería ReportLab. El documento se construye directamente en la memoria RAM y se despacha al cliente mediante `send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf')`. Al no escribir archivos temporales en el disco, la API es mucho más rápida, limpia y no consume almacenamiento del servidor."

---

### PREGUNTA DE ORO (Diapositiva 36):
### "¿Qué tendrían que cambiar para que 100 personas usaran su API al mismo tiempo?"
> **Respuesta Modelo para 5.0:**  
> "Actualmente, para desarrollo local usamos el servidor integrado de Flask (`app.run()`), el cual maneja peticiones de manera sincrónica y está diseñado para una sola persona. Además, **SQLite bloquea el archivo completo durante las operaciones de escritura** (`INSERT`, `UPDATE`), por lo que 100 usuarios escribiendo al tiempo colapsarían la base de datos con errores de `database is locked`.
> 
> Para soportar 100 usuarios concurrentes en producción en la Nube cambiaríamos 4 cosas:
> 
> 1. **Servidor de Aplicaciones WSGI:** Reemplazar el servidor de desarrollo por **Gunicorn** o **uWSGI**, configurando múltiples *workers* (procesos) y *threads* (hilos) para atender peticiones en paralelo.
> 2. **Base de Datos Cliente-Servidor:** Migrar de SQLite a un motor relacional robusto como **PostgreSQL** o **MySQL**, los cuales manejan bloqueo a nivel de fila (*row-level locking*) y alta concurrencia.
> 3. **Pool de Conexiones:** Implementar un *Connection Pool* para que las conexiones a la base de datos se reutilicen y no se abra una conexión por cada petición HTTP.
> 4. **Escalabilidad Horizontal y Balanceador:** Desplegar múltiples réplicas de la API en contenedores (ej. AWS ECS, Google Cloud Run o Kubernetes) detrás de un **Balanceador de Carga (Nginx o Cloud Load Balancer)** que distribuya el tráfico entre las diferentes instancias."
