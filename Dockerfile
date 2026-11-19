# Imagen ligera oficial de Python 3.12 para la API Flask (Backend)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar código del backend (incluye fuentes Poppins para PDF)
COPY backend/ ./backend/

# Puerto dinámico (Render inyecta $PORT; por defecto 5000)
ENV PORT=5000
EXPOSE 5000

# Arranque en producción con Gunicorn (inicializa tablas una sola vez con --preload)
CMD ["sh", "-c", "gunicorn --preload --chdir backend --bind 0.0.0.0:${PORT:-5000} --workers 2 --threads 4 --timeout 60 app:app"]

