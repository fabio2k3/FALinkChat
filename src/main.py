import sys
import os
import time
import threading
from queue import Queue, Empty
import socket
import fcntl
import struct
import tkinter.filedialog as fd

# Path para importar interface y módulos
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
INTERFACE_DIR = os.path.join(ROOT, 'interface')
if INTERFACE_DIR not in sys.path:
    sys.path.insert(0, INTERFACE_DIR)

import interface 
import protocolo
import network
import file_transfer

BROADCAST_MAC = b'\xff\xff\xff\xff\xff\xff'

# Debug :-O
ENABLE_DEBUG_NEIGH_PRINTER = True  # imprime vecinos periódicamente
DISCOVERY_WAIT_SECONDS = 0.6       # tiempo de espera tras send_discovery 

# FUNCIONES UTILES :-)
def mac_str_to_bytes(mac_str: str) -> bytes:
    return bytes(int(x, 16) for x in mac_str.split(':'))

def mac_bytes_to_str(mac_bytes: bytes) -> str:
    return ':'.join(f'{b:02x}' for b in mac_bytes)

def get_interface_mac(iface: str) -> bytes:
    # Obtener la dirección MAC de la interfaz 
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', bytes(iface[:15], 'utf-8')))
    return info[18:24]

def detect_default_iface():
    # Detectar automáticamente una interfaz activa
    try:
        for ifname in os.listdir('/sys/class/net'):
            if ifname == 'lo':
                continue
            try:
                with open(f'/sys/class/net/{ifname}/operstate', 'r') as f:
                    if f.read().strip() != 'up':
                        continue
            except Exception:
                continue
            return ifname
    except Exception:
        pass
    # fallback
    try:
        for ifname in os.listdir('/sys/class/net'):
            if ifname != 'lo':
                return ifname
    except Exception:
        pass
    raise RuntimeError("No se pudo detectar interfaz automáticamente; usa --iface")


# Variables globales
gui_queue = Queue()
neighbors_lock = threading.Lock()
neighbors = []  # lista de MACs 
ft_sender_lock = threading.Lock()

# UI helpers
def ui_add_message(text: str):
    # Añadir texto al display desde la GUI.
    disp = interface.display
    disp.configure(state='normal')
    disp.insert('end','\n' +  text.strip() + '\n')
    disp.see('end')
    disp.configure(state='disabled')

def find_widget_by_text(root_widget, text_to_find):
    # Buscar un widget por texto si no hay referencia directa."""
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

# Inicialización de red
def start_network(iface):
    sock = network.create_raw_socket(iface)
    src_mac = get_interface_mac(iface)

    # Cargar clase Discovery 
    try:
        # intentar cargar módulo de tests
        sys.path.insert(0, os.path.join(ROOT, 'tests'))
        from test_auto import Discovery as MyDiscovery
        DiscClass = MyDiscovery
        # quitar tests path 
        try:
            sys.path.remove(os.path.join(ROOT, 'tests'))
        except Exception:
            pass
    except Exception:
        class DiscClass:
            def __init__(self, sock, src_mac):
                self.sock = sock
                self.src_mac = src_mac
                self.neighbors = {}

            def send_discovery(self):
                hdr = protocolo.pack_header(0, 0, 0, 0, protocolo.MSG_DISCOVERY, 0)
                frame = network.build_ethernet_frame(BROADCAST_MAC, self.src_mac, network.ETH_P_CUSTOM, hdr)
                network.send_frame(self.sock, frame)

            def handle_packet(self, src_mac, payload):
                hdr, _ = protocolo.unpack_header(payload)
                if hdr['msg_type'] == protocolo.MSG_REPLY:
                    self.neighbors[src_mac] = time.time()

            def get_neighbors(self):
                now = time.time()
                self.neighbors = {mac: t for mac, t in self.neighbors.items() if now - t < 300}
                return list(self.neighbors.keys())

    disc = DiscClass(sock, src_mac)
    ft_s = file_transfer.FileTransfer(sock, BROADCAST_MAC, src_mac)
    ft_r = file_transfer.FileReceiver(sock, None, src_mac)
    return sock, src_mac, disc, ft_s, ft_r


# Hilo receptor 
def receiver_thread_fn(sock, disc_obj, ft_s, ft_r, stop_event):
    while not stop_event.is_set():
        try:
            frame = network.receive_frame(sock)
            if not frame:
                continue

            # Desempaquetado L2
            try:
                dst_mac, src_mac, ethertype, payload = network.unpack_ethernet_frame(frame)
            except Exception as e:
                print("[RX DEBUG] Error unpack_ethernet_frame:", e)
                continue

            # Debug L2 
            try:
                print("[RX L2] dst:", mac_bytes_to_str(dst_mac), "src:", mac_bytes_to_str(src_mac), "etype:", hex(ethertype), "len:", len(frame))
            except Exception:
                print("[RX L2] (raw) len=", len(frame))

            if ethertype != network.ETH_P_CUSTOM:
                continue

            # Desempaquetado del header Link-Chat
            try:
                hdr, body = protocolo.unpack_header(payload)
            except Exception as e:
                print("[RX] Error unpacking header:", e)
                continue

            # Debug header
            print("[RX] hdr msg_type =", hdr.get('msg_type'), "file_id=", hdr.get('file_id'), "frag_index=", hdr.get('frag_index'))

            if hdr['msg_type'] in (protocolo.MSG_DISCOVERY, protocolo.MSG_REPLY):
                try:
                    disc_obj.handle_packet(src_mac, payload)
                    print("[RX] discovery.handle_packet invoked for src", mac_bytes_to_str(src_mac))
                except Exception as e:
                    print("[RX] discovery.handle_packet error:", e)
            elif hdr['msg_type'] == protocolo.MSG_CHAT:
                try:
                    text = body.decode('utf-8', errors='replace')
                except Exception:
                    text = repr(body)
                gui_queue.put(('chat', mac_bytes_to_str(src_mac), text))
            elif hdr['msg_type'] == protocolo.MSG_FILE_CHUNK:
                complete = ft_r.receive_fragment(payload, src_mac)
                if complete:
                    fname = f"received_{int(time.time())}.bin"
                    filepath = os.path.join(os.getcwd(), fname)
                    with open(filepath, 'wb') as f:
                        f.write(complete)
                    gui_queue.put(('file', mac_bytes_to_str(src_mac), filepath))
            elif hdr['msg_type'] == protocolo.MSG_ACK:
                ft_s.receive_ack(payload)
        except Exception as e:
            print("[receiver_thread_fn exception]", e)
            time.sleep(0.01)


# Callbacks GUI
def on_connect_pressed(disc_obj):
    # Envía mensaje de descubrimiento y muestra vecinos.
    ui_add_message("Enviando discovery...")
    disc_obj.send_discovery()
    time.sleep(DISCOVERY_WAIT_SECONDS)   
    found = disc_obj.get_neighbors()
    with neighbors_lock:
        neighbors.clear()
        neighbors.extend(found)
    ui_add_message("Neighbors:")
    if not found:
        ui_add_message("  (ninguno)")
    else:
        for m in found:
            ui_add_message("  - " + mac_bytes_to_str(m))

def on_send_text_pressed(ft_s):
    # Enviar texto a todos los vecinos.
    text = interface.entry.get().strip()
    if not text:
        return
    ui_add_message("Yo: " + text)
    interface.entry.delete(0, 'end')
    with neighbors_lock:
        dests = list(neighbors)
    if not dests:
        ui_add_message("(No hay vecinos: pulsa Connect)")
        return

    def send_to(mac_bytes):
        prev = getattr(ft_s, 'dst_mac', None)
        with ft_sender_lock:
            ft_s.dst_mac = mac_bytes
            try:
                ft_s.send_chat_message(text)
            except Exception as e:
                gui_queue.put(('error', f"Error enviando a {mac_bytes_to_str(mac_bytes)}: {e}"))
            finally:
                ft_s.dst_mac = prev

    for d in dests:
        threading.Thread(target=lambda m=d: send_to(m), daemon=True).start()

def on_send_file_pressed(ft_s):
    # Enviar un archivo a todos los vecinos.
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

# Poller GUI 
def gui_poller():
    try:
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
        pass
    interface.root.after(100, gui_poller)


# Debug: imprime vecinos periódicamente 
def _debug_neighbor_printer(disc_obj):
    while True:
        time.sleep(1.0)
        try:
            found = disc_obj.get_neighbors()
            if found:
                print("[DEBUG neighbors]", [mac_bytes_to_str(m) for m in found])
        except Exception:
            pass


def main(argv):
    iface = None
    if len(argv) > 1 and argv[1] == '--iface' and len(argv) > 2:
        iface = argv[2]
    iface = iface or detect_default_iface()

    print(f"[main] interface: {iface}")
    sock, src_mac, disc_obj, ft_s, ft_r = start_network(iface)
    print(f"[main] local MAC: {mac_bytes_to_str(src_mac)}")

    stop_event = threading.Event()
    t = threading.Thread(target=receiver_thread_fn, args=(sock, disc_obj, ft_s, ft_r, stop_event), daemon=True)
    t.start()

    # Debug neighbor printer 
    if ENABLE_DEBUG_NEIGH_PRINTER:
        threading.Thread(target=_debug_neighbor_printer, args=(disc_obj,), daemon=True).start()

    # Asignar acciones a los botones
    try:
        if hasattr(interface, 'btn_connect'):
            interface.btn_connect.configure(command=lambda: on_connect_pressed(disc_obj))
        else:
            btn = find_widget_by_text(interface.root, "Connect")
            if btn:
                btn.configure(command=lambda: on_connect_pressed(disc_obj))
    except Exception:
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

    # Iniciar bucle GUI y poller
    interface.root.after(100, gui_poller)
    interface.root.mainloop()

    # Cierre limpio
    stop_event.set()
    try:
        sock.close()
    except Exception:
        pass
    print("[main] Finalizado correctamente.")

if __name__ == '__main__':
    main(sys.argv)