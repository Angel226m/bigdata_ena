FROM python:3.9-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivo de requisitos e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar archivos de la aplicación
COPY *.py .
COPY helpers/ ./helpers/

# Crear directorio para logs
RUN mkdir -p /tmp

# Comando por defecto (se puede sobrescribir)
CMD ["python", "process_data.py"]