# API de Facturación Electrónica DIAN — Personas Naturales

API RESTful desarrollada en **Python** con **Flask**, **SQLite3 nativo** y **autenticación JWT** para la emisión, cálculo tributario y gestión de facturas electrónicas de venta ante la **DIAN** para **Personas Naturales**.

> **Materia:** Computación en la Nube (8vo Semestre)  
> **Grupo:** Grupo 5  
> **Integrantes:** Nelson Felipe Gonzales, Daniel Alarcón, Gabriel Bastidas, Michelle Carolina Camargo  

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
pip install flask pyjwt reportlab pytest
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

## 🎓 Preparación para la Sustentación
Consulte la **[Guía de Sustentación Grupo 5](guia_sustentacion_grupo5.md)** para repasar las preguntas probables del docente, la demostración paso a paso y la respuesta a la pregunta de concurrencia y escalabilidad de la Diapositiva 36.
