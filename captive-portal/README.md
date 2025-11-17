# Captive Portal - Proyecto de Redes de Computadoras

## Descripción

Portal cautivo implementado en Python para controlar el acceso a una red corporativa. Al conectarse un dispositivo nuevo, el gateway bloquea toda comunicación fuera de la red local hasta que el usuario inicie sesión correctamente.

## Estructura del Proyecto

```
captive-portal/
├── scripts/              # Scripts de inicio/parada del portal
│   ├── start_portal.sh   # Inicia el modo AP y el servidor
│   └── stop_portal.sh    # Detiene el modo AP y limpia reglas
├── backend/              # Código Python del servidor
│   ├── __init__.py
│   ├── portal_server.py  # Servidor HTTP principal
│   ├── auth.py           # Gestión de autenticación
│   ├── fw_manager.py     # Gestión de firewall (iptables/ipset)
│   └── utils.py          # Utilidades
├── html/                 # Páginas web del portal
│   ├── login.html        # Página de inicio de sesión
│   ├── success.html      # Página de acceso exitoso
│   └── fail.html         # Página de acceso denegado
├── config/               # Archivos de configuración
│   ├── users.txt         # Credenciales de usuarios
│   └── settings.py       # Configuración general
├── README.md
└── requirements.txt
```

## Requisitos del Sistema

- Sistema operativo Linux (probado en Ubuntu/Debian)
- Python 3.7 o superior
- iptables y ipset
- hostapd y dnsmasq
- NetworkManager
- Permisos de root/sudo

## Instalación

1. Clonar el repositorio:
```bash
git clone <repo-url>
cd captive-portal
```

2. Instalar dependencias del sistema:
```bash
sudo apt-get update
sudo apt-get install iptables ipset hostapd dnsmasq python3
```

3. Configurar usuarios en `config/users.txt`:
```
usuario:contraseña
admin:admin123
```

4. Ajustar interfaces de red en `scripts/start_portal.sh` según tu hardware:
- `IF_AP`: Interfaz WiFi del Access Point
- `IF_WAN`: Interfaz con conexión a Internet
- `AP_IP`: IP del gateway (laptop que actúa como AP)

## Uso

### Iniciar el Portal Cautivo

```bash
cd captive-portal
sudo bash scripts/start_portal.sh
```

Esto realizará:
- Configuración del modo Access Point
- Habilitación de IP forwarding
- Configuración de iptables y NAT
- Creación del ipset para IPs autorizadas
- Inicio de hostapd y dnsmasq
- Inicio del servidor web Python

### Detener el Portal Cautivo

```bash
sudo bash scripts/stop_portal.sh
```

### Acceso de Usuarios

1. Los dispositivos se conectan al Access Point
2. Al intentar navegar, son redirigidos al portal (http://192.168.50.1)
3. Ingresan sus credenciales en la página de login
4. Si son correctas, su IP se agrega al conjunto de autorizados
5. Obtienen acceso a Internet