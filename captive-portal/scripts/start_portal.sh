#!/usr/bin/env bash
set -euo pipefail

# Interfaces
IF_AP="wlo1"
IF_WAN="enxda47e69f9fe2"
AP_IP="192.168.50.1/24"

echo "[+] Iniciando modo AP..."

# 🔹 Apagar WiFi cliente y preparar interfaz AP
sudo nmcli radio wifi off
sudo rfkill unblock wifi
sudo nmcli device set "$IF_AP" managed no
sudo ip addr flush dev "$IF_AP"
sudo ip addr add "$AP_IP" dev "$IF_AP"
sudo ip link set "$IF_AP" up

# 🔹 Habilitar IP forwarding
sudo sysctl -w net.ipv4.ip_forward=1

# 🔹 Limpiar reglas previas y NAT
sudo iptables -t nat -F
sudo iptables -F FORWARD

# 🔹 Política por defecto: bloquear todo
sudo iptables -P FORWARD DROP

# 🔹 Quitar regla FORWARD antigua y borrar cadena si existe
sudo iptables -D FORWARD -i "$IF_AP" -j captive_portal 2>/dev/null || true
sudo iptables -F captive_portal 2>/dev/null || true
sudo iptables -X captive_portal 2>/dev/null || true

# 🔹 Crear nueva cadena y asociarla a FORWARD
sudo iptables -N captive_portal
sudo iptables -A FORWARD -i "$IF_AP" -j captive_portal

# 🔹 NAT para compartir Internet
sudo iptables -t nat -A POSTROUTING -o "$IF_WAN" -j MASQUERADE

# 🔹 Permitir DNS y HTTP desde AP
sudo iptables -A INPUT -i "$IF_AP" -p udp --dport 53 -j ACCEPT
sudo iptables -A INPUT -i "$IF_AP" -p tcp --dport 80 -j ACCEPT

# 🔹 ipset para IPs autorizadas
sudo ipset destroy AUTHORIZED 2>/dev/null || true
sudo ipset create AUTHORIZED hash:ip family inet timeout 7200

# 🔹 Reglas del chain captive_portal
#   - Solo deja pasar tráfico de IPs autorizadas
sudo iptables -A captive_portal -m set --match-set AUTHORIZED src -j RETURN
# Todo lo demás queda bloqueado por la política DROP

# 🔹 Redirección HTTP al portal Python (puerto 8080)
sudo iptables -t nat -A PREROUTING -i "$IF_AP" -p tcp --dport 80 -j REDIRECT --to-port 8080

# 🔹 Permitir tráfico de clientes autorizados hacia WAN
sudo iptables -A FORWARD -i "$IF_AP" -m set --match-set AUTHORIZED src -o "$IF_WAN" -j ACCEPT
sudo iptables -A FORWARD -i "$IF_WAN" -o "$IF_AP" -m state --state ESTABLISHED,RELATED -j ACCEPT

# 🔹 Guardar reglas iptables
sudo netfilter-persistent save

# 🔹 Iniciar hostapd y dnsmasq
sudo hostapd -B "$(pwd)/config/hostapd/hostapd.conf"
sudo dnsmasq -C "$(pwd)/config/dnsmasq/dnsmasq.conf"

# 🔹 Iniciar servidor Python
sudo python3 backend/portal_server.py &

echo "[+] Modo AP activado. Gateway: ${AP_IP%/*}"