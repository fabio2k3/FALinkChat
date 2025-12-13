#!/bin/sh

echo "[gateway] Configurando red..."
ip link set eth0 up
ip addr add 10.0.0.1/24 dev eth0

echo "[gateway] IP forwarding..."
echo 1 > /proc/sys/net/ipv4/ip_forward

echo "[gateway] NAT + redirección al portal cautivo..."
# Redirigir todo el tráfico HTTP al portal
iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8080
# Hacer NAT hacia afuera (para clientes autenticados)
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

echo "[gateway] Usuarios configurados desde entorno:"
echo "USER1=$USER1 PASS1=$PASS1"
echo "USER2=$USER2 PASS2=$PASS2"

echo "[gateway] Iniciando portal cautivo..."
python3 /app/test_portal.py

echo "[gateway] Portal detenido, entrando en shell..."
/bin/sh
