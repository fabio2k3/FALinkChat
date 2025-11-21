#!/usr/bin/env bash
set -euo pipefail

IF_AP="wlo1"

echo "[+] Deteniendo modo AP..."

# 🔹 Parar hostapd y dnsmasq
sudo pkill hostapd  
sudo pkill dnsmasq   

# 🔹 Quitar regla FORWARD que apunta a captive_portal
sudo iptables -D FORWARD -i "$IF_AP" -j captive_portal 2>/dev/null || true

# 🔹 Limpiar reglas y borrar la cadena captive_portal
sudo iptables -F captive_portal 2>/dev/null || true
sudo iptables -X captive_portal 2>/dev/null || true

# 🔹 Limpiar NAT
sudo iptables -t nat -F

# 🔹 Destruir ipset
sudo ipset destroy AUTHORIZED 2>/dev/null || true

# 🔹 Quitar IP estática de la interfaz AP
sudo ip addr flush dev "$IF_AP"

# 🔹 Restaurar gestión por NetworkManager
sudo nmcli device set "$IF_AP" managed yes
sudo nmcli radio wifi on

echo "[+] Modo AP desactivado. Sistema restaurado."
