# Guía de Sustentación - API Facturación DIAN (Grupo 5)

> **Materia:** Computación en la Nube (8vo Semestre)  
> **Integrantes:** Nelson Felipe Gonzales, Daniel Alarcón, Gabriel Bastidas, Michelle Carolina Camargo  
> **Proyecto:** API de Facturación Electrónica para Personas Naturales ante la DIAN  

---

## 1. Resumen del Proyecto y Cumplimiento de Criterios

| Criterio de Evaluación | Porcentaje | Cómo se cumple y demuestra en el código |
| :--- | :---: | :--- |
| **Base Común:** CRUD, JWT y Persistencia SQLite | **40%** | • Autenticación JWT en `POST /login` con decorador `@token_required`.<br>• CRUD completo del recurso `Persona Natural` (GET, POST, PUT, DELETE).<br>• Persistencia en SQLite (`facturacion.db`) con queries seguras parametrizadas (`?`).<br>• 10 pruebas automatizadas pasando al 100% en `pytest`. |
| **Funcionalidad Especial:** DIAN, PDF y Correo | **30%** | • `POST /facturas`: Liquidación de impuestos colombianos (**IVA 19%** y **Gravamen Financiero 4x1000 = 0.4%**).<br>• Generación de **CUFE** (SHA-256) y numeración consecutiva `SETP-XXXX`.<br>• `GET /facturas/<id>/pdf`: Generación al vuelo de PDF profesional con ReportLab.<br>• `POST /facturas/<id>/enviar-correo`: Envío automático al adquiriente vía **Gmail SMTP** con el PDF adjunto.<br>• `DELETE /facturas/<id>`: Anulación oficial de factura. |
| **Sustentación:** Preguntas de Código | **30%** | Respuestas claras y fundamentadas a las preguntas del profesor (ver Sección 3). |

---

## 2. Paso a Paso para la Demostración en Vivo

### Paso 1: Iniciar el servidor
```powershell
python app.py
```
*El servidor arrancará en `http://localhost:5000` e inicializará automáticamente las tablas en SQLite.*

### Paso 2: Ejecutar las pruebas automatizadas
Para demostrar la calidad y cobertura ante el profesor:
```powershell
python -m pytest tests/test_api_facturacion.py -v
```
*(Demuestra 10 tests pasando en verde en menos de 2 segundos).*

---

### Paso 3: Flujo de prueba en vivo (con curl o Postman)

#### 1. Probar ruta pública de salud e información HTTP:
```bash
curl http://localhost:5000/
curl http://localhost:5000/http-info
```

#### 2. Demostrar protección de rutas (Intentar crear sin token → 401 Unauthorized):
```bash
curl -X POST http://localhost:5000/personas \
  -H "Content-Type: application/json" \
  -d '{"nombre": "Prueba Hacker", "cedula": "999"}'
```
*Respuesta:* `401 Unauthorized` ("Falta el token de autorización").

#### 3. Iniciar sesión y obtener el token JWT:
```bash
curl -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{"usuario": "profe", "clave": "cloud2026"}'
```
*Respuesta:* Recibe el token JWT firmado con HS256.

#### 4. Crear una Persona Natural (con el token):
```bash
curl -X POST http://localhost:5000/personas \
  -H "Authorization: Bearer <PEGAR_TOKEN_AQUI>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Gabriel Bastidas",
    "rut": "1098765432-1",
    "cedula": "1098765432",
    "direccion": "Carrera 15 # 85-30, Bogotá",
    "correo": "gabriel.bastidas@example.com",
    "telefono": "3159876543"
  }'
```
*Respuesta:* `201 Created` con el ID generado.

#### 5. Emitir Factura Electrónica con cálculo de tributos DIAN:
```bash
curl -X POST http://localhost:5000/facturas \
  -H "Authorization: Bearer <PEGAR_TOKEN_AQUI>" \
  -H "Content-Type: application/json" \
  -d '{
    "persona_id": 1,
    "concepto": "Servicios de Consultoría e Infraestructura Cloud",
    "subtotal": 2000000
  }'
```
*Respuesta:*
- Subtotal: `$ 2,000,000.00`
- IVA (19%): `$ 380,000.00`
- 4x1000 (0.4%): `$ 8,000.00`
- **Total:** `$ 2,388,000.00`
- Número: `SETP-0001`
- **CUFE:** Hash criptográfico único SHA-256.

#### 6. Descargar el PDF de la Factura:
Abrir en el navegador:
`http://localhost:5000/facturas/1/pdf`

#### 7. Enviar la Factura por Correo Electrónico:
```bash
curl -X POST http://localhost:5000/facturas/1/enviar-correo \
  -H "Authorization: Bearer <PEGAR_TOKEN_AQUI>"
```

---

## 3. Preguntas de Código que Hará el Profesor y Cómo Responderlas

### Pregunta 1: "¿Por qué usaron Flask y no otro framework?"
> **Respuesta:**  
> "Usamos Flask porque es un microframework ligero, predecible y directo para construir APIs RESTful. Nos permite tener control total sobre el ciclo de vida de la petición (`request`), el manejo de respuestas JSON (`jsonify`) y la integración directa con SQLite sin capas innecesarias de abstracción que oscurezcan el funcionamiento de la red."

---

### Pregunta 2: "¿Cómo funciona el decorador `@token_required` que protege los endpoints?"
> **Respuesta:**  
> "En `app.py`, `@token_required` es una función de orden superior decoradora. Envuelve a las funciones de los endpoints (`create_persona`, `create_factura`, etc.).  
> Antes de que el endpoint se ejecute, el decorador extrae el encabezado `Authorization`. Si no viene o no empieza por `Bearer`, corta inmediatamente la petición devolviendo un código `401 Unauthorized`.  
> Luego, mediante `jwt.decode(token, SECRET_KEY, algorithms=['HS256'])`, valida criptográficamente que el token no haya sido manipulado y que su fecha de expiración (`exp`) aún sea válida. Si la firma es correcta, permite que la petición continúe."

---

### Pregunta 3: "¿Cómo evitaron la Inyección SQL en las consultas a la base de datos?"
> **Respuesta:**  
> "Todas las consultas en `app.py` y `database.py` utilizan **consultas parametrizadas** con marcadores de posición `?`, por ejemplo:  
> `cursor.execute('SELECT * FROM personas WHERE id = ?', (persona_id,))`.  
> De esta forma, el motor de SQLite trata los parámetros estrictamente como datos literales y nunca como código SQL ejecutable, neutralizando cualquier intento de inyección SQL."

---

### Pregunta 4: "¿Cómo calcularon los impuestos de la DIAN y qué es el CUFE?"
> **Respuesta:**  
> "En `facturacion_servicio.py`, la función `calcular_impuestos()` aplica las tarifas vigentes en Colombia:  
> 1. **IVA:** 19% sobre la base imponible (`subtotal * 0.19`).  
> 2. **Gravamen a los Movimientos Financieros (4x1000):** 0.4% (`subtotal * 0.004`).  
> 3. **Total:** Subtotal + IVA + 4x1000.  
> 
> El **CUFE** (Código Único de Facturación Electrónica) es la huella digital del documento. Se calcula aplicando el algoritmo hash **SHA-256** sobre la concatenación del número de factura, la fecha, los importes, el NIT del emisor, la cédula del cliente y una clave técnica. Si se llega a modificar un solo centavo de la factura, el CUFE cambia totalmente, garantizando la integridad."

---

### Pregunta 5: "¿Cómo se genera el PDF sin saturar el disco duro del servidor?"
> **Respuesta:**  
> "Utilizamos `io.BytesIO()` en memoria con la librería ReportLab. El documento se construye directamente en la memoria RAM y se despacha al cliente mediante `send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf')`. Al no escribir archivos temporales en el disco, la API es mucho más rápida, limpia y no consume almacenamiento del servidor."

---

### PREGUNTA DE ORO (Diapositiva 36):
### "¿Qué tendrían que cambiar para que 100 personas usaran su API al mismo tiempo?"
> **Respuesta Modelo para 5.0:**  
> "Actualmente, para desarrollo local usamos el servidor integrado de Flask (`app.run()`), el cual maneja peticiones de manera sincrónica y está diseñado para una sola persona. Además, **SQLite bloquea el archivo completo durante las operaciones de escritura** (`INSERT`, `UPDATE`), por lo que 100 usuarios escribiendo al tiempo colapsarían la base de datos.
> 
> Para soportar 100 usuarios concurrentes en producción en la Nube cambiaríamos 4 cosas:
> 
> 1. **Servidor de Aplicaciones WSGI:** Reemplazar el servidor de desarrollo por **Gunicorn** o **uWSGI**, configurando múltiples *workers* (procesos) y *threads* (hilos) para atender peticiones en paralelo.
> 2. **Base de Datos Cliente-Servidor:** Migrar de SQLite a un motor relacional robusto como **PostgreSQL** o **MySQL**, los cuales manejan bloqueo a nivel de fila (*row-level locking*) y alta concurrencia.
> 3. **Pool de Conexiones:** Implementar un *Connection Pool* para que las conexiones a la base de datos se reutilicen y no se abra una conexión por cada petición HTTP.
> 4. **Escalabilidad Horizontal y Balanceador:** Desplegar múltiples réplicas de la API en contenedores (ej. AWS ECS, Google Cloud Run o Kubernetes) detrás de un **Balanceador de Carga (Nginx o Cloud Load Balancer)** que distribuya el tráfico entre las diferentes instancias."
