"""
http_utils.py - Utilidades para parsing HTTP manual

Este módulo contiene funciones puras para parsear peticiones HTTP
y construir respuestas. 

"""

from typing import Dict
from urllib.parse import unquote_plus


def parse_request(raw_data: bytes) -> Dict:
    """
    Parsea una petición HTTP cruda en sus componentes.
    
    Args:
        raw_data: Bytes crudos recibidos del socket
        
    Returns:
        Dict con keys: method, path, version, headers, body
    """
    result = {
        'method': '',
        'path': '',
        'version': '',
        'headers': {},
        'body': ''
    }
    
    try:
        # Separar headers del body usando la línea vacía (CRLF CRLF)
        if b'\r\n\r\n' in raw_data:
            header_part, body = raw_data.split(b'\r\n\r\n', 1)
            result['body'] = body.decode('utf-8', errors='replace')
        else:
            header_part = raw_data
        
        # Decodificar headers a string
        header_text = header_part.decode('utf-8', errors='replace')
        
        # Dividir en líneas
        lines = header_text.split('\r\n')
        
        if not lines:
            return result
        
        # Primera línea: GET /path HTTP/1.1
        request_line = lines[0]
        parts = request_line.split(' ')
        
        if len(parts) >= 3:
            result['method'] = parts[0].upper()  # GET, POST, etc.
            result['path'] = parts[1]             # /login, /success
            result['version'] = parts[2]          # HTTP/1.1
        elif len(parts) == 2:
            result['method'] = parts[0].upper()
            result['path'] = parts[1]
        
        # Parsear headers (líneas 1 en adelante)
        for line in lines[1:]:
            if ':' in line:
                key, value = line.split(':', 1)
                # Headers en minúsculas para consistencia
                result['headers'][key.strip().lower()] = value.strip()
        
    except Exception as e:
        print(f"[ERROR] Parseando request: {e}")
    
    return result


def parse_form_data(body: str) -> Dict[str, str]:
    """
    Parsea datos de formulario URL-encoded.
    
    Formato entrada: key1=value1&key2=value2
    
    Args:
        body: String con datos del formulario
        
    Returns:
        Dict con key=value decodificados
        
    Ejemplo:
        >>> parse_form_data("user=admin&password=mi%20clave")
        {'user': 'admin', 'password': 'mi clave'}
    """
    form = {}
    
    if not body:
        return form
    
    # Dividir por & para obtener pares key=value
    pairs = body.split('&')
    
    for pair in pairs:
        if '=' in pair:
            key, value = pair.split('=', 1)
            # unquote_plus decodifica %XX y convierte + a espacio
            form[unquote_plus(key)] = unquote_plus(value)
    
    return form


def build_response(status_code: int, body: str, 
                   content_type: str = 'text/html; charset=utf-8',
                   extra_headers: Dict[str, str] = None) -> bytes:
    """
    Construye una respuesta HTTP completa.
    
    Args:
        status_code: Código HTTP (200, 302, 404, etc.)
        body: Contenido HTML/texto de la respuesta
        content_type: Tipo MIME del contenido
        extra_headers: Headers adicionales opcionales
        
    Returns:
        Bytes listos para enviar por socket
        
    Ejemplo:
        >>> resp = build_response(200, "<h1>Hola</h1>")
        >>> b"HTTP/1.1 200 OK" in resp
        True
    """
    # Mapeo de códigos a mensajes
    status_messages = {
        200: 'OK',
        204: 'No Content',
        301: 'Moved Permanently',
        302: 'Found',
        400: 'Bad Request',
        403: 'Forbidden',
        404: 'Not Found',
        500: 'Internal Server Error'
    }
    
    status_text = status_messages.get(status_code, 'Unknown')
    
    # Convertir body a bytes
    body_bytes = body.encode('utf-8')
    
    # Construir headers
    headers = [
        f"HTTP/1.1 {status_code} {status_text}",
        f"Content-Type: {content_type}",
        f"Content-Length: {len(body_bytes)}",
        "Connection: close"
    ]
    
    # Agregar headers extra
    if extra_headers:
        for key, value in extra_headers.items():
            headers.append(f"{key}: {value}")
    
    # Unir todo: headers + línea vacía + body
    header_text = '\r\n'.join(headers) + '\r\n\r\n'
    
    return header_text.encode('utf-8') + body_bytes


def build_redirect(location: str, status_code: int = 302) -> bytes:
    """
    Construye una respuesta de redirección HTTP.
    
    Args:
        location: URL destino de la redirección
        status_code: 301 (permanente) o 302 (temporal)
        
    Returns:
        Bytes de la respuesta de redirección
    """
    status_text = 'Moved Permanently' if status_code == 301 else 'Found'
    
    headers = [
        f"HTTP/1.1 {status_code} {status_text}",
        f"Location: {location}",
        "Content-Length: 0",
        "Connection: close"
    ]
    
    return ('\r\n'.join(headers) + '\r\n\r\n').encode('utf-8')
