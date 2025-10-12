# src/file_transfer.py
# Este módulo implementa la transferencia confiable de archivos y mensajes sobre Ethernet
# Utiliza fragmentación y confirmaciones (ACKs) para garantizar la entrega correcta
# Características principales:
# - Transferencia directa sobre Ethernet (capa 2)
# - Control de errores mediante CRC32
# - Sistema de reenvíos automáticos
# - Soporte para archivos y mensajes de chat
# - Manejo de fragmentos desordenados
import time
import threading
import protocolo
import network

def fragment_data(data, max_payload_size):
    # Divide los datos completos en fragmentos de tamaño máximo especificado.
    # Esto es necesario porque no se puede mandar payloads mayores que la MTU.
    return [data[i:i+max_payload_size] for i in range(0, len(data), max_payload_size)]


class FileTransfer:
    # Esta clase maneja el envío confiable de archivos y mensajes:
    # - Fragmenta archivos grandes en tramas pequeñas
    # - Implementa sistema de reenvío automático si se pierden paquetes
    # - Usa números de secuencia (file_id) para identificar cada transferencia
    # - Mantiene un hilo dedicado para gestionar retransmisiones
    
    def __init__(self, sock, dst_mac, src_mac):
        # Socket raw que usaremos para enviar paquetes Ethernet
        self.sock = sock
        # MAC destino para la transferencia
        self.dst_mac = dst_mac
        # MAC origen de esta máquina (se usará en la trama)
        self.src_mac = src_mac
        # Identificador único incremental de cada archivo o mensaje que enviamos
        self.next_file_id = 1
        # Diccionario para almacenar fragmentos enviados pendientes de confirmación
        # Clave: (file_id, frag_index)
        # Valor: (paquete completo, tiempo del último envío, contador de retransmisiones)
        self.sent_fragments = {}
        # Candado para proteger acceso concurrente desde posibles hilos
        self.lock = threading.Lock()
        # Tiempo en segundos para considerar que un fragmento necesita retransmisión
        self.timeout = 2
        # Límite máximo de reintentos por fragmento antes de abandonarlo
        self.max_retransmissions = 8
        # Bandera para controlar ciclo del hilo de retransmisiones
        self.running = True
        # Hilo daemon que revisa periódicamente si hay fragmentos que reenviar
        self._retrans_thread = threading.Thread(target=self.retransmit_check_loop, daemon=True)
        self._retrans_thread.start()

    def send_file(self, data, dst_mac=None, msg_type=protocolo.MSG_FILE_CHUNK):
        # Permite especificar MAC destino por llamada, si no usa la dada en self
        dst_mac = dst_mac or self.dst_mac
        if dst_mac is None:
            raise ValueError("dst_mac no especificado para send_file")

        # Asigna un id único para esta transferencia para diferenciar archivos/mensajes
        file_id = self.next_file_id
        self.next_file_id += 1  # Incremento para siguiente envío

        # Define tamaño máximo de payload para evitar pasar MTU Ethernet
        max_payload = 1472
        # Fragmenta los datos en pedazos pequeños según max_payload
        fragments = fragment_data(data, max_payload)
        total_frags = len(fragments)

        # Envía cada fragmento con encabezado, flags y CRC
        # El proceso de fragmentación es necesario porque Ethernet tiene un límite
        # de tamaño máximo por trama (MTU). Dividimos archivos grandes en partes
        # más pequeñas y las enviamos una por una con control de errores
        for i, frag in enumerate(fragments):
            flags = 0
            # Marcamos el primer y último fragmento para que el receptor
            # sepa cuándo comienza y termina un archivo
            if i == 0:
                flags = protocolo.set_flag(flags, protocolo.FLAG_IS_FIRST)
            if i == total_frags - 1:
                flags = protocolo.set_flag(flags, protocolo.FLAG_IS_LAST)

            # Proceso de construcción del paquete:
            # 1. Añadir CRC al fragmento para detectar errores
            payload_with_crc = protocolo.append_crc(frag)  # payload + 4 bytes CRC
            # 2. Crear encabezado con metadata (id, número de fragmento, flags)
            header = protocolo.pack_header(file_id, total_frags, i, flags, msg_type, len(payload_with_crc))
            # 3. Ensamblar trama Ethernet completa (direcciones MAC + payload)
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
        # Sistema de mensajes de chat:
        # - Reutiliza el mismo mecanismo que los archivos
        # - Mensajes cortos: envío directo sin fragmentar
        # - Mensajes largos: usa fragmentación automática
        # - Usa MSG_CHAT para identificar que es un mensaje
        data = message_text.encode('utf-8')
        max_payload = 1472
        # Si mensaje es pequeño, envía en un solo paquete sin fragmentar
        if len(data) <= max_payload:
            header = protocolo.pack_header(
                file_id=0,             # ID 0 porque no es archivo
                total_frags=1,
                frag_index=0,
                flags=0,
                msg_type=protocolo.MSG_CHAT,
                payload_len=len(data)
            )
            packet = network.build_ethernet_frame(self.dst_mac, self.src_mac, network.ETH_P_CUSTOM, header + data)
            network.send_frame(self.sock, packet)
        else:
            # Para mensajes largos, utiliza fragmentación igual que archivos, pero tipo chat
            self.send_file(data, msg_type=protocolo.MSG_CHAT)

    def receive_ack(self, ack_packet):
        # Procesa un paquete ACK recibido para eliminar fragmentos confirmados
        try:
            hdr, _ = protocolo.unpack_header(ack_packet)
        except Exception:
            return  # Paquete no válido, ignorar
        if hdr['msg_type'] == protocolo.MSG_ACK:
            key = (hdr['file_id'], hdr['frag_index'])
            with self.lock:
                # Si el fragmento estaba pendiente, se marca como confirmado y se elimina
                if key in self.sent_fragments:
                    del self.sent_fragments[key]
                    # Se puede hacer print para debugging: ACK recibido

    def retransmit_check_loop(self):
        # Mecanismo de retransmisión automática:
        # - Revisa periódicamente los fragmentos enviados
        # - Si pasa el timeout sin recibir ACK, reenvía el fragmento
        # - Mantiene un contador de reintentos para evitar bucles infinitos
        # - Si se excede el máximo de reintentos, abandona el fragmento
        # Este mecanismo garantiza la entrega incluso si hay pérdida de paquetes
        while self.running:
            now = time.time()
            with self.lock:
                for key, (packet, send_time, retrans) in list(self.sent_fragments.items()):
                    # Si pasó el tiempo de espera sin ACK, se revisa reintentos
                    if now - send_time > self.timeout:
                        if retrans >= self.max_retransmissions:
                            # Si se superó el máximo, se elimina fragmento para evitar bloqueo
                            print(f"[FileTransfer] fragment {key} excedió reintentos ({retrans})")
                            del self.sent_fragments[key]
                            continue
                        try:
                            # Reenvía fragmento por socket raw
                            network.send_frame(self.sock, packet)
                        except Exception as e:
                            print(f"[FileTransfer] error re-sending {key}: {e}")
                        # Actualiza tiempo y contador de reintentos
                        self.sent_fragments[key] = (packet, now, retrans + 1)
            # Pausa breve para no consumir CPU excesivamente
            time.sleep(0.5)

    def stop(self):
        self.running = False


class FileReceiver:
    # Esta clase implementa la recepción y reensamblado de archivos:
    # - Recibe fragmentos en cualquier orden
    # - Los almacena en buffers organizados por file_id
    # - Verifica la integridad de cada fragmento con CRC
    # - Reensambla el archivo cuando recibe todos los fragmentos
    # - Envía confirmaciones (ACK) al emisor
    
    def __init__(self, sock, dst_mac, src_mac):
        # Almacena referencias a socket y direcciones MAC para respuesta ACK
        self.sock = sock
        self.dst_mac = dst_mac
        self.src_mac = src_mac
        # Sistema de buffers para reensamblar archivos:
        # - Usa un diccionario donde la clave es el file_id
        # - Cada buffer es una lista del tamaño total de fragmentos
        # - Los fragmentos no recibidos se marcan como None
        # - Permite recibir fragmentos en cualquier orden
        self.buffers = {}

    def receive_fragment(self, packet, src_mac):
        # Este método implementa la lógica de recepción de fragmentos:
        # 1. Desempaqueta y valida el encabezado
        # 2. Verifica el CRC para detectar errores de transmisión
        # 3. Almacena el fragmento en el buffer correspondiente
        # 4. Envía ACK al emisor para confirmar recepción correcta
        # 5. Si recibió todos los fragmentos, reensambla y retorna el archivo completo
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

        # Sistema de verificación de integridad:
        # - Extrae el CRC que viene al final del payload (4 bytes)
        # - Calcula el CRC del payload recibido
        # - Compara ambos CRC para detectar errores de transmisión
        # - Si no coinciden, el fragmento se descarta y será retransmitido
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
        # Sistema de confirmación (ACK):
        # - Confirma al emisor que un fragmento llegó correctamente
        # - Los ACKs son pequeños y no llevan payload
        # - Incluyen el file_id y frag_index para identificar el fragmento
        # - Son fundamentales para la confiabilidad del protocolo
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