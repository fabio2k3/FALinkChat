# src/file_transfer.py
import time
import threading
import protocolo
import network

def fragment_data(data, max_payload_size):
    #Dividir datos grandes en fragmentos de tamaño max_payload_size
    return [data[i:i+max_payload_size] for i in range(0, len(data), max_payload_size)]


class FileTransfer:
    def __init__(self, sock, dst_mac, src_mac):
        self.sock = sock
        self.dst_mac = dst_mac
        self.src_mac = src_mac
        self.next_file_id = 1

        # sent_fragments maps (file_id, frag_index) -> (packet, last_send_time, retrans_count)
        self.sent_fragments = {}
        self.lock = threading.Lock()

        self.timeout = 2  # segundos para considerar retransmisión
        self.max_retransmissions = 8  # límite de reintentos por fragmento

        self.running = True
        self._retrans_thread = threading.Thread(target=self.retransmit_check_loop, daemon=True)
        self._retrans_thread.start()

    def send_file(self, data, dst_mac=None, msg_type=protocolo.MSG_FILE_CHUNK):
        dst_mac = dst_mac or self.dst_mac
        if dst_mac is None:
            raise ValueError("dst_mac no especificado para send_file")

        file_id = self.next_file_id
        # evitar wrap simple 
        self.next_file_id += 1

        max_payload = 1472  
        fragments = fragment_data(data, max_payload)
        total_frags = len(fragments)

        for i, frag in enumerate(fragments):
            flags = 0
            if i == 0:
                flags = protocolo.set_flag(flags, protocolo.FLAG_IS_FIRST)
            if i == total_frags - 1:
                flags = protocolo.set_flag(flags, protocolo.FLAG_IS_LAST)

            payload_with_crc = protocolo.append_crc(frag)  # payload + 4 bytes CRC
            header = protocolo.pack_header(file_id, total_frags, i, flags, msg_type, len(payload_with_crc))
            packet = network.build_ethernet_frame(dst_mac, self.src_mac, network.ETH_P_CUSTOM, header + payload_with_crc)

            # DEBUG EMISOR: longitud, crc calculado y primeros bytes
            try:
                crc_calc = protocolo.crc32_bytes(frag)
            except Exception:
                crc_calc = None
            print(f"[EMIT] file_id={file_id} frag={i}/{total_frags} payload_len={len(payload_with_crc)} crc_calc={('0x%08x'%crc_calc) if crc_calc is not None else None} first16={payload_with_crc[:16].hex()} total_packet_len={len(packet)}")

            key = (file_id, i)
            with self.lock:
                # inicializar registro del fragmento con contador 0
                self.sent_fragments[key] = (packet, time.time(), 0)

            sent_ok = False
            # ciclo hasta recibir ACK (o hasta exceder retransmisiones)
            while not sent_ok:
                try:
                    network.send_frame(self.sock, packet)
                except Exception as e:
                    print(f"[FileTransfer] error sending packet {key}: {e}")

                start_time = time.time()
                while time.time() - start_time < self.timeout:
                    with self.lock:
                        if key not in self.sent_fragments:
                            sent_ok = True
                            break
                    time.sleep(0.05)

                if sent_ok:
                    break

                # si timeout sin ACK, gestionar reintentos
                with self.lock:
                    pkt, last_send, retrans = self.sent_fragments.get(key, (packet, time.time(), 0))
                    if retrans >= self.max_retransmissions:
                        # abandonar fragmento 
                        print(f"[FileTransfer] fragment {key} excedió reintentos ({retrans}). Abandonando fragmento.")
                        if key in self.sent_fragments:
                            del self.sent_fragments[key]
                        sent_ok = True
                        break
                    else:
                        # actualizar contador y reintentar inmediatamente
                        self.sent_fragments[key] = (pkt, time.time(), retrans + 1)
                        try:
                            network.send_frame(self.sock, pkt)
                        except Exception as e:
                            print(f"[FileTransfer] error re-sending {key}: {e}")
                        # luego volver al bucle esperar ACK


    def send_chat_message(self, message_text):
        data = message_text.encode('utf-8')
        max_payload = 1472

        if len(data) <= max_payload:
            header = protocolo.pack_header(
                file_id=0,
                total_frags=1,
                frag_index=0,
                flags=0,
                msg_type=protocolo.MSG_CHAT,
                payload_len=len(data)
            )
            packet = network.build_ethernet_frame(self.dst_mac, self.src_mac, network.ETH_P_CUSTOM, header + data)
            network.send_frame(self.sock, packet)
        else:
            # fragmentar chats largos usando send_file con msg_type MSG_CHAT
            self.send_file(data, msg_type=protocolo.MSG_CHAT)

    def receive_ack(self, ack_packet):
        try:
            hdr, _ = protocolo.unpack_header(ack_packet)
        except Exception:
            return
        if hdr['msg_type'] == protocolo.MSG_ACK:
            key = (hdr['file_id'], hdr['frag_index'])
            with self.lock:
                if key in self.sent_fragments:
                    del self.sent_fragments[key]
                    # opcional: print(f"[FileTransfer] ACK recibido para {key}")

    def retransmit_check_loop(self):
        while self.running:
            now = time.time()
            with self.lock:
                for key, (packet, send_time, retrans) in list(self.sent_fragments.items()):
                    if now - send_time > self.timeout:
                        if retrans >= self.max_retransmissions:
                            print(f"[FileTransfer] fragment {key} excedió reintentos ({retrans}) en retransmit loop. Removiendo.")
                            del self.sent_fragments[key]
                            continue
                        try:
                            network.send_frame(self.sock, packet)
                        except Exception as e:
                            print(f"[FileTransfer] error re-sending {key}: {e}")
                        # actualizar tiempo y contador
                        self.sent_fragments[key] = (packet, now, retrans + 1)
            time.sleep(0.5)

    def stop(self):
        self.running = False


class FileReceiver:
    def __init__(self, sock, dst_mac, src_mac):
        self.sock = sock
        self.dst_mac = dst_mac
        self.src_mac = src_mac
        self.buffers = {}

    def receive_fragment(self, packet, src_mac):
        try:
            hdr, remainder = protocolo.unpack_header(packet)
        except Exception as e:
            print(f"[FileReceiver] unpack_header error: {e}")
            return None

        payload_len = hdr.get('payload_len', None)
        if payload_len is None:
            print("[FileReceiver] header sin payload_len válido. Fragmento descartado.")
            return None

        remainder_len = len(remainder)
        if remainder_len < payload_len:
            print(f"[FileReceiver] Fragmento truncado (remainder_len={remainder_len} < payload_len={payload_len}). Descartado.")
            return None

        payload_with_crc = remainder[:payload_len]

        # obtener CRC recibido y calcular CRC local
        if len(payload_with_crc) >= 4:
            crc_received = int.from_bytes(payload_with_crc[-4:], 'big')
            payload = payload_with_crc[:-4]
            crc_calc = protocolo.crc32_bytes(payload)
        else:
            crc_received = None
            payload = b''
            crc_calc = None

        # debug receptor
        print(f"[RECV] file_id={hdr['file_id']} frag={hdr['frag_index']}/{hdr['total_frags']} payload_len={payload_len} remainder_len={remainder_len} crc_received={('0x%08x'%crc_received) if crc_received is not None else None} crc_calc={('0x%08x'%crc_calc) if crc_calc is not None else None} first16={payload_with_crc[:16].hex()}")

        valid_crc, _ = protocolo.verify_and_strip_crc(payload_with_crc)
        if not valid_crc:
            print("CRC incorrecto. Fragmento descartado.")
            return None

        file_id = hdr['file_id']
        frag_index = hdr['frag_index']
        total_frags = hdr['total_frags']

        if file_id not in self.buffers:
            # inicializa la lista con tamaño total_frags
            self.buffers[file_id] = [None] * total_frags

        # evitar duplicados
        if self.buffers[file_id][frag_index] is not None:
            # reenviar ACK por si el emisor lo necesita
            self.send_ack(file_id, frag_index, src_mac)
            return None

        self.buffers[file_id][frag_index] = payload

        # enviar ACK de confirmación
        self.send_ack(file_id, frag_index, src_mac)

        # si ya tenemos todos los fragmentos, ensamblar y devolver
        if None not in self.buffers[file_id]:
            complete_data = b''.join(self.buffers[file_id])
            del self.buffers[file_id]
            return complete_data

        return None

    def send_ack(self, file_id, frag_index, dst_mac):
        flags = 0
        msg_type = protocolo.MSG_ACK
        payload_len = 0
        total_frags = 0

        header = protocolo.pack_header(file_id, total_frags, frag_index, flags, msg_type, payload_len)

        ack_packet = network.build_ethernet_frame(
            dst_mac,          # A quien responder
            self.src_mac,     # MAC local del receptor (emisor del ACK)
            network.ETH_P_CUSTOM,
            header
        )
        network.send_frame(self.sock, ack_packet)