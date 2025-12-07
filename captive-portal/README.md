# Captive Portal - Proyecto de Redes de Computadoras

## Descripción

Portal cautivo implementado en Python para controlar el acceso a una red corporativa. Al conectarse un dispositivo nuevo, el gateway bloquea toda comunicación fuera de la red local hasta que el usuario inicie sesión correctamente.

## Estructura del Proyecto

```
captive-portal/
├── backend/
│   ├── __init__.py
│   ├── auth.py
│   ├── fw_manager.py
│   ├── handler.py
│   ├── http_utils.py
│   ├── main.py
│   ├── server.py
│   └── utils.py
├── config/
│   ├── dnsmasq/
│   ├── hostapd/
│   ├── settings.py
│   └── users.txt
├── html/
│   ├── fail.html
│   ├── login.html
│   ├── styleAccepted.css
│   ├── styleFail.css
│   ├── styles.css
│   └── success.html
├── scripts/
│   ├── start_portal.sh
│   └── stop_portal.sh
├── tests/
│   ├── test_cleanup.py
│   ├── test_concurrency.py
│   ├── test_error_handling.py
│   ├── test_functional_access.py
│   ├── test_fw_manager_mock.py
│   ├── test_load_users.py
│   └── test_portal_server_integration.py
├── requirements.txt
└── README.md
```
## Requisitos del Sistema

- Sistema operativo Linux (probado en Ubuntu/Debian)
- Python 3.7 o superior
- iptables y ipset
- hostapd y dnsmasq
- NetworkManager
- Permisos de root/sudo


1. Clonar el repositorio:
```bash
git clone <repo-url>
cd captive-portal
```

2. Instalar dependencias del sistema:
```bash
sudo apt-get update
```
sudo apt-get install iptables ipset hostapd dnsmasq python3
```

3. Configurar usuarios en `config/users.txt`:
```
usuario:contraseña
admin:admin123
```

```
4. Ajustar interfaces de red en `scripts/start_portal.sh` según tu hardware:
- `IF_AP`: Interfaz WiFi del Access Point
- `IF_WAN`: Interfaz con conexión a Internet
- `AP_IP`: IP del gateway (laptop que actúa como AP)

## Uso

### Iniciar el Portal Cautivo

```bash
cd FALinkChat/captive-portal
sudo bash scripts/start_portal.sh
```

Este script realiza:
- Verificación de requisitos y dependencias
- Creación de interfaz virtual WiFi (`wlo1_ap`)
- Conexión al hotspot móvil (SSID y clave configurables)
- Configuración del modo Access Point y red local
- Habilitación de IP forwarding
- Configuración de iptables y NAT
- Creación del ipset para IPs autorizadas
- Inicio de hostapd y dnsmasq
- Lanzamiento del servidor web manual en Python (`main.py`)

### Detener el Portal Cautivo

```bash
sudo bash scripts/stop_portal.sh
```

Este script realiza:
- Detención de servicios (hostapd, dnsmasq, servidor Python)
- Limpieza de reglas de firewall
- Eliminación de ipset
- Eliminación de la interfaz virtual WiFi
- Limpieza de archivos temporales
- Restauración de NetworkManager y reconexión al hotspot si es necesario

### Acceso de Usuarios

1. Los dispositivos se conectan al Access Point creado por el portal cautivo
2. Al intentar navegar, son redirigidos al portal (http://192.168.50.1)
3. Ingresan sus credenciales en la página de login
4. Si son correctas, su IP se agrega al conjunto de autorizados (ipset)
5. Obtienen acceso a Internet