# API de Facturación Electrónica DIAN — Personas Naturales

API RESTful desarrollada en **Python** con **Flask**, **SQLite3 nativo** y **autenticación JWT** para la emisión, cálculo tributario y gestión de facturas electrónicas de venta ante la **DIAN** para **Personas Naturales**.

> **Materia:** Cloud Computing Para El Desarrollo De Software
> **Grupo:** Grupo 5  
> **Integrantes:** Nelson Felipe Gonzales Gordillo, Daniel Esteban Alarcón Rojas, Gabriel Felipe Bastidas Alvarado, Michelt Carolina Camargo Cobo

---

## 🚀 Inicio Rápido

### 1. Crear y activar el entorno virtual
En Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
*(En Linux / macOS: `python -m venv .venv && source .venv/bin/activate`)*

### 2. Instalar dependencias
```powershell
pip install -r requirements.txt
```

### 3. Configurar variables de entorno (Opcional)
Copie el archivo de ejemplo para configurar Gmail SMTP si desea enviar correos reales:
```powershell
cp .env.example .env
```

### 4. Iniciar la API
```powershell
python app.py
```
El servidor arrancará en `http://localhost:5000` e inicializará automáticamente la base de datos `facturacion.db`.

### 5. Ejecutar las pruebas automatizadas
```powershell
python -m pytest tests/test_api_facturacion.py -v
```

### 6. Pruebas interactivas con Postman
Importe el archivo `API Facturación DIAN - Grupo 5 (Cloud).postman_collection.json` directamente en Postman. Incluye todas las peticiones organizadas secuencialmente con scripts automáticos que gestionan el token JWT y las variables dinámicas de clientes y facturas.

---

## 📋 Endpoints de la API

### 1. Autenticación y Estado
| Método | Ruta | Acceso | Descripción |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | Público | Información general y salud de la API |
| `POST` | `/login` | Público | Login con `{"usuario": "profe", "clave": "cloud2026"}` → Retorna JWT |

### 2. CRUD Persona Natural (Recurso Principal)
| Método | Ruta | Acceso | Descripción |
| :--- | :--- | :--- | :--- |
| `GET` | `/personas` | Público | Lista todas las personas naturales registradas |
| `GET` | `/personas/<id>` | Público | Consulta detalle de una persona por ID |
| `POST` | `/personas` | **Protegido** | Registra una persona natural (`nombre`, `rut`, `cedula`, `direccion`, `correo`, `telefono`) |
| `PUT` | `/personas/<id>` | **Protegido** | Actualiza los datos de una persona |
| `DELETE` | `/personas/<id>` | **Protegido** | Elimina una persona natural de la base de datos |

### 3. Facturación DIAN (Funcionalidad Especial)
| Método | Ruta | Acceso | Descripción |
| :--- | :--- | :--- | :--- |
| `GET` | `/facturas` | Público | Lista todas las facturas emitidas con datos del cliente |
| `GET` | `/facturas/<id>` | Público | Consulta detalle de factura por ID |
| `POST` | `/facturas` | **Protegido** | Emite factura liquidando **IVA 19%**, **4x1000 (0.4%)**, genera consecutivo `SETP-XXXX` y **CUFE** SHA-256 |
| `DELETE` | `/facturas/<id>` | **Protegido** | Anula una factura electrónica emitida |
| `GET` | `/facturas/<id>/pdf` | Público | Descarga en memoria la representación gráfica en **PDF oficial** |
| `POST` | `/facturas/<id>/enviar-correo` | **Protegido** | Envía la factura al correo del cliente vía **Gmail SMTP** con el PDF adjunto |

---

## 📧 Configuración de Gmail SMTP (Envío de Correos)

Para enviar facturas a correos electrónicos reales:
1. Active la **Verificación en 2 pasos** en su cuenta de Google.
2. Genere una **Contraseña de aplicación** de 16 caracteres en [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
3. Configure su `.env`:
   ```env
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_EMAIL=su_correo@gmail.com
   SMTP_PASSWORD=abcd efgh ijkl mnop
   ```
*(Si no se configuran credenciales, el sistema simula el envío con respuesta exitosa sin detener el servicio).*

---

