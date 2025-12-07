#!/bin/bash
#=============================================================
# Portal Cautivo - Script de Inicio con Interfaces Virtuales
#=============================================================

set -e  # Salir ante cualquier error

#-----------------------------------------
# CONFIGURACION DE VARIABLES
#-----------------------------------------
# Interfaz fisica WiFi
IF_PHY="wlo1"

# Interfaz virtual para AP (se creara)
IF_AP="wlo1_ap"

# Interfaz WAN será la física conectada al hotspot
IF_WAN="$IF_PHY"

# Red del portal cautivo
AP_IP="192.168.50.1"
AP_NETWORK="192.168.50.0/24"
DHCP_RANGE_START="192.168.50.2"
DHCP_RANGE_END="192.168.50.50"

# SSID y canal del hotspot móvil al que conectarse
HOTSPOT_SSID="MiHotspotMovil"
HOTSPOT_PASSWORD="password123"

# Directorio del proyecto
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_DIR="$PROJECT_DIR/config"
BACKEND_DIR="$PROJECT_DIR/backend"

# Archivos PID
HOSTAPD_PID="/var/run/hostapd_portal.pid"
DNSMASQ_PID="/var/run/dnsmasq_portal.pid"
PORTAL_PID="/var/run/portal_server.pid"

#-----------------------------------------
# FUNCIONES AUXILIARES
#-----------------------------------------
log_info() {
    echo "[INFO] $(date '+%H:%M:%S') - $1"
}

log_error() {
    echo "[ERROR] $(date '+%H:%M:%S') - $1" >&2
}

log_success() {
    echo "[OK] $(date '+%H:%M:%S') - $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "Este script debe ejecutarse como root"
        exit 1
    fi
}

cleanup_on_error() {
    log_error "Error detectado, limpiando..."
    "$SCRIPT_DIR/stop_portal.sh" 2>/dev/null || true
    exit 1
}

trap cleanup_on_error ERR

#-----------------------------------------
# 1. VERIFICAR REQUISITOS
#-----------------------------------------
check_requirements() {
    log_info "Verificando requisitos del sistema..."
    
    local missing=()
    
    for cmd in iw ip hostapd dnsmasq iptables ipset nmcli python3; do
        if ! command -v "$cmd" &> /dev/null; then
            missing+=("$cmd")
        fi
    done
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Comandos faltantes: ${missing[*]}"
        exit 1
    fi
    
    # Verificar soporte de interfaces virtuales
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
    
    # Asegurar que WiFi está activo
    nmcli radio wifi on
    sleep 2
    
    # Escanear redes disponibles
    nmcli device wifi rescan 2>/dev/null || true
    sleep 2
    
    # Intentar conectar
    if nmcli device wifi connect "$HOTSPOT_SSID" password "$HOTSPOT_PASSWORD" ifname "$IF_PHY"; then
        log_success "Conectado a $HOTSPOT_SSID"
    else
        # Si ya esta conectado, verificar
        if nmcli -t -f NAME connection show --active | grep -q "$HOTSPOT_SSID"; then
            log_info "Ya conectado a $HOTSPOT_SSID"
        else
            log_error "No se pudo conectar a $HOTSPOT_SSID"
            exit 1
        fi
    fi
    
    # Esperar a obtener IP
    sleep 3
    
    # Verificar conectividad
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
    
    # Obtener información de la conexión actual
    local channel_info
    channel_info=$(iw dev "$IF_PHY" info 2>/dev/null | grep "channel" | head -1)
    
    if [[ -z "$channel_info" ]]; then
        log_error "No se pudo obtener información del canal"
        exit 1
    fi
    
    # Extraer numero de canal
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
    
    # Eliminar si ya existe
    if ip link show "$IF_AP" &>/dev/null; then
        log_info "Eliminando interfaz virtual existente..."
        ip link set "$IF_AP" down 2>/dev/null || true
        iw dev "$IF_AP" del 2>/dev/null || true
        sleep 1
    fi
    
    # Crear interfaz virtual tipo AP
    iw dev "$IF_PHY" interface add "$IF_AP" type __ap
    
    if ! ip link show "$IF_AP" &>/dev/null; then
        log_error "No se pudo crear la interfaz virtual"
        exit 1
    fi
    
    # Generar MAC address derivada (cambiar último byte)
    local base_mac
    base_mac=$(cat /sys/class/net/"$IF_PHY"/address)
    local new_mac
    new_mac=$(echo "$base_mac" | sed 's/..$/02/')
    
    # Asignar MAC diferente para evitar conflictos
    ip link set dev "$IF_AP" address "$new_mac"
    
    # Activar interfaz
    ip link set "$IF_AP" up
    
    # Asignar IP
    ip addr add "$AP_IP/24" dev "$IF_AP" 2>/dev/null || true
    
    log_success "Interfaz virtual $IF_AP creada (MAC: $new_mac)"
}

#-----------------------------------------
# 5. GENERAR CONFIGURACION DINÁMICA DE HOSTAPD
#-----------------------------------------
generate_hostapd_config() {
    log_info "Generando configuración de hostapd..."
    
    local config_file="/tmp/hostapd_portal.conf"
    
    cat > "$config_file" << EOF
# Configuración de hostapd generada dinámicamente
# Canal configurado para coincidir con hotspot: $HOTSPOT_CHANNEL

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
# Configuración de dnsmasq para Portal Cautivo
# IMPORTANTE: No usamos address=/#/ porque rompe clientes autenticados

interface=$IF_AP
bind-interfaces

# DHCP
dhcp-range=$DHCP_RANGE_START,$DHCP_RANGE_END,12h
dhcp-option=3,$AP_IP
dhcp-option=6,$AP_IP

# Reenviar DNS a servidores reales
# La redirección al portal la hace iptables, no dnsmasq
server=8.8.8.8
server=8.8.4.4

# Solo estos dominios para detección automática de portal (captive portal detection)
# Android
address=/connectivitycheck.gstatic.com/$AP_IP
address=/clients3.google.com/$AP_IP
# Apple
address=/captive.apple.com/$AP_IP
address=/www.apple.com/$AP_IP
# Windows
address=/www.msftconnecttest.com/$AP_IP
# Firefox
address=/detectportal.firefox.com/$AP_IP

# Logging
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
    
    # Limpiar reglas existentes del portal
    iptables -t nat -F PREROUTING 2>/dev/null || true
    iptables -t nat -F POSTROUTING 2>/dev/null || true
    iptables -F FORWARD 2>/dev/null || true
    
    # Crear ipset para clientes autorizados
    ipset destroy portal_authorized 2>/dev/null || true
    ipset create portal_authorized hash:ip timeout 3600
    
    # Habilitar IP forwarding
    echo 1 > /proc/sys/net/ipv4/ip_forward
    
    # NAT para clientes autorizados
    iptables -t nat -A POSTROUTING -o "$IF_WAN" -j MASQUERADE
    
    # Permitir tráfico de clientes autorizados
    iptables -A FORWARD -m set --match-set portal_authorized src -j ACCEPT
    iptables -A FORWARD -m set --match-set portal_authorized dst -j ACCEPT
    
    # Permitir tráfico relacionado/establecido
    iptables -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT
    
    # Redirección DNS a nuestro dnsmasq
    iptables -t nat -A PREROUTING -i "$IF_AP" -p udp --dport 53 -j DNAT --to-destination "$AP_IP:53"
    iptables -t nat -A PREROUTING -i "$IF_AP" -p tcp --dport 53 -j DNAT --to-destination "$AP_IP:53"
    
    # Redirección HTTP/HTTPS para no autorizados (portal cautivo)
    iptables -t nat -A PREROUTING -i "$IF_AP" -p tcp --dport 80 \
        -m set ! --match-set portal_authorized src \
        -j DNAT --to-destination "$AP_IP:5000"
    
    iptables -t nat -A PREROUTING -i "$IF_AP" -p tcp --dport 443 \
        -m set ! --match-set portal_authorized src \
        -j DNAT --to-destination "$AP_IP:5000"
    
    # Bloquear otros puertos para no autorizados
    iptables -A FORWARD -i "$IF_AP" -m set ! --match-set portal_authorized src -j DROP
    
    log_success "Firewall configurado"
}

#-----------------------------------------
# 8. INICIAR SERVICIOS
#-----------------------------------------
start_services() {
    log_info "Iniciando servicios..."
    
    # Detener servicios existentes si hay
    pkill -f "hostapd.*portal" 2>/dev/null || true
    pkill -f "dnsmasq.*portal" 2>/dev/null || true
    sleep 1
    
    # Iniciar hostapd
    log_info "Iniciando hostapd..."
    hostapd -B -P "$HOSTAPD_PID" "$HOSTAPD_CONF"
    sleep 2
    
    if pgrep -F "$HOSTAPD_PID" &>/dev/null; then
        log_success "hostapd iniciado"
    else
        log_error "hostapd no pudo iniciarse"
        cat /var/log/syslog | tail -20 | grep hostapd
        exit 1
    fi
    
    # Iniciar dnsmasq
    log_info "Iniciando dnsmasq..."
    dnsmasq -C "$DNSMASQ_CONF" --pid-file="$DNSMASQ_PID"
    sleep 1
    
    if pgrep -F "$DNSMASQ_PID" &>/dev/null; then
        log_success "dnsmasq iniciado"
    else
        log_error "dnsmasq no pudo iniciarse"
        exit 1
    fi
    
    # Iniciar servidor del portal
    log_info "Iniciando servidor del portal cautivo..."
    cd "$BACKEND_DIR"
    python3 portal_server.py &
    echo $! > "$PORTAL_PID"
    sleep 2
    
    if pgrep -F "$PORTAL_PID" &>/dev/null; then
        log_success "Portal cautivo iniciado en http://$AP_IP:5000"
    else
        log_error "Portal cautivo no pudo iniciarse"
        exit 1
    fi
}

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
    show_summary
}

main "$@"
