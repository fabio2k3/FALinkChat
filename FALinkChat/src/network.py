import socket
import struct

# Definimos un EtherType personalizado para Link-Chat,
# que permite a la red identificar que esta trama pertenece a nuestro protocolo.
ETH_P_CUSTOM = 0x88B5

def create_raw_socket(iface):
    # Crea un socket raw en Linux para poder enviar y recibir tramas Ethernet directament
    # AF_PACKET indica que operamos a nivel de enlace (capa 2)
    # SOCK_RAW usamos acceso crudo para controlar toda la trama
    # htons convierte el valor EtherType al orden de bytes correcto de red
    raw_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_CUSTOM))
    # Asociamos el socket a una interfaz física específica (por ejemplo, "eth0")
    raw_sock.bind((iface, 0))
    return raw_sock

def build_ethernet_frame(dst_mac, src_mac, ethertype, payload):
    # Construye una trama Ethernet concatenando:
    # MAC de destino (6 bytes), MAC de origen (6 bytes),
    # EtherType (2 bytes, empaquetado en big-endian con struct) y el payload
    # dst_mac y src_mac deben ser bytes de tamaño exactamente 6
    return dst_mac + src_mac + struct.pack('!H', ethertype) + payload

def unpack_ethernet_frame(frame):
    # Desempaqueta una trama Ethernet recibida en sus campos:
    # Extraemos MAC destino e origen de 6 bytes cada uno
    dst_mac = frame[0:6]
    src_mac = frame[6:12]
    # Extraemos EtherType de 2 bytes en formato big-endian
    ethertype = struct.unpack('!H', frame[12:14])[0]
    # El resto de la trama es el payload que contiene nuestro protocolo
    payload = frame[14:]
    return dst_mac, src_mac, ethertype, payload

def send_frame(sock, frame):
    # Envía la trama completa por el socket raw abierto
    sock.send(frame)

def receive_frame(sock, buffer_size=1600):
    # Recibe una trama desde el socket raw
    # El tamaño por defecto del buffer corresponde al MTU Ethernet típico
    return sock.recv(buffer_size)
