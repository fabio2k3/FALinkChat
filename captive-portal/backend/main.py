"""
main.py - Punto de entrada del Servidor HTTP del Portal Cautivo

Ejecutar con: sudo python3 main.py

Este script:
1. Registra manejadores de señales (Ctrl+C)
2. Carga usuarios desde config/users.txt
3. Inicia el servidor HTTP en puerto 80
"""

import signal
import sys
import os

# Agregar directorio actual al path para imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import HTTPServer
from handler import handle_request
from auth import load_users


# ============================================================================
# CONFIGURACIÓN
# ============================================================================
HOST = '0.0.0.0'  # Escuchar en todas las interfaces de red
PORT = 80         # Puerto HTTP estándar (requiere sudo/root)

# Ruta al archivo de usuarios (relativa al directorio del script)
USERS_FILE = os.path.join(os.path.dirname(__file__), '..', 'config', 'users.txt')


# Variable global para el servidor (para poder cerrarlo desde signal_handler)
server = None


def signal_handler(signum, frame):
    """
    Manejador de señales del sistema operativo.
    
    Se ejecuta cuando el proceso recibe:
    - SIGINT (2): Usuario presionó Ctrl+C
    - SIGTERM (15): Comando kill <pid>
    
    Args:
        signum: Número de señal recibida
        frame: Stack frame actual (no lo usamos)
    """
    global server
    
    signal_names = {
        signal.SIGINT: 'SIGINT (Ctrl+C)',
        signal.SIGTERM: 'SIGTERM (kill)'
    }
    
    print(f"\n[INFO] Señal recibida: {signal_names.get(signum, signum)}")
    
    if server:
        server.stop()
    
    sys.exit(0)


def main():
    """
    Función principal del programa.
    
    Flujo:
    1. Registrar manejadores de señales
    2. Cargar usuarios desde archivo
    3. Crear servidor HTTP
    4. Iniciar servidor (bloquea hasta Ctrl+C)
    5. Limpiar recursos al terminar
    """
    global server
    
    print("=" * 60)
    print("  PORTAL CAUTIVO - Servidor HTTP Manual")
    print("=" * 60)
    
    # ========================================================================
    # PASO 1: Registrar manejadores de señales
    # ========================================================================
    # Esto permite cerrar el servidor limpiamente con Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # kill <pid>
    
    # ========================================================================
    # PASO 2: Cargar usuarios desde archivo
    # ========================================================================
    try:
        load_users(USERS_FILE)
        print(f"[INFO] Usuarios cargados desde: {USERS_FILE}")
    except FileNotFoundError:
        print(f"[WARN] Archivo de usuarios no encontrado: {USERS_FILE}")
        print("[WARN] Creando archivo de ejemplo...")
        create_default_users_file()
        load_users(USERS_FILE)
    except Exception as e:
        print(f"[ERROR] No se pudieron cargar usuarios: {e}")
        sys.exit(1)
    
    # ========================================================================
    # PASO 3: Crear servidor HTTP
    # ========================================================================
    server = HTTPServer(HOST, PORT, handle_request)
    
    # ========================================================================
    # PASO 4: Iniciar servidor
    # ========================================================================
    print(f"[INFO] Iniciando servidor en http://{HOST}:{PORT}")
    print("[INFO] Presiona Ctrl+C para detener")
    print("-" * 60)
    
    try:
        server.start()  # Bloquea aquí hasta que se detenga
        
    except PermissionError:
        print(f"[ERROR] No tienes permisos para usar el puerto {PORT}")
        print("[ERROR] Ejecuta con: sudo python3 main.py")
        sys.exit(1)
        
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"[ERROR] El puerto {PORT} ya está en uso")
            print("[ERROR] Cierra el otro proceso o usa otro puerto")
        else:
            print(f"[ERROR] Error de socket: {e}")
        sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n[INFO] Interrupción de teclado")
        
    finally:
        if server:
            server.stop()


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
    
    print(f"[INFO] Archivo creado: {USERS_FILE}")
    print("[INFO] Usuarios por defecto: admin/admin123, guest/guest")


if __name__ == '__main__':
    main()
