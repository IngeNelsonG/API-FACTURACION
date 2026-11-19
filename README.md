# API de Facturación Electrónica DIAN — Personas Naturales

API RESTful desarrollada en **Python 3.10+** (probada en **3.12** / CI) con **Flask**, **SQLite / PostgreSQL** y **autenticación JWT** para la emisión, cálculo tributario y gestión de facturas electrónicas de venta ante la **DIAN** para **Personas Naturales**, junto con su interfaz web en **React + Vite** (`Node.js 18+`, probada en **Node 22**).

> **Materia:** Cloud Computing Para El Desarrollo De Software
> **Grupo:** Grupo 5  
> **Integrantes:** Nelson Felipe Gonzales Gordillo, Daniel Esteban Alarcón Rojas, Gabriel Felipe Bastidas Alvarado, Michelt Carolina Camargo Cobo

---

## 📦 Requisitos y Dependencias

- **Backend:** Python `3.10+` (`Flask`, `PyJWT`, `flask-cors`, `reportlab`, `gunicorn`, `psycopg2-binary`, `pytest` — listados en `requirements.txt`).
- **Frontend:** Node.js `18+` y `npm` (`react`, `react-router-dom`, `vite` — listados en `frontend/package.json`).
- **Base de datos:**
  - **Local / Pruebas:** SQLite (`facturacion.db`) automático cuando no se define `DATABASE_URL`.
  - **Nube (Producción):** PostgreSQL persistente cuando se define `DATABASE_URL` (p. ej. Render PostgreSQL o Neon).

---

## 🚀 Inicio Rápido (Desarrollo Local)

### 1. Crear y activar el entorno virtual
En Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
*(En Linux / macOS: `python3 -m venv .venv && source .venv/bin/activate`)*

### 2. Instalar dependencias
```powershell
pip install -r requirements.txt
```

### 3. Configurar variables de entorno
Copie el archivo de ejemplo (sin claves reales en Git) y ajústelo si lo desea:
```powershell
cp .env.example .env
```

### 4. Iniciar la API y carga inicial de datos
```powershell
python backend/app.py
```
El servidor arrancará en `http://localhost:5000` e invocará `init_db()`, que crea las tablas (`usuarios`, `personas`, `facturas`) e inserta automáticamente los datos semilla si la base está vacía:
- Usuario administrador inicial: `profe` / `cloud2026` (rol `admin`).
- Cliente de prueba inicial: `Juan Carlos Pérez Gómez` (CC `1020304050`).

### 5. Ejecutar las pruebas automatizadas
```powershell
python -m pytest tests/test_api_facturacion.py -v
```

### 6. Pruebas interactivas con Postman
Importe el archivo `API Facturación DIAN - Grupo 5 (Cloud).postman_collection.json` directamente en Postman. Incluye todos los endpoints con método, ruta, propósito, autenticación, cuerpo, respuestas de éxito/error y scripts automáticos para `{{baseUrl}}`, `{{token}}`, `{{persona_id}}` y `{{factura_id}}`.

### 7. Frontend React (Alba / FacturaPro)
```powershell
cd frontend
cp .env.example .env
npm install
npm run dev
```
Abre `http://localhost:5173` e inicia sesión con `profe` / `cloud2026` o regístrate como cliente desde la página de inicio. La API permite el origen del front mediante **CORS** (`CORS_ORIGINS`). Ver `frontend/README.md` para la estructura de carpetas.

---

## 🐳 Ejecución con Docker (Backend)

```bash
docker build -t alba-facturacion-api .
docker run -p 5000:5000 --env-file .env alba-facturacion-api
```

---

## ☁️ Despliegue en la Nube (Render - Free Tier con Blueprint)

El repositorio incluye [`render.yaml`](render.yaml) listo para desplegar en **Render** con HTTPS, base de datos persistente y CORS configurado:

1. **`alba-facturacion-g5-db`**: Base de datos **PostgreSQL** persistente (plan `free`).
2. **`alba-facturacion-g5-api`**: Backend **Docker** (`Dockerfile` + `gunicorn`), conectado a `DATABASE_URL` con `SECRET_KEY` generada automáticamente y `CORS_ORIGINS` apuntando al frontend.
3. **`alba-facturacion-g5-web`**: Frontend React compilado como **Static Site** gratuito con `VITE_API_URL` enlazada automáticamente a la URL pública de la API y rewrite `/* -> /index.html`.

En el panel de Render: **New → Blueprint** → selecciona este repositorio en GitHub → **Apply**. Si Render asigna un subdominio distinto al frontend, actualiza `CORS_ORIGINS` en las variables de entorno del backend con la URL HTTPS exacta del Static Site.

---

## 📋 Endpoints de la API

### 1. Autenticación y Estado
| Método | Ruta | Acceso | Descripción |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | Público | Información general y salud de la API |
| `GET` | `/health` | Público | Healthcheck para Docker / Render (`{"status": "ok"}`) |
| `POST` | `/login` | Público | Login con `{"usuario": "profe", "clave": "cloud2026"}` → Retorna JWT |
| `POST` | `/registro` | Público | Crea usuario con rol `cliente` y registra la persona asociada |

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
| `GET` | `/facturas` | **Protegido** | Lista facturas con datos del cliente (clientes ven solo las propias) |
| `GET` | `/facturas/<id>` | **Protegido** | Consulta detalle de factura por ID (`403` si pertenece a otro cliente) |
| `POST` | `/facturas` | **Protegido** | Emite factura: total = subtotal + **IVA 19%**; informa el **4x1000** (0.4% del total) que retendrá el banco, sin sumarlo; genera consecutivo `SETP-XXXX` y **CUFE** SHA-256 |
| `DELETE` | `/facturas/<id>` | **Protegido** | Anula una factura electrónica emitida (`403` si pertenece a otro cliente) |
| `PATCH` | `/facturas/<id>/pagar` | **Protegido** | Marca una factura emitida como **PAGADA** (409 si está anulada o ya pagada; `403` si es de otro cliente) |
| `GET` | `/facturas/<id>/pdf` | **Protegido** | Descarga en memoria la representación gráfica en **PDF oficial** (`403` si pertenece a otro cliente) |
| `POST` | `/facturas/<id>/enviar-correo` | **Protegido** | Envía la factura al correo del cliente vía **Gmail SMTP** con el PDF adjunto (`403` si es de otro cliente) |

---

## 📧 Envío de Correos (Resend HTTPS / Gmail SMTP)

- **En Render Free Tier (recomendado):** los puertos SMTP salientes (25/465/587) están bloqueados en el plan gratuito, por lo que puedes configurar `RESEND_API_KEY` (API HTTPS gratuita) para envío real.
- **En ejecución local (Gmail SMTP):**
  1. Active la **Verificación en 2 pasos** en su cuenta de Google.
  2. Genere una **Contraseña de aplicación** de 16 caracteres en [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
  3. Configure su `.env`:
     ```env
     SMTP_HOST=smtp.gmail.com
     SMTP_PORT=587
     SMTP_EMAIL=su_correo@gmail.com
     SMTP_PASSWORD=abcd efgh ijkl mnop
     ```
*(Si no se configuran credenciales de Resend ni de Gmail, el sistema simula el envío con respuesta exitosa sin detener el servicio).*

---

