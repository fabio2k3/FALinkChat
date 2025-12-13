"""
fw_manager.py - Gestor de Firewall y Control de Acceso

Maneja:
1. Autorización de IPs en ipset
2. Verificación de autorización
3. Control de suplantación de IPs vinculando MAC address a IP autorizada
4. Eliminación de IPs
"""

import subprocess
import os
from typing import Dict, Tuple, Optional


# Dict global para almacenar la relación IP -> (usuario, MAC address)
# Estructura: {ip: {"user": nombre_usuario, "mac": aa:bb:cc:dd:ee:ff, "timestamp": 123456}}
AUTHORIZED_SESSIONS = {}


def get_client_mac(client_ip: str) -> Optional[str]:
    """
    Obtiene la MAC address de un cliente usando arp o ip command.
    
    Args:
        client_ip: IP del cliente
        
    Returns:
        MAC address en formato xx:xx:xx:xx:xx:xx o None si no se encuentra
    """
    try:
        # Método 1: Usar 'ip neigh' (más moderno)
        result = subprocess.run(
            ["ip", "neigh", "show", client_ip],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and result.stdout:
            # Formato: "192.168.50.2 dev wlo1_ap lladdr aa:bb:cc:dd:ee:ff STALE"
            parts = result.stdout.split()
            for i, part in enumerate(parts):
                if part == 'lladdr' and i + 1 < len(parts):
                    mac = parts[i + 1].upper()
                    print(f"[INFO] MAC obtenida para {client_ip}: {mac}")
                    return mac
        
        # Método 2: Usar 'arp' como alternativa
        result = subprocess.run(
            ["arp", "-n", client_ip],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and result.stdout:
            # Formato: "Address                  HWtype  HWaddress           Flags Mask            Iface"
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 3:
                    mac = parts[2].upper()
                    print(f"[INFO] MAC obtenida para {client_ip}: {mac}")
                    return mac
        
        print(f"[WARN] No se pudo obtener MAC para {client_ip}")
        return None
        
    except subprocess.TimeoutExpired:
        print(f"[WARN] Timeout obteniendo MAC para {client_ip}")
        return None
    except Exception as e:
        print(f"[ERROR] Obteniendo MAC para {client_ip}: {e}")
        return None


def add_authorized(ip: str, username: str = "unknown") -> bool:
    """
    Agrega una IP al ipset AUTHORIZED y registra la sesión.
    
    Además de agregar la IP al firewall, también:
    1. Obtiene la MAC address del cliente
    2. Registra la sesión en AUTHORIZED_SESSIONS para verificación posterior
    3. Vincula usuario -> IP -> MAC para detección de suplantación
    
    Args:
        ip: IP a autorizar
        username: Usuario autenticado
        
    Returns:
        True si se autorizó exitosamente, False en caso contrario
    """
    try:
        # Obtener MAC address del cliente
        mac = get_client_mac(ip)
        
        if not mac:
            print(f"[WARN] No se pudo obtener MAC para {ip}, pero se autoriza IP")
            mac = "UNKNOWN"
        
        # Agregar IP al ipset con timeout de 2 horas (7200 segundos)
        subprocess.run(
            ["sudo", "ipset", "add", "AUTHORIZED", ip, "timeout", "7200"],
            check=True,
            capture_output=True
        )
        
        # Registrar la sesión
        AUTHORIZED_SESSIONS[ip] = {
            "user": username,
            "mac": mac,
            "timestamp": __import__('time').time()
        }
        
        print(f"[OK] IP {ip} autorizada para usuario '{username}' con MAC {mac}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] No se pudo agregar IP {ip} a ipset: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Autorizando IP {ip}: {e}")
        return False


def remove_authorized(ip: str) -> bool:
    """
    Quita una IP del ipset AUTHORIZED y de las sesiones.
    
    Args:
        ip: IP a remover
        
    Returns:
        True si se removió exitosamente, False en caso contrario
    """
    try:
        subprocess.run(
            ["sudo", "ipset", "del", "AUTHORIZED", ip],
            check=True,
            capture_output=True
        )
        
        # Remover de sesiones
        if ip in AUTHORIZED_SESSIONS:
            user = AUTHORIZED_SESSIONS[ip]["user"]
            del AUTHORIZED_SESSIONS[ip]
            print(f"[OK] IP {ip} (usuario '{user}') removida de ipset")
        
        return True
        
    except subprocess.CalledProcessError:
        print(f"[WARN] IP {ip} no estaba en ipset")
        return False
    except Exception as e:
        print(f"[ERROR] Removiendo IP {ip}: {e}")
        return False


def is_authorized(ip: str) -> bool:
    """
    Verifica si una IP está autorizada en el ipset.
    
    Args:
        ip: IP a verificar
        
    Returns:
        True si está autorizada, False si no
    """
    try:
        result = subprocess.run(
            ["sudo", "ipset", "test", "AUTHORIZED", ip],
            capture_output=True
        )
        return result.returncode == 0
        
    except Exception as e:
        print(f"[ERROR] Verificando autorización de {ip}: {e}")
        return False


def is_ip_spoofed(ip: str) -> bool:
    """
    Verifica si una IP está siendo suplantada.
    
    Detección de suplantación:
    1. Verifica que la IP esté en AUTHORIZED_SESSIONS
    2. Obtiene la MAC actual del cliente
    3. Compara con la MAC registrada en el login
    4. Si no coinciden, es un spoofing
    
    Args:
        ip: IP a verificar
        
    Returns:
        True si se detecta suplantación, False si es legítima
    """
    
    # Si la IP no está en nuestro registro, no es suplantación
    # (simplemente no está autorizada)
    if ip not in AUTHORIZED_SESSIONS:
        return False
    
    session = AUTHORIZED_SESSIONS[ip]
    registered_mac = session["mac"]
    
    # Si la MAC registrada es UNKNOWN, no podemos verificar
    if registered_mac == "UNKNOWN":
        print(f"[INFO] No se puede verificar suplantación de {ip} (MAC desconocida)")
        return False
    
    # Obtener MAC actual
    current_mac = get_client_mac(ip)
    
    if not current_mac:
        print(f"[WARN] No se pudo obtener MAC actual de {ip} para verificar suplantación")
        return False
    
    # Comparar MACs (case-insensitive)
    if current_mac.upper() != registered_mac.upper():
        print(f"[ALERT] SUPLANTACIÓN DETECTADA en {ip}!")
        print(f"  MAC registrada: {registered_mac}")
        print(f"  MAC actual:     {current_mac}")
        print(f"  Usuario: {session['user']}")
        
        # Remover la IP para proteger la red
        remove_authorized(ip)
        
        return True
    
    return False


def get_session_info(ip: str) -> Optional[Dict]:
    """
    Obtiene información de la sesión de una IP autorizada.
    
    Args:
        ip: IP a consultar
        
    Returns:
        Dict con información de la sesión o None si no existe
    """
    return AUTHORIZED_SESSIONS.get(ip)


def get_all_authorized() -> Dict[str, Dict]:
    """
    Obtiene todas las sesiones autorizadas.
    
    Returns:
        Dict con todas las sesiones
    """
    return AUTHORIZED_SESSIONS.copy()


def verify_all_sessions() -> int:
    """
    Verifica todas las sesiones para detectar suplanaciones.
    
    Se ejecuta periódicamente para detectar:
    - IPs con MAC diferente (suplantación)
    - IPs que ya no están en la red (MAC no encontrada)
    
    Returns:
        Número de suplanaciones detectadas
    """
    
    spoofed_count = 0
    ips_to_check = list(AUTHORIZED_SESSIONS.keys())
    
    print(f"[INFO] Verificando {len(ips_to_check)} sesiones activas...")
    
    for ip in ips_to_check:
        if is_ip_spoofed(ip):
            spoofed_count += 1
    
    if spoofed_count > 0:
        print(f"[ALERT] Se detectaron {spoofed_count} intentos de suplantación")
    else:
        print(f"[OK] Todas las sesiones verificadas correctamente")
    
    return spoofed_count


def print_session_stats():
    """
    Imprime estadísticas de las sesiones autorizadas.
    """
    import time
    
    print("\n" + "="*60)
    print("ESTADÍSTICAS DE SESIONES AUTORIZADAS")
    print("="*60)
    print(f"Total de sesiones activas: {len(AUTHORIZED_SESSIONS)}")
    print()
    
    for ip, session in AUTHORIZED_SESSIONS.items():
        elapsed = time.time() - session['timestamp']
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        
        print(f"IP: {ip}")
        print(f"  Usuario: {session['user']}")
        print(f"  MAC: {session['mac']}")
        print(f"  Tiempo conectado: {minutes}m {seconds}s")
        print()
    
    print("="*60 + "\n")