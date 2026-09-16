# ============================================================
# DOCKERFILE - WEBHOOK WHATSAPP TEXEIRA TRAVEL TOUR (v4)
# Objetivo: servidor continuo con volumen persistente (WhatsApp únicamente).
# Cloud Run/scale-to-zero no soportados por la arquitectura actual.
# Messenger aplazado — no incluir FB_PAGE_ACCESS_TOKEN.
# ============================================================
FROM python:3.11-slim

# Variables de entorno base — NO activar WhatsApp aquí; se inyecta en producción.
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ANONYMIZED_TELEMETRY=False

WORKDIR /app

# Dependencias del sistema mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------
# DESCARGAR modelo de embeddings durante el BUILD (una sola vez).
# IMPORTANTE: el bloque python -c debe estar en UNA SOLA LINEA
# para evitar que Docker interprete 'from' como instruccion FROM.
# ---------------------------------------------------------------
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'); print('Modelo OK')"

# Ahora activar modo offline (el modelo ya está en caché de la imagen)
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    ALLOW_CLOUD_RUN=1

# Copiar código fuente — solo módulos necesarios para el webhook
COPY src/ ./src/
COPY data/ ./data/
COPY chroma_f1_confirmado_20260915_db/ ./chroma_f1_confirmado_20260915_db/
COPY app.py .
COPY runtime_settings.py .
COPY verified_routes.py .
COPY handoff_support.py .
COPY trial_support.py .
COPY database.py .
COPY chat_ui.py .
COPY admin_dashboard.py .
COPY operational_metrics.py .
COPY advisor_entry.py .
COPY whatsapp_entry.py .

# Directorio para bases de datos de estado (montar volumen externo aquí)
RUN mkdir -p /app/state /app/logs

# Cloud Run expone el puerto via variable PORT (default 8080 en Cloud Run)
EXPOSE 8080

# Health check: /healthz no expone datos privados
# Cloud Run usa su propio health check; esto es para docker local
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://127.0.0.1:${PORT:-8080}/healthz || exit 1

# ENTRADA: solo el webhook WhatsApp. Cloud Run inyecta PORT; uvicorn lo lee.
# Paneles y chat NO se exponen públicamente.
CMD exec uvicorn whatsapp_entry:app --host 0.0.0.0 --port ${PORT:-8080}
