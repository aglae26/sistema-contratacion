# 1. Imagen base
FROM python:3.10-slim

# 2. Directorio de trabajo
WORKDIR /app

# 3. CORREGIDO: Instalación de dependencias del sistema para WeasyPrint con los nombres correctos
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libpango-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# 4. Copiar requerimientos
COPY requirements.txt .

# 5. Instalar librerías de Python
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiar el resto del código del backend
COPY . .

# 7. Exponer puerto
EXPOSE 8000

# 8. Arrancar el servidor
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]