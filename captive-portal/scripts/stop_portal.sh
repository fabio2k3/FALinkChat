#!/bin/bash
#=============================================================
# Portal Cautivo - Script de Parada
#=============================================================

set -e

#-----------------------------------------
# CONFIGURACION
#-----------------------------------------
IF_AP="wlo1_ap"
IF_PHY="wlo1"
AP_IP="192.168.50.1"

HOSTAPD_PID="/var/run/hostapd_portal.pid"
DNSMASQ_PID="/var/run/dnsmasq_portal.pid"
PORTAL_PID="/var/run/portal_server.pid"

#-----------------------------------------
# FUNCIONES
#-----------------------------------------
log_info() {
    echo "[INFO] $(date '+%H:%M:%S') - $1"
}

log_success() {
    echo "[OK] $(date '+%H:%M:%S') - $1"
}

log_error() {
    echo "[ERROR] $(date '+%H:%M:%S') - $1" >&2
}

stop_service() {
    local name=$1
    local pidfile=$2
    
    if [[ -f "$pidfile" ]]; then
        local pid
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            sleep 1
            # Forzar si sigue vivo
            kill -9 "$pid" 2>/dev/null || true
            log_success "$name detenido (PID: $pid)"
        fi
        rm -f "$pidfile"
    fi
    
    # Matar por nombre tambien
    pkill -f "$name.*portal" 2>/dev/null || true
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "Este script debe ejecutarse como root"
        exit 1
    fi
}

#-----------------------------------------
# MAIN
#-----------------------------------------
main() {
    check_root
    
    log_info "Deteniendo portal cautivo..."
    
    # =============================================
    # PASO 1: Detener servicios
    # =============================================
    log_info "Deteniendo servicios..."
    
    stop_service "portal_server" "$PORTAL_PID"
    stop_service "dnsmasq" "$DNSMASQ_PID"
    stop_service "hostapd" "$HOSTAPD_PID"
    
    # Matar cualquier proceso restante
    pkill -f "portal_server.py" 2>/dev/null || true
    pkill hostapd 2>/dev/null || true
    pkill -f "dnsmasq.*portal" 2>/dev/null || true
    
    # =============================================
    # PASO 2: Limpiar reglas de firewall
    # =============================================
    log_info "Limpiando reglas de firewall..."
    
    # Limpiar cadenas
    iptables -t nat -F PREROUTING 2>/dev/null || true
    iptables -t nat -F POSTROUTING 2>/dev/null || true
    iptables -F FORWARD 2>/dev/null || true
    
    # Restaurar politica por defecto
    iptables -P FORWARD ACCEPT 2>/dev/null || true
    
    log_success "Reglas de firewall limpiadas"
    
    # =============================================
    # PASO 3: Destruir ipset
    # =============================================
    log_info "Eliminando ipset..."
    
    ipset destroy portal_authorized 2>/dev/null || true
    # Tambien el viejo por si acaso
    ipset destroy AUTHORIZED 2>/dev/null || true
    
    log_success "ipset eliminado"
    
    # =============================================
    # PASO 4: Eliminar interfaz virtual
    # =============================================
    log_info "Eliminando interfaz virtual $IF_AP..."
    
    if ip link show "$IF_AP" &>/dev/null; then
        # Quitar IP
        ip addr del "$AP_IP/24" dev "$IF_AP" 2>/dev/null || true
        # Desactivar
        ip link set "$IF_AP" down 2>/dev/null || true
        # Eliminar
        iw dev "$IF_AP" del 2>/dev/null || true
        log_success "Interfaz $IF_AP eliminada"
    else
        log_info "Interfaz $IF_AP no existe"
    fi
    
    # =============================================
    # PASO 5: Limpiar archivos temporales
    # =============================================
    log_info "Limpiando archivos temporales..."
    
    rm -f /tmp/hostapd_portal.conf
    rm -f /tmp/dnsmasq_portal.conf
    
    log_success "Archivos temporales eliminados"
    
    # =============================================
    # PASO 6: Restaurar NetworkManager
    # =============================================
    log_info "Restaurando NetworkManager..."
    
    # Asegurar que WiFi sigue activo
    nmcli radio wifi on 2>/dev/null || true
    
    # Si la conexion al hotspot se perdio, intentar reconectar
    if ! nmcli -t -f DEVICE,STATE dev | grep -q "$IF_PHY:connected"; then
        log_info "Reconectando WiFi..."
        nmcli device wifi rescan 2>/dev/null || true
    fi
    
    log_success "NetworkManager restaurado"
}

main "$@"
