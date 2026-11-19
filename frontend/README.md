# FacturaPro — Frontend (React + Vite)

Interfaz web de la API de Facturación Electrónica DIAN (Grupo 5).

## Cómo correrlo

```bash
# 1. Back (en la raíz del repo, otra terminal)
pip install -r requirements.txt     # ahora incluye flask-cors
python app.py                       # http://localhost:5000

# 2. Front
cd frontend
cp .env.example .env                # ajusta VITE_API_URL si Flask quedó en 5001
npm install
npm run dev                         # http://localhost:5173
```

Credenciales de prueba: `profe` / `cloud2026`.

## Cómo funciona el inicio de sesión

1. `LoginForm` valida que vengan usuario y clave y llama a `onSubmit`.
2. `LoginPage` usa `login()` de `AuthContext`.
3. `AuthContext` llama a `authService.login()` → `POST /login` con `{ usuario, clave }`.
4. El back responde `{ token, usuario, rol, expira }`; se guarda en `localStorage`.
5. `httpClient` agrega `Authorization: Bearer <token>` a cada petición
   (lo que exige `@token_required` en `app.py`). Si el back responde 401, cierra la sesión.
6. La sesión se cierra sola cuando llega la hora de `expira` (2 h).
7. `ProtectedRoute` bloquea `/dashboard` (y lo que agregues) si no hay sesión.

## Estructura de carpetas

```
src/
├── main.jsx                 # Punto de entrada: monta <App/> y estilos globales
├── App.jsx                  # Providers globales + router
│
├── api/                     # CAPA DE DATOS: única que habla con Flask
│   ├── httpClient.js        #   fetch base, token, manejo de errores
│   └── authService.js       #   un archivo por recurso: personasService, facturasService...
│
├── context/                 # ESTADO GLOBAL (sesión, tema...)
│   └── AuthContext.jsx
├── hooks/                   # Hooks reutilizables (useAuth, useFetch...)
│   └── useAuth.js
│
├── routes/                  # NAVEGACIÓN
│   ├── AppRouter.jsx        #   mapa de rutas
│   ├── ProtectedRoute.jsx   #   requiere sesión
│   └── PublicRoute.jsx      #   solo sin sesión (login)
│
├── pages/                   # VISTAS: una carpeta por pantalla / ruta
│   ├── Login/
│   │   ├── LoginPage.jsx            # orquesta: conecta lógica + piezas
│   │   ├── LoginPage.module.css
│   │   └── components/              # piezas que SOLO usa esta vista
│   │       ├── BrandPanel.jsx
│   │       ├── LoginForm.jsx
│   │       └── SpaceScene.jsx
│   ├── Dashboard/
│   └── NotFound/
│
├── components/              # COMPARTIDO entre varias vistas
│   ├── ui/                  #   piezas genéricas sin lógica de negocio (Button, Input, Modal, Table)
│   ├── brand/               #   identidad visual (Logo)
│   └── icons/               #   íconos SVG
│
├── utils/                   # Funciones puras (storage, formato de moneda COP, fechas)
├── styles/                  # variables.css (tokens) + global.css
└── assets/                  # Imágenes, fuentes locales
```

### Jerarquía y reglas

Las dependencias van en una sola dirección, de arriba hacia abajo:

```
pages  →  components  →  hooks/context  →  api  →  utils
```

- **Una `page` puede usar todo**, pero nadie importa una `page`, salvo `AppRouter`.
- **`components/ui` no conoce la API ni el contexto.** Solo recibe props.
  Así `Button` sirve igual en el login que en facturas.
- **Solo `api/` hace `fetch`.** Si mañana cambia la URL o el formato del token, se toca un archivo.
- **Un componente nace dentro de su página** (`pages/X/components/`). Cuando lo necesita
  una segunda vista, se sube a `src/components/`.
- **Cada componente lleva su `.module.css` al lado.** Así las clases no chocan entre vistas.
- **Las variables de color, radios y sombras van en `styles/variables.css`.** No se escriben
  colores sueltos en los componentes.
- **Para importar se usa el alias `@/`** (`import Input from '@/components/ui/Input/Input'`).

### Cómo agregar el módulo de Facturas (ejemplo)

```
api/facturasService.js          → getFacturas, crearFactura, anularFactura, descargarPdf
pages/Facturas/
├── FacturasPage.jsx            → lista (GET /facturas)
├── FacturaDetallePage.jsx      → detalle (GET /facturas/:id)
└── components/
    ├── FacturasTable.jsx
    └── FacturaForm.jsx
routes/AppRouter.jsx            → <Route path="/facturas" .../> dentro de <ProtectedRoute/>
```
