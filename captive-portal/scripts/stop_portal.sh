#!/usr/bin/env bash
set -euo pipefail

IF_AP="wlo1"
DNSMASQ_CONF_ORIG="/etc/dnsmasq.conf.orig"

echo "[+] Deteniendo modo AP..."

# Parar los servicios
sudo systemctl stop hostapd
sudo systemctl stop dnsmasq

# Limpiar reglas iptables
sudo iptables -t nat -F
sudo iptables -F FORWARD
sudo iptables -X captive_portal || true
sudo ipset destroy AUTHORIZED || true

# Quitar la IP estática de la interfaz AP
sudo ip addr flush dev "$IF_AP"

# Reactivar la gestión de la interfaz WiFi por NetworkManager
sudo nmcli device set "$IF_AP" managed yes
sudo nmcli radio wifi on

# Restaurar dnsmasq original si hay respaldo
if [ -f "$DNSMASQ_CONF_ORIG" ]; then
  echo "[+] Restaurando configuración original de dnsmasq"
  sudo mv "$DNSMASQ_CONF_ORIG" /etc/dnsmasq.conf
  sudo systemctl restart dnsmasq
else
  echo "[-] No se encontró respaldo de dnsmasq para restaurar"
fi

echo "[+] Modo AP desactivado."
