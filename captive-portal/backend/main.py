"""
main.py - Servidor DUAL HTTP/HTTPS para Portal Cautivo

SOLUCIÓN AL PROBLEMA:
- Servidor HTTP (puerto 80): Solo redirige a HTTPS
- Servidor HTTPS (puerto 8080): Portal real con TLS

Basado en:
- nginx dual server configuration
- pfSense captive portal architecture
- Apache redirect + SSL VirtualHost pattern
"""

import signal
import sys
import os
import ssl
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import HTTPServer
from handler import handle_request
from auth import load_users


# ============================================================================
# CONFIGURACIÓN
# ============================================================================
HOST = '0.0.0.0'
HTTP_PORT = 80        # HTTP plano - Solo redirige
HTTPS_PORT = 8080     # HTTPS con TLS - Portal real

USERS_FILE = os.path.join(os.path.dirname(__file__), '..', 'config', 'users.txt')

# Variables globales para ambos servidores
http_server = None
https_server = None


def signal_handler(signum, frame):
    """Manejador de señales para detener ambos servidores."""
    global http_server, https_server
    
    signal_names = {
        signal.SIGINT: 'SIGINT (Ctrl+C)',
        signal.SIGTERM: 'SIGTERM (kill)'
    }
    
    print(f"\n[INFO] Señal recibida: {signal_names.get(signum, signum)}")
    
    # Detener ambos servidores
    if http_server:
        http_server.stop()
    if https_server:
        https_server.stop()
    
    sys.exit(0)


def http_redirect_handler(raw_data: bytes, client_ip: str) -> bytes:
    """
    Handler para servidor HTTP (puerto 80).
    
    Solo redirige TODO a HTTPS.
    NO procesa ninguna lógica del portal.
    
    Args:
        raw_data: Petición HTTP (se ignora mayormente)
        client_ip: IP del cliente
        
    Returns:
        Respuesta de redirección 302 a HTTPS
    """
    # Log simple
    print(f"[HTTP:{client_ip}] Redirigiendo a HTTPS")
    
    # Construir redirección 302
    redirect_url = f"https://192.168.50.1:{HTTPS_PORT}/login"
    
    response = (
        "HTTP/1.1 302 Found\r\n"
        f"Location: {redirect_url}\r\n"
        "Content-Length: 0\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    
    return response.encode('utf-8')


def main():
    """Función principal que inicia ambos servidores."""
    global http_server, https_server
    
    print("=" * 60)
    print("  PORTAL CAUTIVO - Servidor DUAL HTTP/HTTPS")
    print("=" * 60)
    
    # ========================================================================
    # PASO 1: Registrar manejadores de señales
    # ========================================================================
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # ========================================================================
    # PASO 2: Cargar usuarios
    # ========================================================================
    try:
        load_users(USERS_FILE)
        print(f"[INFO] Usuarios cargados desde: {USERS_FILE}")
    except FileNotFoundError:
        print(f"[WARN] Archivo de usuarios no encontrado")
        create_default_users_file()
        load_users(USERS_FILE)
    except Exception as e:
        print(f"[ERROR] No se pudieron cargar usuarios: {e}")
        sys.exit(1)
    
    # ========================================================================
    # PASO 3: Crear contexto SSL para servidor HTTPS
    # ========================================================================
    try:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        
        cert_path = os.path.join(os.path.dirname(__file__), 'cert.pem')
        key_path = os.path.join(os.path.dirname(__file__), 'key.pem')
        
        ssl_context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        print(f"[INFO] Certificados SSL cargados correctamente")
    except FileNotFoundError:
        print("[ERROR] Certificados no encontrados")
        print("[ERROR] Ejecuta: openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj '/CN=192.168.50.1'")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Error al cargar certificados: {e}")
        sys.exit(1)
    
    # ========================================================================
    # PASO 4: Crear servidor HTTP (puerto 80) - SIN SSL
    # ========================================================================
    # Este servidor solo redirige a HTTPS
    # ssl_context=None → NO espera TLS
    http_server = HTTPServer(
        host=HOST,
        port=HTTP_PORT,
        handler=http_redirect_handler,  # Handler diferente
        ssl_context=None  # CRÍTICO: Sin SSL
    )
    
    # ========================================================================
    # PASO 5: Crear servidor HTTPS (puerto 8080) - CON SSL
    # ========================================================================
    # Este servidor maneja el portal real
    # ssl_context=ctx → SÍ espera TLS
    https_server = HTTPServer(
        host=HOST,
        port=HTTPS_PORT,
        handler=handle_request,  # Handler completo del portal
        ssl_context=ssl_context  # CRÍTICO: Con SSL
    )
    
    # ========================================================================
    # PASO 6: Iniciar ambos servidores en threads separados
    # ========================================================================
    print(f"[INFO] Iniciando servidor HTTP en  http://{HOST}:{HTTP_PORT}")
    print(f"[INFO] Iniciando servidor HTTPS en https://{HOST}:{HTTPS_PORT}")
    print("[INFO] Presiona Ctrl+C para detener")
    print("-" * 60)
    
    try:
        # Thread para servidor HTTP
        http_thread = threading.Thread(
            target=http_server.start,
            daemon=True,
            name="HTTP-Server"
        )
        
        # Thread para servidor HTTPS
        https_thread = threading.Thread(
            target=https_server.start,
            daemon=True,
            name="HTTPS-Server"
        )
        
        # Iniciar ambos threads
        http_thread.start()
        https_thread.start()
        
        # Esperar a que terminen (bloquea aquí)
        # Como son daemon=True, morirán cuando el proceso principal muera
        http_thread.join()
        https_thread.join()
        
    except PermissionError:
        print(f"[ERROR] No tienes permisos para puertos privilegiados")
        print("[ERROR] Ejecuta con: sudo python3 main.py")
        sys.exit(1)
    
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"[ERROR] Puerto ya en uso")
            print("[ERROR] Cierra el otro proceso primero")
        else:
            print(f"[ERROR] Error de socket: {e}")
        sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n[INFO] Interrupción de teclado")
    
    finally:
        # Detener ambos servidores
        if http_server:
            http_server.stop()
        if https_server:
            https_server.stop()


def create_default_users_file():
    """Crea archivo de usuarios por defecto."""
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        f.write("# Archivo de usuarios - formato: usuario:password\n")
        f.write("# Líneas que empiezan con # son comentarios\n")
        f.write("admin:admin123\n")
        f.write("guest:guest\n")
    
    print(f"[INFO] Archivo creado: {USERS_FILE}")


if __name__ == '__main__':
    main()