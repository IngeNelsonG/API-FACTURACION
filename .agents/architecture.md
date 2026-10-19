# Arquitectura (resumen para agentes)

Monolito modular, puertos y adaptadores. Detalle: `docs/04-arquitectura/arquitectura.md`.

- `src/facturacion/dominio/`: código puro (sin FastAPI/SQLAlchemy). Montos en `Decimal`, ROUND_HALF_UP.
- `ubl/generador.py`: el orden de elementos sigue el XSD UBL 2.1; `UBLExtension[2]` queda vacío para la firma.
- Puertos: `firma/puertos.py`, `dian/puertos.py`, `correo/puertos.py`. Cada uno tiene adaptador real y simulado.
- `arranque.py` es el **único** lugar que elige adaptadores según la configuración.
- `servicios/facturacion.py` orquesta; las rutas (`api/rutas/`) solo traducen HTTP ↔ servicio.
- Persistencia: `persistencia/modelos.py` + Alembic (`migraciones/`). Cambiar un modelo exige
  una migración nueva (`alembic revision --autogenerate`).
- La factura se guarda como instantánea JSON (`FacturaRegistro.datos`) para regenerar PDF/QR.
- Estados: `aceptada`, `rechazada`, `en_proceso` (set de pruebas), `error_envio` (reintentable).
