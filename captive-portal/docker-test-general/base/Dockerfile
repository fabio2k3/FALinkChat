FROM debian:bookworm-slim

# Instalar herramientas necesarias
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    iproute2 \
    iptables \
    ipset \
    openssl \
    curl \
    wget \
    net-tools \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

CMD ["/bin/bash"]
