# Convenciones

- Python 3.12, `from __future__ import annotations`, tipado completo.
- Nombres y docstrings en español; comentarios solo para explicar el porqué.
- Ruff (línea 100) con reglas `E,F,W,I,B,UP,S,N,SIM,RUF`; `N818` ignorada (excepciones `ErrorXxx`).
- Excepciones de dominio con mensaje seguro para el cliente (`ErrorNegocio`, `EstadoNoPermitido`);
  las de adaptadores (`ErrorDian`, `ErrorFirma`, `ErrorCorreo`) se traducen en `api/errores.py`.
- Esquemas de entrada heredan de `EsquemaEntrada` (`extra="forbid"`) y llevan límites de longitud/formato.
- Tests: `tests/unitarias/` (sin BD ni red) y `tests/integracion/` (TestClient + SQLite temporal).
  Fixtures en `tests/conftest.py` (`cliente`, `auth_facturador`, `auth_admin`, `factura_valida`).
- Decisiones relevantes → ADR en `docs/decisions/`.
