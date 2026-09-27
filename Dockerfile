# Imagen de producción de la Bitácora (PWA + bot + tareas programadas).
# Un mismo contenedor base; docker-compose.yml decide qué proceso corre.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=America/Bogota \
    MPLCONFIGDIR=/tmp/matplotlib \
    HF_HOME=/app/data/.cache/huggingface \
    BITACORA_DB=/app/data/bitacora.db \
    USERS_FILE=/app/data/users.json \
    MEDIA_DIR=media \
    PWA_HOST=0.0.0.0 \
    PWA_PORT=8080

# ffmpeg: notas de voz (Whisper) · tesseract: OCR de aretes y recibos ·
# sqlite3: respaldos consistentes · tzdata: hora de la finca.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg tesseract-ocr tesseract-ocr-spa sqlite3 tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY src ./src
COPY scripts ./scripts
COPY docs/GanaderiaJA_Logo.jpg ./docs/GanaderiaJA_Logo.jpg

# Usuario sin privilegios: la app nunca corre como root.
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin bitacora \
    && mkdir -p /app/data /app/media /app/backups \
    && chown -R bitacora:bitacora /app
USER bitacora

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/login', timeout=4).status == 200 else 1)"

CMD ["python", "-m", "src.pwa.app"]
