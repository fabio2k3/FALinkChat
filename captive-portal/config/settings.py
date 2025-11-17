# Configuración del portal cautivo

# Configuración del servidor
SERVER_PORT = 80
SERVER_HOST = ""

# Interfaces de red
INTERFACE_AP = "wlo1"
INTERFACE_WAN = "enxda299959de87"
AP_IP = "192.168.50.1/24"

# Configuración de timeout para IPs autorizadas (en segundos)
IPSET_TIMEOUT = 7200  # 2 horas

# Rutas de archivos
USERS_FILE = "config/users.txt"
HTML_DIR = "html"

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "captive_portal.log"
