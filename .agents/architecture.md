# Arquitectura (resumen para agentes)

Monolito modular, puertos y adaptadores. Detalle: `docs/04-arquitectura/arquitectura.md`.

- `src/facturacion/dominio/`: código puro (sin FastAPI/SQLAlchemy). Montos en `Decimal`, ROUND_HALF_UP.
- `ubl/generador.py`: el orden de elementos sigue el XSD UBL 2.1; `UBLExtension[2]` queda vacío para la firma.
- Puertos: `firma/puertos.py`, `dian/puertos.py`, `correo/puertos.py`, `proveedor/puertos.py`.
  Firma/DIAN/correo tienen adaptador real y simulado; el proveedor solo `ClienteFactus`
  (en tests: `httpx.MockTransport` o `ProveedorFalso`).
- `arranque.py` es el **único** lugar que elige adaptadores según la configuración.
- `servicios/facturacion.py` orquesta; las rutas (`api/rutas/`) solo traducen HTTP ↔ servicio.
  Modo directo: `commit` en `error_envio` antes de transmitir, luego actualiza. Modo factus
  (`_emitir_con_proveedor`): registro pendiente `PEND-…` → rechazo lo borra (422), fallo lo
  deja `error_envio` con la referencia (502), éxito → `aceptada`. No reintentar facturas del proveedor.
- `web/`: SPA estática en `/app/` y `/verificar/{cufe}`; DOM solo con `textContent`, CSP
  `_CSP_WEB` en `api/middleware.py`. Un test prohíbe `innerHTML` y similares.
- Persistencia: `persistencia/modelos.py` + Alembic (`migraciones/`). Cambiar un modelo exige
  una migración nueva (`alembic revision --autogenerate`).
- La factura se guarda como instantánea JSON (`FacturaRegistro.datos`) para regenerar PDF/QR.
- Estados: `aceptada`, `rechazada`, `en_proceso` (set de pruebas o pendiente del proveedor), `error_envio`.
