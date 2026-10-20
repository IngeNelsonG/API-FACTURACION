# Desarrollo, pruebas y despliegue

## Requisitos

Python 3.12+. Docker opcional.

## Inicio rápido (modo simulado)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # y cambie JWT_SECRETO
python -m facturacion.cli crear-admin --email admin@example.com --nombre "Admin"
uvicorn facturacion.asgi:app --reload
```

Abra la interfaz web en http://localhost:8000/app/ e inicie sesión con el administrador,
o use Swagger en http://localhost:8000/docs con **Authorize** con el correo y la contraseña del
administrador y pruebe `POST /api/v1/facturas`. Los correos simulados quedan en
`var/correos/*.eml`.

## Pruebas y calidad

```bash
pytest --cov                       # unitarias + integración (sin red)
ruff check src tests migraciones   # lint (incluye reglas de seguridad Bandit "S")
ruff format src tests migraciones
pip-audit --skip-editable          # vulnerabilidades en dependencias
```

CI (`.github/workflows/ci.yml`) ejecuta todo lo anterior, exige cobertura ≥ 85 % y
comprueba que las migraciones aplican y revierten.

## Migraciones

En desarrollo el esquema se crea al arrancar. En producción solo con Alembic:

```bash
alembic upgrade head
alembic revision --autogenerate -m "descripcion"   # tras cambiar persistencia/modelos.py
```

## Docker

```bash
cp .env.example .env
export POSTGRES_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(24))")
docker compose up --build
docker compose exec api python -m facturacion.cli crear-admin --email admin@example.com --nombre Admin
```

Mailpit muestra los correos en http://localhost:8025. La imagen corre como usuario
sin privilegios y aplica migraciones al iniciar.

## Configuración

Todas las variables están documentadas en [`.env.example`](../../.env.example) y
validadas en `src/facturacion/configuracion.py`. Con `ENTORNO=produccion`:
Swagger se desactiva, se exige `JWT_SECRETO` propio, se envía HSTS y el esquema
no se crea automáticamente.
