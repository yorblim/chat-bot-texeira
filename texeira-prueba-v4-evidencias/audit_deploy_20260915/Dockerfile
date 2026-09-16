# ============================================================
# DOCKERFILE - AGENTE CONVERSACIONAL TEXEIRA TRAVEL TOUR (v4)
# ============================================================
# Imagen base ligera con Python 3.11
FROM python:3.11-slim

# Evitar prompts interactivos y buffering de logs
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    ANONYMIZED_TELEMETRY=False

WORKDIR /app

# Instalar dependencias del sistema mínimas para compilación y SQLite
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente, base vectorial y catálogos canónicos
COPY src/ ./src/
COPY data/ ./data/
COPY chroma_f1_confirmado_20260915_db/ ./chroma_f1_confirmado_20260915_db/
COPY app.py .
COPY verified_routes.py .
COPY handoff_support.py .
COPY trial_support.py .
COPY database.py .
COPY chat_ui.py .
COPY admin_dashboard.py .
COPY operational_metrics.py .
COPY advisor_entry.py .
COPY whatsapp_entry.py .

# Crear directorios para logs y persistencia de bases de datos
RUN mkdir -p logs

# Exponer puertos: 8021 (Chat/API), 8022 (Webhook WhatsApp), 8023 (Asesores/Métricas)
EXPOSE 8021 8022 8023

# Verificación de salud del servicio principal
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://127.0.0.1:8021/chat || exit 1

# Comando por defecto: arrancar el servidor principal de Chat/API
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8021"]
