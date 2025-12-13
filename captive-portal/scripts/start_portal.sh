<<<<<<< Updated upstream
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
=======
#!/bin/bash
#=============================================================
# Portal Cautivo - Script de Inicio con HTTP/HTTPS
#=============================================================

set -e

#-----------------------------------------
# CONFIGURACION DE VARIABLES
#-----------------------------------------
IF_PHY="wlo1"
IF_AP="wlo1_ap"
IF_WAN="$IF_PHY"

AP_IP="192.168.50.1"
AP_NETWORK="192.168.50.0/24"
DHCP_RANGE_START="192.168.50.2"
DHCP_RANGE_END="192.168.50.50"

HOTSPOT_SSID="MiHotspotMovil"
HOTSPOT_PASSWORD="password123"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_DIR="$PROJECT_DIR/config"
BACKEND_DIR="$PROJECT_DIR/backend"

HOSTAPD_PID="/var/run/hostapd_portal.pid"
DNSMASQ_PID="/var/run/dnsmasq_portal.pid"
PORTAL_PID="/var/run/portal_main.pid"
>>>>>>> Stashed changes

# 🔹 NAT para compartir Internet
sudo iptables -t nat -A POSTROUTING -o "$IF_WAN" -j MASQUERADE

# 🔹 Permitir DNS y HTTP desde AP
sudo iptables -A INPUT -i "$IF_AP" -p udp --dport 53 -j ACCEPT
sudo iptables -A INPUT -i "$IF_AP" -p tcp --dport 80 -j ACCEPT

<<<<<<< Updated upstream
# 🔹 ipset para IPs autorizadas
sudo ipset destroy AUTHORIZED 2>/dev/null || true
sudo ipset create AUTHORIZED hash:ip family inet timeout 7200
=======
log_success() {
    echo "[✓] $(date '+%H:%M:%S') - $1"
}
>>>>>>> Stashed changes

# 🔹 Reglas del chain captive_portal
#   - Solo deja pasar tráfico de IPs autorizadas
sudo iptables -A captive_portal -m set --match-set AUTHORIZED src -j RETURN
# Todo lo demás queda bloqueado por la política DROP

# 🔹 Redirección HTTP al portal Python (puerto 8080)
sudo iptables -t nat -A PREROUTING -i "$IF_AP" -p tcp --dport 80 -j REDIRECT --to-port 8080

# 🔹 Permitir tráfico de clientes autorizados hacia WAN
sudo iptables -A FORWARD -i "$IF_AP" -m set --match-set AUTHORIZED src -o "$IF_WAN" -j ACCEPT
sudo iptables -A FORWARD -i "$IF_WAN" -o "$IF_AP" -m state --state ESTABLISHED,RELATED -j ACCEPT

<<<<<<< Updated upstream
# 🔹 Guardar reglas iptables
sudo netfilter-persistent save

# 🔹 Iniciar hostapd y dnsmasq
sudo hostapd -B "$(pwd)/config/hostapd/hostapd.conf"
sudo dnsmasq -C "$(pwd)/config/dnsmasq/dnsmasq.conf"

# 🔹 Iniciar servidor Python
sudo python3 backend/portal_server.py &

echo "[+] Modo AP activado. Gateway: ${AP_IP%/*}"
=======
#-----------------------------------------
# 1. VERIFICAR REQUISITOS
#-----------------------------------------
check_requirements() {
    log_info "Verificando requisitos del sistema..."
    
    local missing=()
    
    for cmd in iw ip hostapd dnsmasq iptables ipset nmcli python3 openssl; do
        if ! command -v "$cmd" &> /dev/null; then
            missing+=("$cmd")
        fi
    done
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Comandos faltantes: ${missing[*]}"
        log_info "Instálalos con: sudo apt-get install ${missing[*]}"
        exit 1
    fi
    
    if ! iw phy phy0 info | grep -q "AP"; then
        log_error "La tarjeta WiFi no soporta modo AP"
        exit 1
    fi
    
    log_success "Todos los requisitos verificados"
}

#-----------------------------------------
# 2. CONECTAR A HOTSPOT MÓVIL
#-----------------------------------------
connect_to_hotspot() {
    log_info "Conectando a hotspot móvil: $HOTSPOT_SSID"
    
    nmcli radio wifi on
    sleep 2
    
    nmcli device wifi rescan 2>/dev/null || true
    sleep 2
    
    if nmcli device wifi connect "$HOTSPOT_SSID" password "$HOTSPOT_PASSWORD" ifname "$IF_PHY"; then
        log_success "Conectado a $HOTSPOT_SSID"
    else
        if nmcli -t -f NAME connection show --active | grep -q "$HOTSPOT_SSID"; then
            log_info "Ya conectado a $HOTSPOT_SSID"
        else
            log_error "No se pudo conectar a $HOTSPOT_SSID"
            exit 1
        fi
    fi
    
    sleep 3
    
    if ping -c 1 -W 3 8.8.8.8 &>/dev/null; then
        log_success "Conectividad a Internet verificada"
    else
        log_error "Sin conectividad a Internet"
        exit 1
    fi
}

#-----------------------------------------
# 3. OBTENER CANAL DEL HOTSPOT
#-----------------------------------------
get_hotspot_channel() {
    log_info "Obteniendo canal del hotspot..."
    
    local channel_info
    channel_info=$(iw dev "$IF_PHY" info 2>/dev/null | grep "channel" | head -1)
    
    if [[ -z "$channel_info" ]]; then
        log_error "No se pudo obtener información del canal"
        exit 1
    fi
    
    HOTSPOT_CHANNEL=$(echo "$channel_info" | awk '{print $2}')
    
    if [[ -z "$HOTSPOT_CHANNEL" || ! "$HOTSPOT_CHANNEL" =~ ^[0-9]+$ ]]; then
        log_error "Canal inválido: $HOTSPOT_CHANNEL"
        exit 1
    fi
    
    log_success "Canal del hotspot: $HOTSPOT_CHANNEL"
}

#-----------------------------------------
# 4. CREAR INTERFAZ VIRTUAL AP
#-----------------------------------------
create_virtual_interface() {
    log_info "Creando interfaz virtual: $IF_AP"
    
    if ip link show "$IF_AP" &>/dev/null; then
        log_info "Eliminando interfaz virtual existente..."
        ip link set "$IF_AP" down 2>/dev/null || true
        iw dev "$IF_AP" del 2>/dev/null || true
        sleep 1
    fi
    
    iw dev "$IF_PHY" interface add "$IF_AP" type __ap
    
    if ! ip link show "$IF_AP" &>/dev/null; then
        log_error "No se pudo crear la interfaz virtual"
        exit 1
    fi
    
    local base_mac
    base_mac=$(cat /sys/class/net/"$IF_PHY"/address)
    local new_mac
    new_mac=$(echo "$base_mac" | sed 's/..$/02/')
    
    ip link set dev "$IF_AP" address "$new_mac"
    ip link set "$IF_AP" up
    ip addr add "$AP_IP/24" dev "$IF_AP" 2>/dev/null || true
    
    log_success "Interfaz virtual $IF_AP creada (MAC: $new_mac)"
}

#-----------------------------------------
# 5. GENERAR CONFIGURACIÓN DINÁMICA DE HOSTAPD
#-----------------------------------------
generate_hostapd_config() {
    log_info "Generando configuración de hostapd..."
    
    local config_file="/tmp/hostapd_portal.conf"
    
    cat > "$config_file" << EOF
interface=$IF_AP
driver=nl80211
ssid=MiRed_Captive
hw_mode=g
channel=$HOTSPOT_CHANNEL
wmm_enabled=1
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=portal1234
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP
ieee80211n=1
country_code=ES
ieee80211d=1
EOF

    log_success "Configuración hostapd generada en $config_file"
    HOSTAPD_CONF="$config_file"
}

#-----------------------------------------
# 6. GENERAR CONFIGURACIÓN DINÁMICA DE DNSMASQ
#-----------------------------------------
generate_dnsmasq_config() {
    log_info "Generando configuración de dnsmasq..."
    
    local config_file="/tmp/dnsmasq_portal.conf"
    
    cat > "$config_file" << EOF
interface=$IF_AP
bind-interfaces

# DHCP
dhcp-range=$DHCP_RANGE_START,$DHCP_RANGE_END,12h
dhcp-option=3,$AP_IP
dhcp-option=6,$AP_IP

# DNS
server=8.8.8.8
server=8.8.4.4

# Detección automática de portal cautivo
address=/connectivitycheck.gstatic.com/$AP_IP
address=/clients3.google.com/$AP_IP
address=/captive.apple.com/$AP_IP
address=/www.apple.com/$AP_IP
address=/www.msftconnecttest.com/$AP_IP
address=/detectportal.firefox.com/$AP_IP

log-queries
log-dhcp
EOF

    log_success "Configuración dnsmasq generada en $config_file"
    DNSMASQ_CONF="$config_file"
}

#-----------------------------------------
# 7. CONFIGURAR FIREWALL (iptables + ipset)
#-----------------------------------------
configure_firewall() {
    log_info "Configurando firewall..."
    
    iptables -t nat -F PREROUTING 2>/dev/null || true
    iptables -t nat -F POSTROUTING 2>/dev/null || true
    iptables -F FORWARD 2>/dev/null || true
    
    # Crear ipset para autorizados (timeout 2 horas)
    ipset destroy AUTHORIZED 2>/dev/null || true
    ipset create AUTHORIZED hash:ip timeout 7200
    
    echo 1 > /proc/sys/net/ipv4/ip_forward
    
    # NAT para autorizados
    iptables -t nat -A POSTROUTING -o "$IF_WAN" -j MASQUERADE
    
    # Permitir tráfico de autorizados
    iptables -A FORWARD -m set --match-set AUTHORIZED src -j ACCEPT
    iptables -A FORWARD -m set --match-set AUTHORIZED dst -j ACCEPT
    
    iptables -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT
    
    # Redireccionar DNS
    iptables -t nat -A PREROUTING -i "$IF_AP" -p udp --dport 53 -j DNAT --to-destination "$AP_IP:53"
    iptables -t nat -A PREROUTING -i "$IF_AP" -p tcp --dport 53 -j DNAT --to-destination "$AP_IP:53"
    
    # Redireccionar HTTP/HTTPS a puerto 5000 (servidor manual) para no autorizados
    iptables -t nat -A PREROUTING -i "$IF_AP" -p tcp --dport 80 \
        -m set ! --match-set AUTHORIZED src \
        -j DNAT --to-destination "$AP_IP:5000"
    
    iptables -t nat -A PREROUTING -i "$IF_AP" -p tcp --dport 443 \
        -m set ! --match-set AUTHORIZED src \
        -j DNAT --to-destination "$AP_IP:5001"
    
    # Bloquear otros puertos para no autorizados
    iptables -A FORWARD -i "$IF_AP" -m set ! --match-set AUTHORIZED src -j DROP
    
    log_success "Firewall configurado"
}

#-----------------------------------------
# 8. INICIAR SERVICIOS
#-----------------------------------------
start_services() {
    log_info "Iniciando servicios..."
    
    pkill -f "hostapd.*portal" 2>/dev/null || true
    pkill -f "dnsmasq.*portal" 2>/dev/null || true
    sleep 1
    
    log_info "Iniciando hostapd..."
    hostapd -B -P "$HOSTAPD_PID" "$HOSTAPD_CONF"
    sleep 2
    
    if pgrep -F "$HOSTAPD_PID" &>/dev/null; then
        log_success "hostapd iniciado"
    else
        log_error "hostapd no pudo iniciarse"
        exit 1
    fi
    
    log_info "Iniciando dnsmasq..."
    dnsmasq -C "$DNSMASQ_CONF" --pid-file="$DNSMASQ_PID"
    sleep 1
    
    if pgrep -F "$DNSMASQ_PID" &>/dev/null; then
        log_success "dnsmasq iniciado"
    else
        log_error "dnsmasq no pudo iniciarse"
        exit 1
    fi
    
    log_info "Iniciando servidor del portal cautivo (HTTP/HTTPS)..."
    cd "$BACKEND_DIR"
    python3 main.py &
    echo $! > "$PORTAL_PID"
    sleep 3

    if pgrep -F "$PORTAL_PID" &>/dev/null; then
        log_success "Servidor del portal iniciado correctamente"
    else
        log_error "El servidor del portal no pudo iniciarse"
        exit 1
    fi
}

#-----------------------------------------
# FUNCIÓN PRINCIPAL
#-----------------------------------------
main() {
    check_root
    check_requirements
    connect_to_hotspot
    get_hotspot_channel
    create_virtual_interface
    generate_hostapd_config
    generate_dnsmasq_config
    configure_firewall
    start_services
    
    echo ""
    echo "╔════════════════════════════════════════════════════════════════════╗"
    echo "║                  ✓ PORTAL CAUTIVO OPERATIVO                       ║"
    echo "╠════════════════════════════════════════════════════════════════════╣"
    echo "║                                                                    ║"
    echo "║  CARACTERÍSTICAS IMPLEMENTADAS:                                   ║"
    echo "║  ✓ Detección automática de portal cautivo (iOS/Android/Windows)   ║"
    echo "║  ✓ Servidor HTTPS con certificado autofirmado                    ║"
    echo "║  ✓ Control de suplantación de IPs (MAC address binding)          ║"
    echo "║  ✓ Monitoreo periódico de sesiones                               ║"
    echo "║                                                                    ║"
    echo "║  ENDPOINTS:                                                        ║"
    echo "║  • HTTP:  http://192.168.50.1/login                              ║"
    echo "║  • HTTPS: https://192.168.50.1/login                             ║"
    echo "║                                                                    ║"
    echo "║  CREDENCIALES DEFAULT:                                            ║"
    echo "║  • Usuario: admin                                                 ║"
    echo "║  • Password: admin123                                             ║"
    echo "║                                                                    ║"
    echo "║  Para detener: sudo bash scripts/stop_portal.sh                   ║"
    echo "║                                                                    ║"
    echo "╚════════════════════════════════════════════════════════════════════╝"
    echo ""
}

main "$@"
>>>>>>> Stashed changes
