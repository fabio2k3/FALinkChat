import sys
import os
import time
import threading
from queue import Queue, Empty
import socket
import fcntl
import struct
import tkinter.filedialog as fd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
INTERFACE_DIR = os.path.join(ROOT, 'interface')

# Añadimos INTERFACE_DIR al sys.path para poder importar el módulo interface
# que contiene los widgets de la GUI (root, entry, display, botones, etc).
if INTERFACE_DIR not in sys.path:
    sys.path.insert(0, INTERFACE_DIR)

import interface
import protocolo
import network
import file_transfer

# Constantes y configuración global
BROADCAST_MAC = b'\xff\xff\xff\xff\xff\xff'  # dirección MAC de broadcast (todo el LAN)

# Flags de depuración 
ENABLE_DEBUG_NEIGH_PRINTER = True  # si True, imprime vecinos periodicamente en consola
DISCOVERY_WAIT_SECONDS = 0.6       # tiempo que espera la UI tras enviar un discovery


def mac_str_to_bytes(mac_str: str) -> bytes:
    """
    Convierte una MAC en formato 'aa:bb:cc:dd:ee:ff' a 6 bytes.
    Útil para cuando el usuario introduce MACs en forma textual.
    """
    return bytes(int(x, 16) for x in mac_str.split(':'))

def mac_bytes_to_str(mac_bytes: bytes) -> str:
    """
    Convierte 6 bytes de MAC a su representación textual con ':'.
    """
    return ':'.join(f'{b:02x}' for b in mac_bytes)

def get_interface_mac(iface: str) -> bytes:
    """
    Obtener la dirección MAC asociada a la interfaz `iface` en Linux.
    - Crea un socket UDP solo para obtener un file descriptor (no envía UDP).
    - Llama a ioctl(SIOCGIFHWADDR) para pedir al kernel la dirección hardware.
    - Extrae los 6 bytes de la MAC del buffer devuelto (offset 18:24).
    Nota: esta implementación asume Linux y layout del struct ifreq.
    """
    # Creamos socket (AF_INET, SOCK_DGRAM) únicamente para usar su fileno()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Preparar el buffer estilo ifreq con el nombre de la interfaz (max 15 chars)
    # struct.pack('256s', ...) crea 256 bytes donde los primeros contienen el nombre.
    info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', bytes(iface[:15], 'utf-8')))
    # Los 6 bytes de la MAC están en info[18:24] según layout de ifreq/ifr_hwaddr en Linux.
    return info[18:24]

def detect_default_iface():
    """
    Intentar detectar automáticamente una interfaz de red valida cuando no
    se especifica por argumento. Estrategia:
      1) Recorre /sys/class/net buscando la primera interfaz que no sea 'lo'
         y cuyo archivo 'operstate' diga 'up'.
      2) Si no encuentra ninguna 'up', devuelve la primera interfaz distinta
         de 'lo' (fallback).
      3) Si no hay interfaces válidas, lanza RuntimeError.
    NOTA: esta función está orientada a entornos Linux que exponen /sys/class/net.
    """
    # Intentamos detectar la primera interfaz 'up' (excluyendo loopback)
    try:
        for ifname in os.listdir('/sys/class/net'):
            if ifname == 'lo':
                continue
            try:
                with open(f'/sys/class/net/{ifname}/operstate', 'r') as f:
                    if f.read().strip() != 'up':
                        # si el estado no es 'up' seguimos buscando
                        continue
            except Exception:
                # si hay cualquier problema leyendo el archivo (p. ej. permisos),
                # saltamos esta interfaz
                continue
            # devolvemos la primera interfaz no-loopback que esté 'up'
            return ifname
    except Exception:
        # si listar '/sys/class/net' falla (p. ej. no existe), caemos al fallback
        pass

    # fallback: devolvemos la primera interfaz que no sea 'lo' (aunque no esté 'up')
    try:
        for ifname in os.listdir('/sys/class/net'):
            if ifname != 'lo':
                return ifname
    except Exception:
        pass

    # si todo falla, pedimos al usuario que especifique --iface
    raise RuntimeError("No se pudo detectar interfaz automáticamente; usa --iface")


# Cola para pasar eventos del hilo de red a la GUI (thread-safe)
gui_queue = Queue()
# Lock para proteger acceso concurrente a la lista 'neighbors'
neighbors_lock = threading.Lock()
# Lista mantenida por la GUI con las MACs de vecinos (bytes)
neighbors = []
# Lock para serializar accesos/temporalmente cambiar ft_s.dst_mac al enviar
ft_sender_lock = threading.Lock()



def ui_add_message(text: str):
    """
    Inserta una línea en el display de la GUI de forma segura.
    - interface.display se asume un widget Text de Tkinter.
    - Se cambia el estado temporalmente para permitir escritura.
    """
    disp = interface.display
    disp.configure(state='normal')
    disp.insert('end', '\n' + text.strip() + '\n')
    disp.see('end')  # desplaza al final para ver el mensaje
    disp.configure(state='disabled')

def find_widget_by_text(root_widget, text_to_find):
    """
    Busca recursivamente en la jerarquía de widgets un widget que contenga
    'text_to_find' en su texto (propiedad 'text').
    Útil cuando interface no exporta el widget pero queremos localizarlo.
    """
    txt_lower = text_to_find.lower()
    stack = [root_widget]
    while stack:
        w = stack.pop()
        try:
            if hasattr(w, 'cget'):
                t = w.cget('text')
                if isinstance(t, str) and txt_lower in t.lower():
                    return w
        except Exception:
            pass
        try:
            stack.extend(w.winfo_children())
        except Exception:
            pass
    return None

# Inicialización de la red y creación de objetos principales
def start_network(iface):
    """
    Inicializar la capa de enlace:
      - crea un socket raw sobre la interfaz indicada
      - obtiene la MAC local
      - instancia Discovery (clase para buscar vecinos)
      - instancia FileTransfer (emisor) y FileReceiver (receptor)
    Devuelve: sock, src_mac, disc_obj, ft_sender, ft_receiver
    """
    # Crear socket raw (AF_PACKET) para enviar/recibir tramas Ethernet
    sock = network.create_raw_socket(iface)
    # Obtener MAC de la interfaz local (6 bytes)
    src_mac = get_interface_mac(iface)

    # Intento opcional de cargar una clase Discovery desde tests (para automatización/test)
    try:
        # añadimos la carpeta 'tests' temporalmente para poder importar test_auto.Discovery
        sys.path.insert(0, os.path.join(ROOT, 'tests'))
        from test_auto import Discovery as MyDiscovery
        DiscClass = MyDiscovery
        # removemos el path de tests para no ensuciar sys.path
        try:
            sys.path.remove(os.path.join(ROOT, 'tests'))
        except Exception:
            pass
    except Exception:
        # Si no existe test_auto, definimos una clase Discovery mínima localmente.
        class DiscClass:
            def __init__(self, sock, src_mac):
                self.sock = sock
                self.src_mac = src_mac
                self.neighbors = {}

            def send_discovery(self):
                # Construye un header de tipo DISCOVERY sin payload y lo envía a broadcast
                hdr = protocolo.pack_header(0, 0, 0, 0, protocolo.MSG_DISCOVERY, 0)
                frame = network.build_ethernet_frame(BROADCAST_MAC, self.src_mac, network.ETH_P_CUSTOM, hdr)
                network.send_frame(self.sock, frame)

            def handle_packet(self, src_mac, payload):
                # Procesa replies: si recibe MSG_REPLY registra el vecino con timestamp
                hdr, _ = protocolo.unpack_header(payload)
                if hdr['msg_type'] == protocolo.MSG_REPLY:
                    self.neighbors[src_mac] = time.time()

            def get_neighbors(self):
                # Elimina vecinos no vistos en los últimos 300 segundos (5 minutos)
                now = time.time()
                self.neighbors = {mac: t for mac, t in self.neighbors.items() if now - t < 300}
                return list(self.neighbors.keys())

    # Instanciamos objetos de uso: discovery, file transfer sender y receptor
    disc = DiscClass(sock, src_mac)
    ft_s = file_transfer.FileTransfer(sock, BROADCAST_MAC, src_mac)
    ft_r = file_transfer.FileReceiver(sock, None, src_mac)
    return sock, src_mac, disc, ft_s, ft_r


# Hilo receptor: lee tramas L2 y las despacha a módulos (discovery, chat, file)
def receiver_thread_fn(sock, disc_obj, ft_s, ft_r, stop_event):
    """
    Bucle que corre en un hilo (daemon) y recibe tramas Ethernet:
      - desempaqueta Ethernet (dst, src, ethertype, payload)
      - filtra por ethertype del protocolo Link-Chat
      - desempaqueta header del protocolo y despacha por tipo de mensaje:
        DISCOVERY / REPLY -> disc_obj.handle_packet
        CHAT -> enviar a GUI
        FILE_CHUNK -> ft_r.receive_fragment (reensamblado)
        ACK -> ft_s.receive_ack (confirmar fragmentos)
    stop_event es un threading.Event que permite salir limpiamente.
    """
    while not stop_event.is_set():
        try:
            # Recibe una trama desde el socket raw; bloquea hasta que llegue algo
            frame = network.receive_frame(sock)
            if not frame:
                # Si no hay datos (posible socket no bloqueante o timeout), repetir
                continue
            # Desempaquetado L2
            try:
                dst_mac, src_mac, ethertype, payload = network.unpack_ethernet_frame(frame)
            except Exception as e:
                # Si la trama está mal formada, la ignoramos y seguimos
                print("[RX DEBUG] Error unpack_ethernet_frame:", e)
                continue

            # Debug L2: imprimir info legible (MACs en hex) si es posible
            try:
                print("[RX L2] dst:", mac_bytes_to_str(dst_mac),
                      "src:", mac_bytes_to_str(src_mac),
                      "etype:", hex(ethertype), "len:", len(frame))
            except Exception:
                print("[RX L2] (raw) len=", len(frame))

            # Procesar solo tramas con el EtherType que usa Link-Chat
            if ethertype != network.ETH_P_CUSTOM:
                continue

            # Desempaquetado del header del protocolo (capa Link-Chat)
            try:
                hdr, body = protocolo.unpack_header(payload)
            except Exception as e:
                print("[RX] Error unpacking header:", e)
                continue

            # Debug header: ver el tipo y metadatos básicos
            print("[RX] hdr msg_type =", hdr.get('msg_type'),
                  "file_id=", hdr.get('file_id'),
                  "frag_index=", hdr.get('frag_index'))

            # Dispatch por tipo de mensaje
            if hdr['msg_type'] in (protocolo.MSG_DISCOVERY, protocolo.MSG_REPLY):
                # Mensajes de descubrimiento: pasar al objeto discovery para que responda
                try:
                    disc_obj.handle_packet(src_mac, payload)
                    print("[RX] discovery.handle_packet invoked for src", mac_bytes_to_str(src_mac))
                except Exception as e:
                    print("[RX] discovery.handle_packet error:", e)

            elif hdr['msg_type'] == protocolo.MSG_CHAT:
                # Mensaje de chat: decodificar texto y ponerlo en la cola GUI
                try:
                    text = body.decode('utf-8', errors='replace')
                except Exception:
                    text = repr(body)
                gui_queue.put(('chat', mac_bytes_to_str(src_mac), text))

            elif hdr['msg_type'] == protocolo.MSG_FILE_CHUNK:
                # Fragmento de archivo: pasarlo al reensamblador (ft_r)
                # ft_r.receive_fragment devuelve los datos completos si ya se reensamblaron todos los fragmentos
                complete = ft_r.receive_fragment(payload, src_mac)
                if complete:
                    # Escrita del archivo recibido en disco con nombre simple basado en timestamp
                    fname = f"received_{int(time.time())}.bin"
                    filepath = os.path.join(os.getcwd(), fname)
                    with open(filepath, 'wb') as f:
                        f.write(complete)
                    # Notificar a GUI que hemos recibido un archivo
                    gui_queue.put(('file', mac_bytes_to_str(src_mac), filepath))

            elif hdr['msg_type'] == protocolo.MSG_ACK:
                # ACK de fragmento: notificar al emisor para que elimine fragmento pendiente
                ft_s.receive_ack(payload)

        except Exception as e:
            # Capturamos excepciones de alto nivel para no matar el hilo; pequeño sleep evita bucle caliente.
            print("[receiver_thread_fn exception]", e)
            time.sleep(0.01)


# Callbacks conectados a botones de la GUI
def on_connect_pressed(disc_obj):
    """
    Acción ejecutada cuando el usuario pulsa 'Connect' en la GUI:
      - Envía un discovery broadcast
      - Espera un breve intervalo para recibir replies
      - Actualiza la lista global `neighbors` con lo descubierto
      - Muestra la lista en la GUI
    """
    ui_add_message("Enviando discovery...")
    disc_obj.send_discovery()               # broadcast DISCOVERY
    time.sleep(DISCOVERY_WAIT_SECONDS)      # esperamos un poco para que lleguen replies
    found = disc_obj.get_neighbors()        # obtenemos vecinos conocidos (filtrados por TTL)

    # Actualizamos la lista global de vecinos de forma thread-safe
    with neighbors_lock:
        neighbors.clear()
        neighbors.extend(found)

    # Mostramos resultado en la GUI
    ui_add_message("Neighbors:")
    if not found:
        ui_add_message("  (ninguno)")
    else:
        for m in found:
            ui_add_message("  - " + mac_bytes_to_str(m))

def on_send_text_pressed(ft_s):
    """
    Acción cuando el usuario pulsa el botón de enviar texto:
      - Lee el texto del entry de la GUI
      - Para cada vecino conocido lanza un hilo que:
        - ajusta temporalmente ft_s.dst_mac al destino
        - llama a ft_s.send_chat_message(text)
        - restaura ft_s.dst_mac original
    Esta estrategia permite enviar en paralelo sin interferir con otros envíos.
    """
    text = interface.entry.get().strip()
    if not text:
        return
    ui_add_message("Yo: " + text)
    interface.entry.delete(0, 'end')

    # copia segura de la lista de vecinos
    with neighbors_lock:
        dests = list(neighbors)

    if not dests:
        ui_add_message("(No hay vecinos: pulsa Connect)")
        return

    def send_to(mac_bytes):
        # Guardamos el dst_mac previo para restaurarlo al terminar
        prev = getattr(ft_s, 'dst_mac', None)
        with ft_sender_lock:
            ft_s.dst_mac = mac_bytes
            try:
                ft_s.send_chat_message(text)
            except Exception as e:
                # Comunicamos errores a la GUI mediante la cola
                gui_queue.put(('error', f"Error enviando a {mac_bytes_to_str(mac_bytes)}: {e}"))
            finally:
                # Restauramos el destino anterior (si lo había)
                ft_s.dst_mac = prev

    # Lanzamos un hilo por destino para no bloquear la GUI
    for d in dests:
        threading.Thread(target=lambda m=d: send_to(m), daemon=True).start()

def on_send_file_pressed(ft_s):
    """
    Acción cuando el usuario pulsa el botón de enviar archivo:
      - Abre diálogo para seleccionar archivo
      - Lee el archivo en memoria (data)
      - Para cada vecino lanza un hilo que usa ft_s.send_file(data)
    Nota: leer archivos grandes en memoria puede consumir RAM; para archivos muy grandes
    podría implementarse lectura por streaming/fragmentos fuera de memoria.
    """
    path = fd.askopenfilename()
    if not path:
        return
    ui_add_message("Yo: enviando archivo " + os.path.basename(path))
    with open(path, 'rb') as f:
        data = f.read()

    with neighbors_lock:
        dests = list(neighbors)

    if not dests:
        ui_add_message("(No hay vecinos: pulsa Connect)")
        return

    for d in dests:
        def _send(mac=d, dat=data):
            prev = getattr(ft_s, 'dst_mac', None)
            with ft_sender_lock:
                ft_s.dst_mac = mac
                try:
                    ft_s.send_file(dat)
                except Exception as e:
                    gui_queue.put(('error', f"Error enviando archivo a {mac_bytes_to_str(mac)}: {e}"))
                finally:
                    ft_s.dst_mac = prev
        threading.Thread(target=_send, daemon=True).start()


# Poller de la GUI: saca eventos de la cola gui_queue y actualiza la interfaz
def gui_poller():
    """
    Ejecutado periódicamente desde el hilo principal de la GUI (Tkinter).
    Lee eventos que los hilos de red han puesto en gui_queue y actualiza display.
    Esto evita manipular widgets de Tkinter desde hilos secundarios.
    """
    try:
        # Vaciar la cola hasta que esté vacía
        while True:
            typ, *rest = gui_queue.get_nowait()
            if typ == 'chat':
                macstr, text = rest
                ui_add_message(f"{macstr}: {text}")
            elif typ == 'file':
                macstr, filepath = rest
                ui_add_message(f"{macstr}: archivo recibido -> {filepath}")
            elif typ == 'error':
                (msg,) = rest
                ui_add_message("[ERROR] " + msg)
    except Empty:
        # Si la cola está vacía, no hacemos nada
        pass
    # Volver a programar el poller dentro de 100 ms
    interface.root.after(100, gui_poller)

# Hilo de debugging: imprime vecinos periódicamente 
def _debug_neighbor_printer(disc_obj):
    """
    Hilo que imprime en consola la lista de vecinos cada segundo.
    Útil para desarrollo/ver que discovery funciona.
    """
    while True:
        time.sleep(1.0)
        try:
            found = disc_obj.get_neighbors()
            if found:
                print("[DEBUG neighbors]", [mac_bytes_to_str(m) for m in found])
        except Exception:
            pass


# Función main: parseo inicial, arranque de hilos y GUI
def main(argv):
    """
    Punto de entrada principal:
      - obtiene la interfaz a usar (argumento --iface o detect_default_iface)
      - inicializa red y objetos
      - lanza el hilo receptor
      - conecta callbacks a botones de la GUI
      - inicia loop principal de Tkinter
      - al cerrar, hace limpieza
    """
    # Permitir pasar la interfaz por argumentos: python main.py --iface enp0s3
    iface = None
    if len(argv) > 1 and argv[1] == '--iface' and len(argv) > 2:
        iface = argv[2]
    # Si no se pasó por argumento, intentar detectar una interfaz por defecto
    iface = iface or detect_default_iface()

    print(f"[main] interface: {iface}")

    # Inicializar red y obtener objetos (socket, mac local, discovery, file transfer sender/receiver)
    sock, src_mac, disc_obj, ft_s, ft_r = start_network(iface)
    print(f"[main] local MAC: {mac_bytes_to_str(src_mac)}")

    # Evento para señalar al hilo receptor que debe parar cuando se cierre la app
    stop_event = threading.Event()
    # Arrancar hilo receptor (daemon para que no impida cerrar la app)
    t = threading.Thread(target=receiver_thread_fn, args=(sock, disc_obj, ft_s, ft_r, stop_event), daemon=True)
    t.start()

    # Hilo opcional de debugging que imprime vecinos cada segundo
    if ENABLE_DEBUG_NEIGH_PRINTER:
        threading.Thread(target=_debug_neighbor_printer, args=(disc_obj,), daemon=True).start()


    # Asociar acciones a botones de la GUI. Se intenta usar referencias directas
    # exportadas por el módulo interface; si no existen, se busca el botón por texto.
    try:
        if hasattr(interface, 'btn_connect'):
            interface.btn_connect.configure(command=lambda: on_connect_pressed(disc_obj))
        else:
            btn = find_widget_by_text(interface.root, "Connect")
            if btn:
                btn.configure(command=lambda: on_connect_pressed(disc_obj))
    except Exception:
        # Si algo falla al asociar evento, ignoramos (no crítico)
        pass

    try:
        if hasattr(interface, 'btn_sendfile'):
            interface.btn_sendfile.configure(command=lambda: on_send_file_pressed(ft_s))
        else:
            btn = find_widget_by_text(interface.root, "Send file")
            if btn:
                btn.configure(command=lambda: on_send_file_pressed(ft_s))
    except Exception:
        pass

    try:
        if hasattr(interface, 'btn_send'):
            interface.btn_send.configure(command=lambda: on_send_text_pressed(ft_s))
        else:
            btn = find_widget_by_text(interface.root, "➤")
            if btn:
                btn.configure(command=lambda: on_send_text_pressed(ft_s))
    except Exception:
        pass

    # Iniciar el poller de la GUI y el bucle principal de Tkinter (bloqueante)
    interface.root.after(100, gui_poller)
    interface.root.mainloop()

    # Limpieza al cerrar
    stop_event.set()  # avisar al hilo receptor que debe salir
    try:
        sock.close()
    except Exception:
        pass
    print("[main] Finalizado correctamente.")


# Ejecutable directo
if __name__ == '__main__':
    main(sys.argv)
