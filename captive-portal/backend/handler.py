"""
handler.py - Manejador de peticiones HTTP para Portal Cautivo

Este módulo contiene la lógica de rutas y procesamiento de peticiones.
Incluye detección automática de captive portal para iOS, Android, 
Windows y Firefox con soporte para HTTP y HTTPS.
"""

import os
from http_utils import parse_request, parse_form_data, build_response, build_redirect
from auth import check_user
from fw_manager import add_authorized, is_ip_spoofed


# Directorio base para archivos HTML
HTML_DIR = os.path.join(os.path.dirname(__file__), '..', 'html')

# URL del portal de login
PORTAL_URL = '/login'

# IPs del gateway para redirecciones
GATEWAY_HTTP = '192.168.50.1'
GATEWAY_HTTPS = '192.168.50.1'


# ============================================================================
# DETECCIÓN DE CAPTIVE PORTAL - Rutas de detección automática
# ============================================================================
# Cada sistema operativo hace peticiones a URLs específicas para detectar
# si hay conexión a Internet. Si la respuesta no es la esperada, muestran
# el portal cautivo automáticamente.

CAPTIVE_PORTAL_PATHS = {
    # Apple iOS / macOS - Espera: "Success" en el body
    '/hotspot-detect.html': 'apple',
    '/library/test/success.html': 'apple',
    '/gen_204': 'apple',  # iOS también usa esto
    
    # Google Android - Espera: HTTP 204 No Content
    '/generate_204': 'android',
    '/gen_204': 'android',
    '/connectivitycheck/gstatic/': 'android',
    '/connectivitycheck.gstatic.com': 'android',
    '/clients3.google.com/generate_204': 'android',
    
    # Microsoft Windows - Espera: "Microsoft Connect Test" en body
    '/connecttest.txt': 'windows',
    '/ncsi.txt': 'windows',
    '/redirect': 'windows',
    '/MSFT_CAPTIVE_PORTAL_DETECTION_CONFIRMATION': 'windows',
    
    # Mozilla Firefox - Espera: "success" en body
    '/canonical.html': 'firefox',
    '/success.txt': 'firefox',
    '/detect_portal': 'firefox',
}


def handle_request(raw_data: bytes, client_ip: str) -> bytes:
    """
    Función principal que procesa cada petición HTTP/HTTPS.
    
    Esta función actúa como dispatcher/router:
    1. Parsea la petición HTTP
    2. Determina qué ruta se está solicitando
    3. Llama al handler correspondiente
    4. Retorna la respuesta HTTP en bytes
    
    Args:
        raw_data: Bytes crudos de la petición HTTP
        client_ip: IP del cliente (para autorizar en firewall)
        
    Returns:
        Bytes de la respuesta HTTP completa
    """
    # Parsear la petición
    request = parse_request(raw_data)
    method = request['method']
    path = request['path']
    
    # Log de la petición
    print(f"[{client_ip}] {method} {path}")
    
    # ========================================================================
    # VERIFICACIÓN DE SUPLANTACIÓN DE IP
    # ========================================================================
    # Si la IP ya está autorizada pero intenta hacer una petición normal
    # (no a rutas de detección de portal), verificamos que no sea suplantada
    if path not in CAPTIVE_PORTAL_PATHS and method == 'GET' and path not in ['/login', '/success', '/fail', '/styles.css', '/styleAccepted.css', '/styleFail.css']:
        # IP ya debería estar autorizada, verificar que no sea spoofed
        if is_ip_spoofed(client_ip):
            print(f"[ALERT] Posible suplantación de IP detectada: {client_ip}")
            return build_redirect(PORTAL_URL)
    
    # ========================================================================
    # DETECCIÓN AUTOMÁTICA DE CAPTIVE PORTAL
    # ========================================================================
    # Verificar si es una petición de detección de conectividad
    for portal_path, os_type in CAPTIVE_PORTAL_PATHS.items():
        if path.startswith(portal_path) or path == portal_path or \
           (portal_path.endswith('/') and path.startswith(portal_path)):
            return handle_captive_detection(os_type, client_ip, method)
    
    # ========================================================================
    # ROUTING PRINCIPAL
    # ========================================================================
    
    # GET /login - Mostrar formulario
    if method == 'GET' and path == '/login':
        return handle_get_login()
    
    # POST /login - Procesar credenciales
    if method == 'POST' and path == '/login':
        return handle_post_login(request, client_ip)
    
    # GET /success - Página de éxito
    if method == 'GET' and path == '/success':
        return handle_success()
    
    # GET /fail - Página de error
    if method == 'GET' and path == '/fail':
        return handle_fail()
    
    # GET /styles.css - Hoja de estilos
    if method == 'GET' and path == '/styles.css':
        return handle_css('styles.css')
    
    if method == 'GET' and path == '/styleAccepted.css':
        return handle_css('styleAccepted.css')
    
    if method == 'GET' and path == '/styleFail.css':
        return handle_css('styleFail.css')
    
    # Cualquier otra ruta - redirigir al login
    # Esto captura peticiones como GET / o rutas desconocidas
    return build_redirect(PORTAL_URL)


def handle_captive_detection(os_type: str, client_ip: str, method: str) -> bytes:
    """
    Maneja las peticiones de detección de captive portal.
    
    Cada sistema operativo espera una respuesta específica:
    - Si la recibe: "Hay Internet, todo bien"
    - Si NO la recibe: "Hay un portal cautivo, mostrar página de login"
    
    Nosotros queremos que detecte el portal, así que devolvemos
    una respuesta que FUERZA la apertura del navegador de portal.
    
    Args:
        os_type: Tipo de sistema operativo (apple, android, windows, firefox)
        client_ip: IP del cliente
        method: Método HTTP (GET, POST)
        
    Returns:
        Respuesta HTTP que activa la detección de portal
    """
    print(f"[{client_ip}] Detección automática de portal: {os_type}")
    
    if os_type == 'apple':
        # Apple espera "Success". Devolvemos HTML con redirect
        # Esto fuerza a iOS/macOS a abrir el navegador de portal cautivo
        html = f'''<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="0;url=http://{GATEWAY_HTTP}{PORTAL_URL}">
    <title>Portal Cautivo</title>
</head>
<body>
    <h1>Redirigiendo al portal de acceso...</h1>
    <p>Si no es redirigido automáticamente, 
       <a href="http://{GATEWAY_HTTP}{PORTAL_URL}">haga clic aquí</a>.</p>
</body>
</html>'''
        return build_response(200, html)
    
    elif os_type == 'android':
        # Android espera HTTP 204. Devolvemos 302 redirect
        # Esto fuerza a Android a abrir el navegador de portal
        return build_redirect(f'http://{GATEWAY_HTTP}{PORTAL_URL}')
    
    elif os_type == 'windows':
        # Windows espera "Microsoft Connect Test"
        # Devolvemos redirect para forzar portal
        # Algunos clientes también esperan HTTP 200 con contenido específico
        html = '<!DOCTYPE html><html><body>Microsoft Connect Test</body></html>'
        
        # Agregar header para indicar que no hay internet
        response = build_response(302, '', extra_headers={
            'Location': f'http://{GATEWAY_HTTP}{PORTAL_URL}'
        })
        return response
    
    elif os_type == 'firefox':
        # Firefox espera "success" en texto plano
        # Devolvemos redirect
        return build_redirect(f'http://{GATEWAY_HTTP}{PORTAL_URL}')
    
    # Por defecto, redirigir al login
    return build_redirect(PORTAL_URL)


def handle_get_login() -> bytes:
    """
    Muestra el formulario de login.
    Lee el archivo login.html y lo devuelve.
    """
    html = read_html_file('login.html')
    return build_response(200, html)


def handle_post_login(request: dict, client_ip: str) -> bytes:
    """
    Procesa el envío del formulario de login.
    
    1. Extrae usuario y password del body
    2. Verifica credenciales con auth.check_user()
    3. Si son correctas: autoriza IP y redirige a /success
    4. Si son incorrectas: redirige a /fail
    
    Args:
        request: Diccionario con la petición parseada
        client_ip: IP del cliente para autorizar
        
    Returns:
        Respuesta HTTP (redirect a /success o /fail)
    """
    # Parsear datos del formulario
    form = parse_form_data(request['body'])
    
    user = form.get('user', '') or form.get('username', '')
    password = form.get('password', '')
    
    print(f"[{client_ip}] Intento de login: usuario='{user}'")
    
    # Verificar credenciales
    if check_user(user, password):
        print(f"[{client_ip}] Login EXITOSO para '{user}'")
        
        # Autorizar IP en el firewall (ipset)
        # Aquí también se registra la MAC address del cliente
        try:
            add_authorized(client_ip, user)
            print(f"[{client_ip}] IP autorizada en firewall para usuario '{user}'")
        except Exception as e:
            print(f"[ERROR] No se pudo autorizar IP {client_ip}: {e}")
        
        # Redirigir a página de éxito
        return build_redirect('/success')
    else:
        print(f"[{client_ip}] Login FALLIDO para '{user}'")
        return build_redirect('/fail')


def handle_success() -> bytes:
    """Muestra la página de acceso exitoso."""
    html = read_html_file('success.html')
    return build_response(200, html)


def handle_fail() -> bytes:
    """Muestra la página de error de login."""
    html = read_html_file('fail.html')
    return build_response(200, html)


def handle_css(filename: str) -> bytes:
    """
    Sirve archivos CSS.
    
    Args:
        filename: Nombre del archivo CSS
        
    Returns:
        Respuesta HTTP con Content-Type: text/css
    """
    css = read_html_file(filename)
    return build_response(200, css, content_type='text/css; charset=utf-8')


def read_html_file(filename: str) -> str:
    """
    Lee un archivo del directorio html/.
    
    Args:
        filename: Nombre del archivo (ej: 'login.html')
        
    Returns:
        Contenido del archivo como string
    """
    filepath = os.path.join(HTML_DIR, filename)
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"[ERROR] Archivo no encontrado: {filepath}")
        return f"<html><body><h1>Error 404</h1><p>Archivo no encontrado: {filename}</p></body></html>"
    except Exception as e:
        print(f"[ERROR] Leyendo {filepath}: {e}")
        return f"<html><body><h1>Error 500</h1><p>Error interno del servidor</p></body></html>"
