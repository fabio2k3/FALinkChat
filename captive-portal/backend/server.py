"""
server.py - Servidor HTTPS con sockets TCP y SSL/TLS

Implementación manual de un servidor HTTPS concurrente usando
sockets, threading y el módulo ssl de la biblioteca estándar.

Autor: Portal Cautivo Lock&Route
"""

import socket
import threading
import ssl
import os
from typing import Callable


BUFFER_SIZE = 8192


class HTTPServer:
    """
    Servidor HTTP manual usando sockets TCP.
    
    Características:
    - Escucha en IP:puerto especificados
    - Maneja múltiples clientes concurrentemente con threads
    - Delega el procesamiento a una función handler externa
    """
    
    def __init__(self, host: str, port: int, handler: Callable):
        """
        Inicializa el servidor.
        
        Args:
            host: IP a escuchar. '0.0.0.0' = todas las interfaces
            port: Puerto TCP. 80 = HTTP estándar (requiere sudo)
            handler: Función(raw_data: bytes, client_ip: str) -> bytes
        """
        self.host = host
        self.port = port
        self.handler = handler
        self.server_socket = None
        self.running = False
    
    def start(self):
        """
        Inicia el servidor y entra en el bucle de aceptación.
        """
        self.server_socket = socket.socket(
            socket.AF_INET, 
            socket.SOCK_STREAM
        )
        
        self.server_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )
        
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        
        self.running = True
        print(f"[INFO] Servidor HTTP escuchando en {self.host}:{self.port}")
        
        self._accept_loop()
    
    def _accept_loop(self):
        """
        Bucle principal que acepta conexiones entrantes.
        """
        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()
                
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                client_thread.start()
                
            except OSError as e:
                if self.running:
                    print(f"[ERROR] En accept: {e}")
            except Exception as e:
                print(f"[ERROR] Inesperado en accept_loop: {e}")
    
    def _handle_client(self, client_socket: socket.socket, 
                       client_address: tuple):
        """
        Maneja UNA conexión de cliente. Se ejecuta en thread separado.
        """
        client_ip = client_address[0]
        
        try:
            client_socket.settimeout(30.0)
            raw_data = self._recv_all(client_socket)
            
            if raw_data:
                response = self.handler(raw_data, client_ip)
                client_socket.sendall(response)
            
        except socket.timeout:
            print(f"[WARN] Timeout esperando datos de {client_ip}")
        except ConnectionResetError:
            pass
        except BrokenPipeError:
            pass
        except Exception as e:
            print(f"[ERROR] Manejando cliente {client_ip}: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass
    
    def _recv_all(self, sock: socket.socket) -> bytes:
        """
        Recibe todos los datos disponibles del socket.
        """
        data = b''
        
        try:
            chunk = sock.recv(BUFFER_SIZE)
            data += chunk
            
            while len(chunk) == BUFFER_SIZE:
                sock.settimeout(0.5)
                try:
                    chunk = sock.recv(BUFFER_SIZE)
                    if chunk:
                        data += chunk
                    else:
                        break
                except socket.timeout:
                    break
                    
        except Exception as e:
            print(f"[ERROR] En recv: {e}")
        
        return data
    
    def stop(self):
        """
        Detiene el servidor limpiamente.
        """
        self.running = False
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        print("[INFO] Servidor detenido")


class HTTPSServer:
    """
    Servidor HTTPS con SSL/TLS.
    
    Características:
    - Escucha en IP:puerto especificados
    - Utiliza certificados SSL/TLS (puede ser autofirmado)
    - Maneja múltiples clientes concurrentemente con threads
    - Delega el procesamiento a una función handler externa
    """
    
    def __init__(self, host: str, port: int, handler: Callable, 
                 certfile: str, keyfile: str):
        """
        Inicializa el servidor HTTPS.
        
        Args:
            host: IP a escuchar
            port: Puerto TCP (típicamente 443 para HTTPS)
            handler: Función(raw_data: bytes, client_ip: str) -> bytes
            certfile: Ruta al certificado X.509 (.pem)
            keyfile: Ruta a la clave privada (.key)
        """
        self.host = host
        self.port = port
        self.handler = handler
        self.certfile = certfile
        self.keyfile = keyfile
        self.server_socket = None
        self.running = False
        
        # Verificar que los archivos existen
        if not os.path.exists(certfile):
            raise FileNotFoundError(f"Certificado no encontrado: {certfile}")
        if not os.path.exists(keyfile):
            raise FileNotFoundError(f"Clave privada no encontrada: {keyfile}")
    
    def start(self):
        """
        Inicia el servidor HTTPS.
        """
        # Crear socket base
        base_socket = socket.socket(
            socket.AF_INET, 
            socket.SOCK_STREAM
        )
        
        base_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )
        
        base_socket.bind((self.host, self.port))
        base_socket.listen(5)
        
        # Crear contexto SSL/TLS
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(self.certfile, self.keyfile)
        
        # Envolver el socket con SSL
        self.server_socket = context.wrap_socket(base_socket, server_side=True)
        
        self.running = True
        print(f"[INFO] Servidor HTTPS escuchando en {self.host}:{self.port}")
        
        self._accept_loop()
    
    def _accept_loop(self):
        """
        Bucle principal que acepta conexiones entrantes.
        """
        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()
                
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                client_thread.start()
                
            except OSError as e:
                if self.running:
                    print(f"[ERROR] En accept: {e}")
            except ssl.SSLError as e:
                print(f"[ERROR] SSL Error: {e}")
            except Exception as e:
                print(f"[ERROR] Inesperado en accept_loop: {e}")
    
    def _handle_client(self, client_socket: socket.socket, 
                       client_address: tuple):
        """
        Maneja UNA conexión de cliente HTTPS.
        """
        client_ip = client_address[0]
        
        try:
            client_socket.settimeout(30.0)
            raw_data = self._recv_all(client_socket)
            
            if raw_data:
                response = self.handler(raw_data, client_ip)
                client_socket.sendall(response)
            
        except socket.timeout:
            print(f"[WARN] Timeout esperando datos de {client_ip}")
        except ssl.SSLError as e:
            print(f"[WARN] SSL Error con {client_ip}: {e}")
        except ConnectionResetError:
            pass
        except BrokenPipeError:
            pass
        except Exception as e:
            print(f"[ERROR] Manejando cliente {client_ip}: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass
    
    def _recv_all(self, sock: socket.socket) -> bytes:
        """
        Recibe todos los datos disponibles del socket SSL.
        """
        data = b''
        
        try:
            chunk = sock.recv(BUFFER_SIZE)
            data += chunk
            
            while len(chunk) == BUFFER_SIZE:
                sock.settimeout(0.5)
                try:
                    chunk = sock.recv(BUFFER_SIZE)
                    if chunk:
                        data += chunk
                    else:
                        break
                except socket.timeout:
                    break
                    
        except Exception as e:
            print(f"[ERROR] En recv: {e}")
        
        return data
    
    def stop(self):
        """
        Detiene el servidor HTTPS limpiamente.
        """
        self.running = False
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        print("[INFO] Servidor HTTPS detenido")