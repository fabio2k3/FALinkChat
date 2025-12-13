FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    openssl iptables ipset iproute2 curl wget net-tools \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Las rutas son relativas a captive-portal (donde ejecutamos docker build)
COPY backend ./backend
COPY config ./config
COPY html ./html
COPY scripts ./scripts

RUN chmod +x ./scripts/*.sh || true
RUN mkdir -p ./config/certs

EXPOSE 80 443

CMD ["python3", "./backend/main.py"]