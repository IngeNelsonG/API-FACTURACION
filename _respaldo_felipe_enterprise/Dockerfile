# syntax=docker/dockerfile:1
FROM python:3.12-slim AS construccion
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade pip \
 && pip wheel --no-cache-dir --wheel-dir /wheels ".[postgres]"

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 facturacion
WORKDIR /app
COPY --from=construccion /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY alembic.ini ./
COPY migraciones ./migraciones
RUN mkdir -p /app/var /app/certificados && chown -R facturacion:facturacion /app/var
USER facturacion
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/salud')"
CMD ["sh", "-c", "alembic upgrade head && uvicorn facturacion.asgi:app --host 0.0.0.0 --port 8000 --proxy-headers"]
