FROM python:3.9-slim

# Instalar herramientas necesarias
RUN apt-get update && apt-get install -y \
    openssl \
    iptables \
    ipset \
    iproute2 \
    curl \
    wget \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de aplicación
WORKDIR /app

# ============================================================================
# COPIAR DESDE EL CONTEXTO DE BUILD (raíz del proyecto)
# El contexto se especifica en el comando docker build desde la raíz
# ============================================================================

# Copiar archivos del proyecto
COPY backend/ ./backend/
COPY config/ ./config/
COPY html/ ./html/
COPY scripts/ ./scripts/

# Dar permisos de ejecución
RUN chmod +x /app/scripts/*.sh 2>/dev/null || true

# Crear directorio de certificados
RUN mkdir -p /app/config/certs

# El servidor escuchará en puerto 80 (HTTP) y 443 (HTTPS)
EXPOSE 80 443

# Comando por defecto: ejecutar el servidor del portal
CMD ["python3", "/app/backend/main.py"]