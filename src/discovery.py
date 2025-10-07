import time
import protocolo
import network

BROADCAST_MAC = b'\xff\xff\xff\xff\xff\xff'

class Discovery:
    def __init__(self, sock, src_mac):
        self.sock = sock
        self.src_mac = src_mac
        self.neighbors = {}  # Guarda MAC vecinos con fecha última vez vistos

    def send_discovery(self):
        """Envia un mensaje broadcast para descubrir vecinos"""
        # Header Link-Chat tipo DISCOVERY (sin payload)
        header = protocolo.pack_header(
            file_id=0,
            total_frags=0,
            frag_index=0,
            flags=0,
            msg_type=protocolo.MSG_DISCOVERY,
            payload_len=0
        )
        frame = network.build_ethernet_frame(
            BROADCAST_MAC,  # Broadcast a toda la red local
            self.src_mac,
            network.ETH_P_CUSTOM,
            header
        )
        network.send_frame(self.sock, frame)

    def handle_packet(self, src_mac, payload):
        """Procesa mensajes DISCOVERY y REPLY recibidos"""
        hdr, _ = protocolo.unpack_header(payload)

        if hdr["msg_type"] == protocolo.MSG_DISCOVERY:
            # Recibimos discovery, responder con mensaje REPLY unicast
            reply_hdr = protocolo.pack_header(
                file_id=0,
                total_frags=0,
                frag_index=0,
                flags=0,
                msg_type=protocolo.MSG_REPLY,
                payload_len=0
            )
            reply_frame = network.build_ethernet_frame(
                src_mac,        # Enviar a quien pidió discovery
                self.src_mac,
                network.ETH_P_CUSTOM,
                reply_hdr
            )
            network.send_frame(self.sock, reply_frame)

        elif hdr["msg_type"] == protocolo.MSG_REPLY:
            # Vecino responde, actualizamos tabla de vecinos con timestamp
            self.neighbors[src_mac] = {"last_seen": time.time()}

    def get_neighbors(self):
        """Devuelve lista de vecinos activos (puedes limpiar vecinos antigüos)"""
        # Por ejemplo eliminar vecinos no vistos hace más de 5 minutos
        tiempo_actual = time.time()
        self.neighbors = {mac: info for mac, info in self.neighbors.items() if tiempo_actual - info["last_seen"] < 300}
        return list(self.neighbors.keys())
