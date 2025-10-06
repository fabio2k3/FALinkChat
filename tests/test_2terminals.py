import sys
import os
import argparse
import threading
import time
from queue import Queue
import socket
import fcntl
import struct

# Ajuste del path para poder importar los módulos desde tests/
# Si este archivo está en PROJECT_ROOT/tests/test_2terminals.py,
# entonces ROOT = PROJECT_ROOT
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'src'))

import protocolo
import network
import file_transfer

BROADCAST_MAC = b'\xff\xff\xff\xff\xff\xff'

# ---------- Discovery ----------
class Discovery:
    def __init__(self, sock, src_mac):
        self.sock = sock
        self.src_mac = src_mac
        self.neighbors = {}  # MAC -> timestamp

    def send_discovery(self):
        header = protocolo.pack_header(
            file_id=0,
            total_frags=0,
            frag_index=0,
            flags=0,
            msg_type=protocolo.MSG_DISCOVERY,
            payload_len=0
        )
        frame = network.build_ethernet_frame(BROADCAST_MAC, self.src_mac, network.ETH_P_CUSTOM, header)
        network.send_frame(self.sock, frame)
        print("[discovery] MSG_DISCOVERY enviado (broadcast)")

    def handle_packet(self, src_mac, payload):
        hdr, _ = protocolo.unpack_header(payload)
        if hdr['msg_type'] == protocolo.MSG_DISCOVERY:
            # Responder REPLY unicast
            reply_hdr = protocolo.pack_header(
                file_id=0,
                total_frags=0,
                frag_index=0,
                flags=0,
                msg_type=protocolo.MSG_REPLY,
                payload_len=0
            )
            reply_frame = network.build_ethernet_frame(src_mac, self.src_mac, network.ETH_P_CUSTOM, reply_hdr)
            network.send_frame(self.sock, reply_frame)
            print(f"[discovery] REPLY enviado a {mac_bytes_to_str(src_mac)}")
        elif hdr['msg_type'] == protocolo.MSG_REPLY:
            # Registrar vecino
            self.neighbors[src_mac] = time.time()
            print(f"[discovery] MSG_REPLY recibido de {mac_bytes_to_str(src_mac)}")

    def get_neighbors(self):
        # Limpiar vecinos > 5 min
        now = time.time()
        self.neighbors = {mac: t for mac, t in self.neighbors.items() if now - t < 300}
        return list(self.neighbors.keys())

# ---------- utilitarios ----------
def mac_str_to_bytes(mac_str: str) -> bytes:
    return bytes(int(x, 16) for x in mac_str.split(':'))

def mac_bytes_to_str(mac_bytes: bytes) -> str:
    return ':'.join(f'{b:02x}' for b in mac_bytes)

# ---------- receptor ----------
def receiver_loop(sock, discovery_obj, ft_sender, ft_receiver, stop_event):
    print("[receiver] iniciado")
    while not stop_event.is_set():
        try:
            frame = network.receive_frame(sock)
            # --- DEBUG TEMPORAL: mostrar raw frame info ---
            try:
                print("[receiver DEBUG] raw_len=", len(frame), "sample_hex=", frame[:60].hex())
            except Exception:
                print("[receiver DEBUG] raw frame (could not hex)")
            # --- fin DEBUG ---

            if not frame:
                continue
            dst_mac, src_mac, ethertype, payload = network.unpack_ethernet_frame(frame)
            if ethertype != network.ETH_P_CUSTOM:
                continue

            # Discovery
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
                complete = ft_receiver.receive_fragment(payload)
                if complete:
                    fname = f"received_{int(time.time())}.bin"
                    with open(fname, 'wb') as f:
                        f.write(complete)
                    print(f"[receiver] File recibido: {fname}")
            elif hdr['msg_type'] == protocolo.MSG_ACK:
                ft_sender.receive_ack(payload)
        except Exception as e:
            print(f"[receiver] exception: {e}")
            time.sleep(0.1)

# ---------- consola ----------
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

# ---------- main ----------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--iface', required=True)
    parser.add_argument('--mac', required=True)
    args = parser.parse_args()

    iface = args.iface
    src_mac = mac_str_to_bytes(args.mac)

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
                print("  /sendfile <MAC> <archivo>")
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
            elif cmd == "--sendfile" or cmd == "/sendfile":
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
