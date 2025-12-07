"""
server.py - Servidor HTTP con sockets TCP puros

Implementación manual de un servidor HTTP concurrente usando
solo el módulo socket y threading. 

Autor: Portal Cautivo Lock&Route
"""

import socket
import threading
from typing import Callable


# Tamaño del buffer para recv()
BUFFER_SIZE = 8192  # 8KB - suficiente para la mayoría de requests HTTP


class HTTPServer:
    """
    Servidor HTTP manual usando sockets TCP.
    
    Características:
    - Escucha en IP:puerto especificados
    - Maneja múltiples clientes concurrentemente con threads
    - Delega el procesamiento a una función handler externa
    
    Uso:
        def mi_handler(raw_data: bytes, client_ip: str) -> bytes:
            # Procesar petición...
            return respuesta_bytes
        
        server = HTTPServer('0.0.0.0', 80, mi_handler)
        server.start()
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
        Este método bloquea hasta que se llame a stop().
        """
        # Crear socket TCP (IPv4)
        # AF_INET = IPv4, SOCK_STREAM = TCP
        self.server_socket = socket.socket(
            socket.AF_INET, 
            socket.SOCK_STREAM
        )
        
        # SO_REUSEADDR: permite reusar el puerto inmediatamente
        # Sin esto, tras cerrar el servidor hay que esperar ~2 minutos
        self.server_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )
        
        # Bind: asociar socket a IP:puerto
        self.server_socket.bind((self.host, self.port))
        
        # Listen: convertir en socket servidor
        # El argumento (5) es el backlog: conexiones en cola
        self.server_socket.listen(5)
        
        self.running = True
        print(f"[INFO] Servidor HTTP escuchando en {self.host}:{self.port}")
        
        # Entrar al bucle de aceptación
        self._accept_loop()
    
    def _accept_loop(self):
        """
        Bucle principal que acepta conexiones entrantes.
        Cada cliente se maneja en un thread separado.
        """
        while self.running:
            try:
                # accept() bloquea hasta que llegue una conexión
                # Retorna: (socket_cliente, (ip, puerto))
                client_socket, client_address = self.server_socket.accept()
                
                # Crear thread para manejar este cliente
                # daemon=True: el thread muere cuando el programa termina
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                client_thread.start()
                
            except OSError as e:
                # Socket cerrado durante accept() - normal al hacer stop()
                if self.running:
                    print(f"[ERROR] En accept: {e}")
            except Exception as e:
                print(f"[ERROR] Inesperado en accept_loop: {e}")
    
    def _handle_client(self, client_socket: socket.socket, 
                       client_address: tuple):
        """
        Maneja UNA conexión de cliente. Se ejecuta en thread separado.
        
        Args:
            client_socket: Socket conectado al cliente
            client_address: Tupla (ip, puerto) del cliente
        """
        client_ip = client_address[0]
        
        try:
            # Configurar timeout para evitar bloqueo infinito
            client_socket.settimeout(30.0)  # 30 segundos
            
            # Recibir datos del cliente
            raw_data = self._recv_all(client_socket)
            
            if raw_data:
                # Llamar al handler para procesar la petición
                response = self.handler(raw_data, client_ip)
                
                # Enviar respuesta completa
                # sendall() garantiza que se envíen todos los bytes
                client_socket.sendall(response)
            
        except socket.timeout:
            print(f"[WARN] Timeout esperando datos de {client_ip}")
        except ConnectionResetError:
            # Cliente cerró conexión abruptamente - normal
            pass
        except BrokenPipeError:
            # Intentamos escribir a socket cerrado - normal
            pass
        except Exception as e:
            print(f"[ERROR] Manejando cliente {client_ip}: {e}")
        finally:
            # SIEMPRE cerrar el socket del cliente
            try:
                client_socket.close()
            except:
                pass
    
    def _recv_all(self, sock: socket.socket) -> bytes:
        """
        Recibe todos los datos disponibles del socket.
        
        Nota: Para HTTP simple, una sola llamada a recv() suele ser
        suficiente. Para casos complejos, habría que parsear
        Content-Length y leer exactamente esa cantidad.
        
        Args:
            sock: Socket del cliente
            
        Returns:
            Bytes recibidos
        """
        data = b''
        
        try:
            # Primera lectura
            chunk = sock.recv(BUFFER_SIZE)
            data += chunk
            
            # Si recibimos exactamente BUFFER_SIZE, puede haber más
            # Pero para peticiones HTTP típicas, esto es suficiente
            while len(chunk) == BUFFER_SIZE:
                sock.settimeout(0.5)  # Timeout corto para datos adicionales
                try:
                    chunk = sock.recv(BUFFER_SIZE)
                    if chunk:
                        data += chunk
                    else:
                        break
                except socket.timeout:
                    break  # No hay más datos
                    
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
