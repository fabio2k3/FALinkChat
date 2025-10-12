# src/discovery.py
# Este módulo implementa el descubrimiento automático de otros nodos en la red local
# Utiliza mensajes broadcast y un sistema de solicitud-respuesta para encontrar vecinos
# Características:
# - Descubrimiento automático de nodos
# - Mantenimiento de lista de vecinos activos
# - Limpieza automática de nodos inactivos
# - Uso de broadcast Ethernet para búsqueda

import time
import protocolo
import network

# Dirección MAC de broadcast: FF:FF:FF:FF:FF:FF
# Cuando se usa esta dirección, la trama llega a todos los equipos de la red local
BROADCAST_MAC = b'\xff\xff\xff\xff\xff\xff'

class Discovery:
    # Esta clase maneja el protocolo de descubrimiento:
    # - Envía mensajes broadcast para encontrar otros nodos
    # - Procesa respuestas de otros nodos
    # - Mantiene una tabla actualizada de vecinos
    # - Limpia automáticamente nodos que ya no responden

    def __init__(self, sock, src_mac):
        # Socket raw para enviar/recibir tramas Ethernet
        self.sock = sock
        # MAC address de este nodo
        self.src_mac = src_mac
        # Diccionario de vecinos descubiertos
        # Clave: MAC address del vecino
        # Valor: Diccionario con información del vecino (timestamp último contacto)
        self.neighbors = {}

    def send_discovery(self):
        # Envía mensaje de descubrimiento:
        # 1. Crea un mensaje tipo DISCOVERY sin payload
        # 2. Lo envía a la dirección de broadcast
        # 3. Todos los nodos en la red local lo recibirán
        # 4. Los nodos responderán con un mensaje REPLY
        
        # Crear header tipo DISCOVERY (sin payload)
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
        # Procesa mensajes de descubrimiento:
        # - Si recibe DISCOVERY: responde con REPLY al emisor
        # - Si recibe REPLY: actualiza tabla de vecinos
        # Este sistema permite mantener una lista actualizada
        # de nodos activos en la red
        
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
        # Sistema de mantenimiento de vecinos:
        # 1. Elimina nodos no vistos en los últimos 5 minutos
        # 2. Esto evita mantener nodos que ya no están activos
        # 3. Asegura que la lista de vecinos está actualizada
        # 4. Retorna solo los nodos que están respondiendo
        tiempo_actual = time.time()
        self.neighbors = {mac: info for mac, info in self.neighbors.items() if tiempo_actual - info["last_seen"] < 300}
        return list(self.neighbors.keys())
