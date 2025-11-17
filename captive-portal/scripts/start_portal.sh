#!/usr/bin/env bash
set -euo pipefail

# Interfaces a ajustar
IF_AP="wlo1"              # Interfaz WiFi del AP
IF_WAN="enxda299959de87"  # Interfaz con Internet (por ejemplo tethering USB)
AP_IP="192.168.50.1/24"   # IP estática del AP (laptop) como gateway

echo "[+] Iniciando modo AP..."

# Apagar WiFi cliente y preparar interfaz AP
sudo nmcli radio wifi off
sudo rfkill unblock wifi
sudo nmcli device set "$IF_AP" managed no
sudo ip addr flush dev "$IF_AP"
sudo ip addr add "$AP_IP" dev "$IF_AP"
sudo ip link set "$IF_AP" up

# Habilitar IP forwarding en kernel
sudo sysctl -w net.ipv4.ip_forward=1

# Limpiar reglas previas y configurar NAT
sudo iptables -t nat -F
sudo iptables -F FORWARD

# Mascarade (NAT) de salida para compartir Internet
sudo iptables -t nat -A POSTROUTING -o "$IF_WAN" -j MASQUERADE

# Cadena custom para el portal cautivo
sudo iptables -N captive_portal

# Permitir DNS y HTTP al AP
sudo iptables -A INPUT -i "$IF_AP" -p udp --dport 53 -j ACCEPT
sudo iptables -A INPUT -i "$IF_AP" -p tcp --dport 80 -j ACCEPT

# Reenviar todo el tráfico del AP a la cadena captive_portal
sudo iptables -A FORWARD -i "$IF_AP" -j captive_portal

# Redirigir todas las peticiones HTTP al servidor del portal
sudo iptables -t nat -A PREROUTING -i "$IF_AP" -p tcp --dport 80 \
     -j DNAT --to-destination "${AP_IP%/*}:80"

# Crear ipset para almacenar IPs autorizadas
sudo ipset create AUTHORIZED hash:ip family inet timeout 7200

# Reglas del chain captive_portal
sudo iptables -A captive_portal -m set ! --match-set AUTHORIZED src -j REJECT
sudo iptables -A captive_portal -j SET --add-set AUTHORIZED src --exist
sudo iptables -A captive_portal -j ACCEPT

# Guardar reglas de iptables
sudo netfilter-persistent save

# Iniciar hostapd y dnsmasq
sudo systemctl unmask hostapd
sudo systemctl enable hostapd
sudo systemctl start hostapd
sudo systemctl restart dnsmasq

# Iniciar servidor Python en segundo plano
sudo python3 backend/portal_server.py &

echo "[+] Modo AP activado. Gateway: ${AP_IP%/*}"
