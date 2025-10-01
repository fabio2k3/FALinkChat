import time
import threading
import protocolo
import network

def fragment_data(data, max_payload_size):
    # Divide datos grandes en fragmentos para enviar
    return [data[i:i+max_payload_size] for i in range(0, len(data), max_payload_size)]

class FileTransfer:
    def __init__(self, sock, dst_mac, src_mac):
        self.sock = sock
        self.dst_mac = dst_mac
        self.src_mac = src_mac
        self.next_file_id = 1
        self.sent_fragments = {}  # fragmentos enviados y no confirmados
        self.lock = threading.Lock()
        self.timeout = 2  # tiempo para retransmitir
        self.running = True
        threading.Thread(target=self.retransmit_check_loop, daemon=True).start()

    def send_file(self, data, msg_type=protocolo.MSG_FILE_CHUNK):
        file_id = self.next_file_id
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

            # Use the provided msg_type when packing the header
            header = protocolo.pack_header(file_id, total_frags, i, flags, msg_type, len(frag))
            payload = protocolo.append_crc(frag)
            packet = network.build_ethernet_frame(self.dst_mac, self.src_mac, network.ETH_P_CUSTOM, header + payload)

            ack_received = False
            while not ack_received:
                network.send_frame(self.sock, packet)
                with self.lock:
                    self.sent_fragments[(file_id, i)] = (packet, time.time())

                start_time = time.time()
                while time.time() - start_time < self.timeout:
                    with self.lock:
                        if (file_id, i) not in self.sent_fragments:
                            ack_received = True
                            break
                    time.sleep(0.05)
    
    def send_chat_message(self, message_text):
        data = message_text.encode('utf-8')
        max_payload = 1472

        if len(data) <= max_payload:
        # El mensaje cabe en un solo fragmento
            header = protocolo.pack_header(
                file_id=0,
                total_frags=1,
                frag_index=0,
                flags=0,
                msg_type=protocolo.MSG_CHAT,
                payload_len=len(data)
        )
            packet = network.build_ethernet_frame(
                self.dst_mac, self.src_mac, network.ETH_P_CUSTOM, header + data
        )
            network.send_frame(self.sock, packet)
        else:
        # Si mensaje es muy largo, fragmentar y enviar usando la misma función que para archivos
            self.send_file(data, msg_type=protocolo.MSG_CHAT)


    def receive_ack(self, ack_packet):
        hdr, _ = protocolo.unpack_header(ack_packet)
        if hdr['msg_type'] == protocolo.MSG_ACK:
            key = (hdr['file_id'], hdr['frag_index'])
            with self.lock:
                if key in self.sent_fragments:
                    del self.sent_fragments[key]

    def retransmit_check_loop(self):
        while self.running:
            now = time.time()
            with self.lock:
                for key, (packet, send_time) in list(self.sent_fragments.items()):
                    if now - send_time > self.timeout:
                        network.send_frame(self.sock, packet)
                        self.sent_fragments[key] = (packet, now)
            time.sleep(0.5)

class FileReceiver:
    def __init__(self, sock, dst_mac, src_mac):
        self.sock = sock
        self.dst_mac = dst_mac
        self.src_mac = src_mac
        self.buffers = {}

    def receive_fragment(self, packet):
        hdr, payload_crc = protocolo.unpack_header(packet)
        valid_crc, payload = protocolo.verify_and_strip_crc(payload_crc)
        if not valid_crc:
            print("CRC incorrecto. Fragmento descartado.")
            return None

        file_id = hdr['file_id']
        frag_index = hdr['frag_index']
        total_frags = hdr['total_frags']

        if file_id not in self.buffers:
            self.buffers[file_id] = [None] * total_frags

        self.buffers[file_id][frag_index] = payload

        self.send_ack(file_id, frag_index)

        if None not in self.buffers[file_id]:
            complete_data = b''.join(self.buffers[file_id])
            del self.buffers[file_id]
            return complete_data
        return None

    def send_ack(self, file_id, frag_index):
        flags = 0
        msg_type = protocolo.MSG_ACK
        payload_len = 0
        total_frags = 0

        header = protocolo.pack_header(file_id, total_frags, frag_index, flags, msg_type, payload_len)

        ack_packet = network.build_ethernet_frame(
            self.dst_mac,
            self.src_mac,
            network.ETH_P_CUSTOM,
            header
        )
        network.send_frame(self.sock, ack_packet)
