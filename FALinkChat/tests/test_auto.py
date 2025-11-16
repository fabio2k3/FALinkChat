import sys
import os
import argparse
import threading
import time
from queue import Queue
import socket
import fcntl
import struct

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'src'))

import protocolo
import network
import file_transfer

BROADCAST_MAC = b'\xff\xff\xff\xff\xff\xff'

# UTILES ;-)
def mac_str_to_bytes(mac_str: str) -> bytes:
    return bytes(int(x, 16) for x in mac_str.split(':'))

def mac_bytes_to_str(mac_bytes: bytes) -> str:
    return ':'.join(f'{b:02x}' for b in mac_bytes)

def get_interface_mac(iface: str) -> bytes:
    # Obtiener MAC de interfaz 
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', bytes(iface[:15], 'utf-8')))
    mac = info[18:24]
    return mac

def detect_default_iface():
    # Seleccionar la primera interfaz no-loopback y 'up' en /sys/class/net."""
    try:
        for ifname in os.listdir('/sys/class/net'):
            if ifname == 'lo':
                continue
            try:
                with open(f'/sys/class/net/{ifname}/operstate', 'r') as f:
                    state = f.read().strip()
                if state != 'up':
                    continue
            except Exception:
                continue
            return ifname
    except Exception:
        pass
    # fallback: pick any non-loopback
    try:
        for ifname in os.listdir('/sys/class/net'):
            if ifname != 'lo':
                return ifname
    except Exception:
        pass
    raise RuntimeError("No se pudo detectar interfaz de red automáticamente; especifica --iface")

# DISCOVERY
class Discovery:
    """
    Esta clase implementa el mecanismo de *descubrimiento de vecinos* en la red local.
    Su función principal es permitir que los nodos 
    se encuentren entre sí cuando están en la misma red, intercambiando mensajes
    de broadcast y reply en la capa de enlace.

    Funciona de la siguiente manera:
      1. Se envía un mensaje de tipo DISCOVERY (broadcast a todos los equipos).
      2. Los equipos que reciben ese mensaje responden con un mensaje de tipo REPLY.
      3. El nodo que envió el DISCOVERY guarda las MAC de quienes respondieron,
         construyendo una lista de vecinos disponibles.
    """

    def __init__(self, sock, src_mac):
        """
        Constructor de la clase Discovery.
        Recibe:
          - sock: el socket de bajo nivel (raw socket) usado para enviar y recibir tramas Ethernet.
          - src_mac: la dirección MAC local de este dispositivo.

        Inicializa:
          - self.neighbors: un diccionario que guardará los vecinos descubiertos.
            La clave es la MAC del vecino y el valor es el tiempo (timestamp)
            en el que se detectó.
        """
        self.sock = sock              # Socket de capa de enlace
        self.src_mac = src_mac        # Dirección MAC del equipo local
        self.neighbors = {}           # Diccionario MAC -> timestamp (última vez visto)

    def send_discovery(self):
        """
        Enviar una trama de broadcast de tipo DISCOVERY a toda la red local.

        - Se crea un encabezado (header) usando el protocolo definido por 'protocolo.pack_header()'.
        - El tipo de mensaje es MSG_DISCOVERY.
        - Se construye una trama Ethernet con destino 'BROADCAST_MAC' (FF:FF:FF:FF:FF:FF).
        - La trama se envía usando 'network.send_frame()'.
        """
        # Construir el encabezado del mensaje (sin carga útil)
        header = protocolo.pack_header(
            file_id=0,               # Identificador de archivo (no aplica en discovery)
            total_frags=0,           # Número total de fragmentos (no aplica)
            frag_index=0,            # Índice de fragmento (no aplica)
            flags=0,                 # Flags (ninguno en este caso)
            msg_type=protocolo.MSG_DISCOVERY,  # Tipo de mensaje: DISCOVERY
            payload_len=0            # Longitud del contenido (no hay payload)
        )

        # Construir la trama Ethernet con destino broadcast
        frame = network.build_ethernet_frame(
            BROADCAST_MAC,           # MAC destino (todos los equipos)
            self.src_mac,            # MAC origen (la de este equipo)
            network.ETH_P_CUSTOM,    # Tipo EtherType personalizado de LinkChat
            header                   # Datos del mensaje
        )

        # Enviar la trama de broadcast a través del socket
        network.send_frame(self.sock, frame)
        print("[discovery] MSG_DISCOVERY enviado (broadcast)")

    def handle_packet(self, src_mac, payload):
        """
        Procesar una trama recibida que puede ser DISCOVERY o REPLY.

        Parámetros:
          - src_mac: MAC del remitente de la trama recibida.
          - payload: datos de la trama (incluye el encabezado de protocolo LinkChat).

        Funcionamiento:
          1. Se desempaqueta el encabezado para leer el tipo de mensaje.
          2. Si es DISCOVERY → se envía una respuesta (REPLY) solo al emisor.
          3. Si es REPLY → se guarda la MAC del emisor en la lista de vecinos.
        """
        # Interpretar el encabezado del mensaje recibido
        hdr, _ = protocolo.unpack_header(payload)

        # Caso 1: recibimos un mensaje de descubrimiento (otro nodo quiere saber quiénes hay)
        if hdr['msg_type'] == protocolo.MSG_DISCOVERY:
            # Construimos un encabezado de tipo REPLY
            reply_hdr = protocolo.pack_header(
                file_id=0,
                total_frags=0,
                frag_index=0,
                flags=0,
                msg_type=protocolo.MSG_REPLY,  # Tipo de mensaje: respuesta
                payload_len=0
            )

            # Creamos una trama dirigida directamente al remitente original
            reply_frame = network.build_ethernet_frame(
                src_mac,               # Destino: quien envió el DISCOVERY
                self.src_mac,          # Origen: nuestra MAC
                network.ETH_P_CUSTOM,  # Tipo de protocolo personalizado
                reply_hdr              # Cuerpo del mensaje
            )

            # Enviar la respuesta directamente al descubridor
            network.send_frame(self.sock, reply_frame)
            print(f"[discovery] REPLY enviado a {mac_bytes_to_str(src_mac)}")

        # Caso 2: recibimos un mensaje de respuesta (otro nodo nos ha respondido)
        elif hdr['msg_type'] == protocolo.MSG_REPLY:
            # Guardamos la MAC del remitente con su hora de detección
            self.neighbors[src_mac] = time.time()
            print(f"[discovery] MSG_REPLY recibido de {mac_bytes_to_str(src_mac)}")

    def get_neighbors(self):
        """
        Devolver la lista actual de vecinos conocidos.

        - Limpia los que ya no han respondido en los últimos 300 segundos (5 minutos).
        - Retorna una lista de direcciones MAC activas.
        """
        now = time.time()

        # Mantener solo los vecinos recientes (últimos 5 minutos)
        self.neighbors = {
            mac: t
            for mac, t in self.neighbors.items()
            if now - t < 300
        }

        # Devuelve solo las MAC (sin los timestamps)
        return list(self.neighbors.keys())


# Receptor 
def receiver_loop(sock, discovery_obj, ft_sender, ft_receiver, stop_event):
    # Carpeta de guardado de archivos recibidos
    save_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    os.makedirs(save_dir, exist_ok=True)

    print("[receiver] iniciado")
    while not stop_event.is_set():
        try:
            frame = network.receive_frame(sock)
            if not frame:
                continue

            try:
                print("[receiver DEBUG] raw_len=", len(frame), "sample_hex=", frame[:60].hex())
            except Exception:
                pass

            dst_mac, src_mac, ethertype, payload = network.unpack_ethernet_frame(frame)
            if ethertype != network.ETH_P_CUSTOM:
                continue

            try:
                hdr, body = protocolo.unpack_header(payload)
            except Exception:
                continue

            if hdr['msg_type'] in (protocolo.MSG_DISCOVERY, protocolo.MSG_REPLY):
                discovery_obj.handle_packet(src_mac, payload)
            elif hdr['msg_type'] == protocolo.MSG_CHAT:
                try:
                    text = body.decode('utf-8')
                except Exception:
                    text = repr(body)
                print(f"\n[{mac_bytes_to_str(src_mac)}] {text}\n> ", end='', flush=True)
            elif hdr['msg_type'] == protocolo.MSG_FILE_CHUNK:
                complete = ft_receiver.receive_fragment(payload, src_mac)
                if complete:
                    fname = f"received_{int(time.time())}.bin"
                    file_path = os.path.join(save_dir, fname)
                    with open(file_path, 'wb') as f:
                        f.write(complete)
                    print(f"[receiver] File recibido: {file_path}")
            elif hdr['msg_type'] == protocolo.MSG_ACK:
                ft_sender.receive_ack(payload)

        except Exception as e:
            print(f"[receiver] exception: {e}")
            time.sleep(0.1)

# Consola 
def console_loop(cmd_queue, stop_event):
    print("Type /help for commands.")
    while not stop_event.is_set():
        try:
            line = input("> ").strip()
        except EOFError:
            cmd_queue.put(("/exit", []))
            break
        if not line:
            continue
        parts = line.split(' ', 2)
        cmd = parts[0]
        args = parts[1:] if len(parts) > 1 else []
        cmd_queue.put((cmd, args))
        if cmd == "/exit":
            break

# Main 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--iface', required=False, help='Opcional: especificar interfaz. Si no se da, se detecta automáticamente.')
    args = parser.parse_args()

    iface = args.iface or detect_default_iface()
    try:
        src_mac = get_interface_mac(iface)
    except Exception as e:
        print(f"[main] Failed to get MAC for {iface}: {e}")
        sys.exit(1)

    print(f"[main] interface: {iface}")
    print(f"[main] MAC local: {mac_bytes_to_str(src_mac)}")

    try:
        sock = network.create_raw_socket(iface)
    except Exception as e:
        print(f"[main] No se puede crear raw socket: {e}")
        sys.exit(1)

    discovery_obj = Discovery(sock, src_mac)
    ft_sender = file_transfer.FileTransfer(sock, BROADCAST_MAC, src_mac)
    ft_receiver = file_transfer.FileReceiver(sock, None, src_mac)

    stop_event = threading.Event()
    cmd_queue = Queue()

    threading.Thread(target=receiver_loop, args=(sock, discovery_obj, ft_sender, ft_receiver, stop_event), daemon=True).start()
    threading.Thread(target=console_loop, args=(cmd_queue, stop_event), daemon=True).start()

    print("[main] Nodo listo para enviar/recibir mensajes.")

    try:
        while True:
            cmd, args = cmd_queue.get()
            if cmd == "/help":
                print("Comandos:")
                print("  /discover")
                print("  /neighbors")
                print("  /send <MAC> <mensaje>")
                print("  /sendall <mensaje>")
                print("  /sendfile <MAC> <archivo>")
                print("  /sendfileall <archivo>")
                print("  /exit")
            elif cmd == "/discover":
                discovery_obj.send_discovery()
            elif cmd == "/neighbors":
                vecinos = discovery_obj.get_neighbors()
                if vecinos:
                    print("Neighbors:")
                    for m in vecinos:
                        print("  -", mac_bytes_to_str(m))
                else:
                    print("Neighbors: ninguno")
            elif cmd == "/send":
                if len(args) < 2:
                    print("Uso: /send <MAC> <mensaje>")
                    continue
                dst_mac = mac_str_to_bytes(args[0])
                ft_sender.dst_mac = dst_mac
                ft_sender.send_chat_message(args[1])
            elif cmd == "/sendall":
                if len(args) < 1:
                    print("Uso: /sendall <mensaje>")
                    continue
                mensaje = args[0]
                vecinos = discovery_obj.get_neighbors()
                if not vecinos:
                    print("No hay vecinos")
                    continue
                for m in vecinos:
                    ft_sender.dst_mac = m
                    ft_sender.send_chat_message(mensaje)
                print("Mensaje enviado a todos.")
            elif cmd == "/sendfile":
                if len(args) < 2:
                    print("Uso: /sendfile <MAC> <archivo>")
                    continue
                path = args[1]
                if not os.path.isfile(path):
                    print("Archivo no encontrado")
                    continue
                dst_mac = mac_str_to_bytes(args[0])
                with open(path, 'rb') as f:
                    data = f.read()
                ft_sender.dst_mac = dst_mac
                threading.Thread(target=lambda: ft_sender.send_file(data), daemon=True).start()
                print("Envio iniciado.")
            elif cmd == "/sendfileall":
                if len(args) < 1:
                    print("Uso: /sendfileall <archivo>")
                    continue
                path = args[0]
                if not os.path.isfile(path):
                    print("Archivo no encontrado")
                    continue
                with open(path, 'rb') as f:
                    data = f.read()
                vecinos = discovery_obj.get_neighbors()
                if not vecinos:
                    print("No hay vecinos")
                    continue
                for m in vecinos:
                    threading.Thread(target=lambda mac=m: ft_sender.send_file(data), daemon=True).start()
                print("Envios iniciados a todos.")
            elif cmd == "/exit":
                print("Saliendo...")
                break
            else:
                print("Comando desconocido (usa /help)")

    except KeyboardInterrupt:
        print("Interrumpido por usuario")
    finally:
        stop_event.set()
        time.sleep(0.2)
        sock.close()
        print("Bye")

if __name__ == "__main__":
    main()