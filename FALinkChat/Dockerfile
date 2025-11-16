FROM python:3.9-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    python3-tk \
    net-tools \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar todas las carpetas manteniendo la estructura
COPY src/ ./src/
COPY interface/ ./interface/
COPY tests/ ./tests/

# Configurar Python path para que encuentre los módulos
ENV PYTHONPATH="/app/src:/app/interface:/app/tests"

# Comando por defecto - ejecutar desde src
CMD ["python", "src/main.py", "--iface", "eth0"]
