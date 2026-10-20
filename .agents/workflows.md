# Flujos de trabajo

```bash
pip install -e ".[dev]"
pytest --cov                                  # debe pasar todo, cobertura ≥ 85 %
ruff check src tests migraciones && ruff format --check src tests migraciones
pip-audit --skip-editable
DATABASE_URL=sqlite:///./var/x.db alembic upgrade head   # validar migraciones
uvicorn facturacion.asgi:app --reload         # Swagger en /docs
python -m facturacion.cli crear-admin --email a@b.co --nombre A   # pide contraseña
```

Prueba manual rápida: crear admin → login en Swagger → `POST /api/v1/facturas` →
`GET .../pdf` → `POST .../correo` (revisar `var/correos/`) → abrir la URL del QR.
