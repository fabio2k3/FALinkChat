"""
main.py - Punto de entrada del Servidor HTTP/HTTPS del Portal Cautivo

Ejecutar con: sudo python3 main.py

Este script:
1. Genera o carga certificados SSL/TLS autofirmados
2. Registra manejadores de señales (Ctrl+C)
3. Carga usuarios desde config/users.txt
4. Inicia servidores HTTP (puerto 80) y HTTPS (puerto 443) en paralelo
5. Verifica periódicamente sesiones para detectar suplantación de IPs
"""

import signal
import sys
import os
import threading
import time

# Agregar directorio actual al path para imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import HTTPServer, HTTPSServer
from handler import handle_request
from auth import load_users
from ssl_manager import create_certificate_if_needed
from fw_manager import verify_all_sessions, print_session_stats


# ============================================================================
# CONFIGURACIÓN
# ============================================================================
HOST = '0.0.0.0'        # Escuchar en todas las interfaces de red
PORT_HTTP = 80          # Puerto HTTP estándar (requiere sudo/root)
PORT_HTTPS = 443        # Puerto HTTPS estándar (requiere sudo/root)

# Ruta al archivo de usuarios (relativa al directorio del script)
USERS_FILE = os.path.join(os.path.dirname(__file__), '..', 'config', 'users.txt')

# Certificados SSL/TLS
CERT_DIR = os.path.join(os.path.dirname(__file__), '..', 'config', 'certs')
CERTFILE = os.path.join(CERT_DIR, 'portal.pem')
KEYFILE = os.path.join(CERT_DIR, 'portal.key')


# Variables globales para los servidores
http_server = None
https_server = None
monitoring_thread = None
running = True


def signal_handler(signum, frame):
    """
    Manejador de señales del sistema operativo.
    
    Se ejecuta cuando el proceso recibe:
    - SIGINT (2): Usuario presionó Ctrl+C
    - SIGTERM (15): Comando kill <pid>
    """
    global http_server, https_server, running
    
    signal_names = {
        signal.SIGINT: 'SIGINT (Ctrl+C)',
        signal.SIGTERM: 'SIGTERM (kill)'
    }
    
    print(f"\n[INFO] Señal recibida: {signal_names.get(signum, signum)}")
    
    running = False
    
    if http_server:
        http_server.stop()
    
    if https_server:
        https_server.stop()
    
    # Mostrar estadísticas finales
    print_session_stats()
    
    sys.exit(0)


def monitoring_worker():
    """
    Thread que se ejecuta periódicamente para verificar sesiones.
    
    Cada 30 segundos:
    1. Verifica todas las sesiones activas
    2. Detecta intentos de suplantación de IP
    3. Remueve IPs suplantadas
    """
    global running
    
    print("[INFO] Thread de monitoreo iniciado")
    
    while running:
        try:
            time.sleep(30)  # Verificar cada 30 segundos
            
            if not running:
                break
            
            print("\n[INFO] Ejecutando verificación de sesiones...")
            spoofed_count = verify_all_sessions()
            
            if spoofed_count > 0:
                print(f"[ALERT] Se tomaron acciones contra {spoofed_count} intentos de suplantación")
        
        except Exception as e:
            print(f"[ERROR] En thread de monitoreo: {e}")
            if not running:
                break
    
    print("[INFO] Thread de monitoreo terminado")


def main():
    """
    Función principal del programa.
    
    Flujo:
    1. Registrar manejadores de señales
    2. Generar/cargar certificados SSL
    3. Cargar usuarios desde archivo
    4. Crear servidores HTTP y HTTPS
    5. Iniciar servidores en paralelo (threads)
    6. Iniciar thread de monitoreo
    7. Mantener el programa corriendo hasta Ctrl+C
    """
    global http_server, https_server, monitoring_thread, running
    
    print("=" * 70)
    print("  PORTAL CAUTIVO - Servidor HTTP/HTTPS Manual")
    print("  Detección Automática + HTTPS Seguro + Control de Suplantación")
    print("=" * 70)
    
    # ========================================================================
    # PASO 1: Registrar manejadores de señales
    # ========================================================================
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # kill <pid>
    
    # ========================================================================
    # PASO 2: Generar/Cargar certificados SSL/TLS
    # ========================================================================
    print("\n[INFO] Gestionando certificados SSL/TLS...")
    
    certfile, keyfile = create_certificate_if_needed(CERT_DIR, 'portal')
    
    if not certfile or not keyfile:
        print("[ERROR] No se pudieron crear los certificados SSL")
        print("[ERROR] Asegúrate de tener openssl instalado: sudo apt-get install openssl")
        sys.exit(1)
    
    print(f"[OK] Certificados listos:")
    print(f"    Certificado: {certfile}")
    print(f"    Clave privada: {keyfile}")
    
    # ========================================================================
    # PASO 3: Cargar usuarios desde archivo
    # ========================================================================
    try:
        load_users(USERS_FILE)
        print(f"[OK] Usuarios cargados desde: {USERS_FILE}")
    except FileNotFoundError:
        print(f"[WARN] Archivo de usuarios no encontrado: {USERS_FILE}")
        print("[WARN] Creando archivo de ejemplo...")
        create_default_users_file()
        load_users(USERS_FILE)
    except Exception as e:
        print(f"[ERROR] No se pudieron cargar usuarios: {e}")
        sys.exit(1)
    
    # ========================================================================
    # PASO 4: Crear servidores HTTP y HTTPS
    # ========================================================================
    print("\n[INFO] Creando servidores HTTP y HTTPS...")
    
    http_server = HTTPServer(HOST, PORT_HTTP, handle_request)
    https_server = HTTPSServer(HOST, PORT_HTTPS, handle_request, certfile, keyfile)
    
    # ========================================================================
    # PASO 5: Iniciar servidores en threads separados
    # ========================================================================
    print("\n[INFO] Iniciando servidores en paralelo...")
    
    http_thread = threading.Thread(target=http_server.start, daemon=True, name="HTTPServer")
    https_thread = threading.Thread(target=https_server.start, daemon=True, name="HTTPSServer")
    
    try:
        http_thread.start()
        https_thread.start()
        
        # Dar tiempo a que los servidores se inicialicen
        time.sleep(2)
        
        # ====================================================================
        # PASO 6: Iniciar thread de monitoreo
        # ====================================================================
        print("\n[INFO] Iniciando thread de monitoreo de suplantación...")
        monitoring_thread = threading.Thread(target=monitoring_worker, daemon=True, name="Monitor")
        monitoring_thread.start()
        
        # ====================================================================
        # PASO 7: Mantener el programa corriendo
        # ====================================================================
        print("\n" + "=" * 70)
        print("[OK] ¡Portal cautivo operativo!")
        print("-" * 70)
        print("ENDPOINTS:")
        print(f"  HTTP:  http://192.168.50.1/login")
        print(f"  HTTPS: https://192.168.50.1/login")
        print("\nRECUERDA: El navegador puede avisar sobre certificado no verificado")
        print("           (es normal, usamos certificado autofirmado)")
        print("\nMONITOREO:")
        print("  - Verificación de suplantación cada 30 segundos")
        print("  - Detección automática de portal cautivo")
        print("  - Control de MAC address para prevenir spoofing")
        print("\n[INFO] Presiona Ctrl+C para detener")
        print("=" * 70 + "\n")
        
        # Mantener el main thread corriendo
        while running:
            time.sleep(1)
    
    except PermissionError as e:
        print(f"\n[ERROR] Permisos insuficientes")
        print(f"[ERROR] Asegúrate de ejecutar con sudo: sudo python3 main.py")
        sys.exit(1)
    
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"\n[ERROR] Puerto ya en uso")
            print(f"[ERROR] Detén el otro proceso portal o usa otros puertos")
        else:
            print(f"\n[ERROR] Error de socket: {e}")
        sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n[INFO] Interrupción de teclado")
    
    except Exception as e:
        print(f"\n[ERROR] Inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        running = False
        if http_server:
            http_server.stop()
        if https_server:
            https_server.stop()


def create_default_users_file():
    """
    Crea un archivo de usuarios por defecto si no existe.
    """
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        f.write("# Archivo de usuarios - formato: usuario:password\n")
        f.write("# Líneas que empiezan con # son comentarios\n")
        f.write("admin:admin123\n")
        f.write("guest:guest\n")
    
    print(f"[OK] Archivo creado: {USERS_FILE}")
    print("[OK] Usuarios por defecto: admin/admin123, guest/guest")


if __name__ == '__main__':
    main()
