# ============================================================
# Dockerfile — Empaquetado y Contenerización del Agente RAG
# ============================================================
# Este Dockerfile implementa la fase de "Empaquetado y Contenerización"
# de la metodología de la investigación.
#
# Construir: docker build -t texeira-chatbot .
# Ejecutar:  docker run -p 8000:8000 --env-file .env texeira-chatbot
# ============================================================

# imagen base: Python 3.11 slim (ligera, ideal para producción)
FROM python:3.11-slim

# Variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Instalar dependencias del sistema necesarias para PyPDF y ChromaDB
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements.txt primero (mejora el cache de Docker)
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar todo el código de la aplicación
COPY . .

# Crear directorios necesarios para datos persistentes
RUN mkdir -p /app/documentos_tours /app/chroma_db

# Exponer el puerto del servidor
EXPOSE 8000

# Comando de inicio: ejecutar uvicorn
# --host 0.0.0.0 permite accesos externos al contenedor
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
