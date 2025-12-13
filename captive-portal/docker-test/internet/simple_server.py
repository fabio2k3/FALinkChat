#!/usr/bin/env python3
"""
simple_server.py - Servidor HTTP simulado que representa "Internet Externo"

Este servidor corre en el contenedor 'internet_server' y simula un servidor
externo en Internet. Se usa para probar que los clientes autorizados pueden
acceder a él después de autenticarse en el portal cautivo.

Puerto: 8000
Protocolo: HTTP simple
"""

import socket
import sys
import threading
import time
from datetime import datetime

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

HOST = "0.0.0.0"
PORT = 8000
BUFFER_SIZE = 4096

# Contadores para stats
total_requests = 0
total_bytes_sent = 0

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def get_timestamp():
    """Retorna timestamp formateado"""
    return datetime.now().strftime("%H:%M:%S")

def log_info(message):
    """Log de información"""
    print(f"[{get_timestamp()}] [INFO] {message}")

def log_request(client_ip, request_line):
    """Log de request recibido"""
    print(f"[{get_timestamp()}] [REQUEST] {client_ip} -> {request_line}")

def log_response(client_ip, status_code):
    """Log de response enviado"""
    print(f"[{get_timestamp()}] [RESPONSE] {client_ip} <- HTTP {status_code}")

# ============================================================================
# CONSTRUCCIÓN DE RESPUESTAS HTTP
# ============================================================================

def build_html_response():
    """Construye el HTML de la página"""
    html = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Internet Externo - Servidor de Prueba</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
            max-width: 600px;
            padding: 40px;
            text-align: center;
        }
        
        .icon {
            font-size: 60px;
            margin-bottom: 20px;
        }
        
        h1 {
            color: #333;
            margin-bottom: 20px;
            font-size: 2.5em;
        }
        
        h2 {
            color: #667eea;
            font-size: 1.5em;
            margin: 30px 0 20px;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        
        p {
            color: #666;
            line-height: 1.8;
            margin: 15px 0;
            font-size: 1.1em;
        }
        
        .status {
            background: #4CAF50;
            color: white;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
            font-weight: bold;
            font-size: 1.2em;
        }
        
        .info-box {
            background: #f0f0f0;
            padding: 20px;
            border-radius: 5px;
            margin: 20px 0;
            text-align: left;
        }
        
        .info-box p {
            margin: 10px 0;
            text-align: left;
        }
        
        .label {
            font-weight: bold;
            color: #333;
        }
        
        .value {
            color: #667eea;
            word-break: break-all;
        }
        
        .footer {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 2px solid #ddd;
            color: #999;
            font-size: 0.9em;
        }
        
        .success-badge {
            display: inline-block;
            background: #4CAF50;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">🌐</div>
        
        <h1>Internet Externo</h1>
        
        <p>Servidor de prueba que simula un servidor externo en Internet</p>
        
        <div class="status">
            ✓ CONEXIÓN EXITOSA
        </div>
        
        <h2>Información de Conexión</h2>
        
        <div class="info-box">
            <p>
                <span class="label">IP del Cliente:</span><br>
                <span class="value">%s</span>
            </p>
            
            <p>
                <span class="label">Servidor:</span><br>
                <span class="value">Internet Externo (Simulado)</span>
            </p>
            
            <p>
                <span class="label">Puerto:</span><br>
                <span class="value">8000 (HTTP)</span>
            </p>
            
            <p>
                <span class="label">Timestamp:</span><br>
                <span class="value">%s</span>
            </p>
        </div>
        
        <h2>¿Qué significa esto?</h2>
        
        <p>
            Si ves esta página, significa que:
        </p>
        
        <ul style="text-align: left; margin: 20px 0;">
            <li><span class="success-badge">✓</span> Tu cliente se conectó al portal cautivo</li>
            <li><span class="success-badge">✓</span> Te autenticaste exitosamente</li>
            <li><span class="success-badge">✓</span> Tu IP fue autorizada</li>
            <li><span class="success-badge">✓</span> Puedes acceder a "Internet" externo</li>
            <li><span class="success-badge">✓</span> El firewall te permitió salir de la red local</li>
        </ul>
        
        <h2>Propósito de este Servidor</h2>
        
        <p>
            Este servidor está diseñado para <strong>pruebas del portal cautivo</strong>.
            Permite verificar que los clientes autorizados pueden acceder a recursos
            externos después de pasar la autenticación.
        </p>
        
        <div class="footer">
            <p>
                Servidor de prueba para Portal Cautivo Lock&Route<br>
                Proyecto de Redes de Computadoras - Curso 2025
            </p>
        </div>
    </div>
</body>
</html>"""
    return html

def build_http_response(status_code, body):
    """
    Construye una respuesta HTTP completa
    
    Args:
        status_code: Código HTTP (200, 404, 500, etc.)
        body: Contenido HTML/texto de la respuesta
        
    Returns:
        Bytes listos para enviar
    """
    # Mapeo de códigos HTTP a mensajes
    status_messages = {
        200: "OK",
        404: "Not Found",
        500: "Internal Server Error"
    }
    
    status_text = status_messages.get(status_code, "Unknown")
    
    # Convertir body a bytes
    body_bytes = body.encode('utf-8')
    
    # Construir headers HTTP
    headers = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: text/html; charset=utf-8\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        f"Connection: close\r\n"
        f"Server: InternetSimulator/1.0\r\n"
        f"\r\n"
    )
    
    # Retornar headers + body como bytes
    return headers.encode('utf-8') + body_bytes

def parse_request(request_data):
    """
    Parsea una request HTTP simple
    
    Args:
        request_data: String con la request HTTP cruda
        
    Returns:
        Tupla (método, ruta, versión)
    """
    try:
        lines = request_data.split('\r\n')
        if not lines:
            return None, None, None
        
        request_line = lines[0]
        parts = request_line.split(' ')
        
        if len(parts) >= 3:
            method = parts[0].upper()
            path = parts[1]
            version = parts[2]
            return method, path, version
        
        return None, None, None
    except Exception as e:
        log_info(f"Error parseando request: {e}")
        return None, None, None

# ============================================================================
# MANEJADOR DE CONEXIONES
# ============================================================================

def handle_client(client_socket, client_address):
    """
    Maneja una conexión de cliente individual
    
    Args:
        client_socket: Socket del cliente
        client_address: Tupla (IP, puerto) del cliente
    """
    global total_requests, total_bytes_sent
    
    client_ip = client_address[0]
    client_port = client_address[1]
    
    try:
        # Configurar timeout
        client_socket.settimeout(5.0)
        
        # Recibir datos del cliente
        request_data = client_socket.recv(BUFFER_SIZE).decode('utf-8', errors='ignore')
        
        if not request_data:
            return
        
        # Parsear request
        method, path, version = parse_request(request_data)
        
        if method is None:
            return
        
        # Log de la request
        request_line = f"{method} {path} {version}"
        log_request(client_ip, request_line)
        
        # Incrementar contador
        total_requests += 1
        
        # Procesar request según el método y ruta
        if method == 'GET':
            if path == '/' or path == '/index.html':
                # Generar HTML con IP del cliente
                timestamp = get_timestamp()
                html = build_html_response() % (client_ip, timestamp)
                response = build_http_response(200, html)
                
                log_response(client_ip, 200)
                
            elif path == '/health':
                # Endpoint de health check
                html = '{"status": "ok"}'
                response = build_http_response(200, html)
                log_response(client_ip, 200)
                
            elif path == '/stats':
                # Endpoint de estadísticas
                html = f"""
                <html><body>
                <h1>Estadísticas del Servidor</h1>
                <p>Total de requests: {total_requests}</p>
                <p>Total de bytes enviados: {total_bytes_sent}</p>
                <p>Clientes conectados: {client_ip}</p>
                </body></html>
                """
                response = build_http_response(200, html)
                log_response(client_ip, 200)
                
            else:
                # Ruta no encontrada
                html = f"""
                <html><body>
                <h1>404 - Página No Encontrada</h1>
                <p>La ruta <strong>{path}</strong> no existe.</p>
                <p><a href="/">Volver al inicio</a></p>
                </body></html>
                """
                response = build_http_response(404, html)
                log_response(client_ip, 404)
        
        else:
            # Método no soportado
            html = f"""
            <html><body>
            <h1>405 - Método No Soportado</h1>
            <p>El método <strong>{method}</strong> no está soportado.</p>
            </body></html>
            """
            response = build_http_response(405, html)
            log_response(client_ip, 405)
        
        # Enviar response
        client_socket.sendall(response)
        total_bytes_sent += len(response)
        
    except socket.timeout:
        log_info(f"Timeout esperando datos de {client_ip}")
    except ConnectionResetError:
        pass  # Cliente cerró la conexión
    except BrokenPipeError:
        pass  # Conexión rota
    except Exception as e:
        log_info(f"Error manejando cliente {client_ip}: {e}")
    
    finally:
        try:
            client_socket.close()
        except:
            pass

# ============================================================================
# SERVIDOR PRINCIPAL
# ============================================================================

def run_server():
    """
    Inicia el servidor HTTP y entra en el bucle de aceptación de conexiones
    """
    
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║          SERVIDOR DE INTERNET EXTERNO (SIMULADO)              ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()
    
    log_info(f"Iniciando servidor en {HOST}:{PORT}")
    log_info("Este servidor simula 'Internet Externo' para pruebas del portal cautivo")
    log_info("Presiona Ctrl+C para detener")
    print()
    
    try:
        # Crear socket servidor
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Permitir reutilizar dirección
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Bind a IP y puerto
        server_socket.bind((HOST, PORT))
        
        # Escuchar conexiones
        server_socket.listen(5)
        
        log_info(f"Servidor escuchando en http://{HOST}:{PORT}")
        print()
        
        # Bucle principal
        while True:
            try:
                # Aceptar conexión
                client_socket, client_address = server_socket.accept()
                
                # Crear thread para manejar cliente
                client_thread = threading.Thread(
                    target=handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                client_thread.start()
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                log_info(f"Error aceptando conexión: {e}")
        
    except OSError as e:
        print(f"[ERROR] No se pudo iniciar el servidor: {e}")
        sys.exit(1)
    
    finally:
        try:
            server_socket.close()
            log_info("Servidor detenido")
        except:
            pass

# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

if __name__ == "__main__":
    run_server()
