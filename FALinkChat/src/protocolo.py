# src/protocolo.py
# Este módulo implementa el protocolo de comunicación Link-Chat
# Define el formato de los mensajes, tipos, flags y funciones de manipulación

import struct
import binascii

# Definimos el formato del encabezado personalizado para los mensajes de Link-Chat.
# '!H H H B B H' indica el orden y tamaño de cada campo:
# H = unsigned short (2 bytes), B = unsigned char (1 byte).
# Campos: file_id, total_frags, frag_index, flags, msg_type, payload_len (total 10 bytes)
LINK_HDR_FMT = '!H H H B B H'

# Calculamos el tamaño en bytes del header con struct para validar y usar luego.
LINK_HDR_SIZE = struct.calcsize(LINK_HDR_FMT)

# Definimos las constantes para los flags del mensaje usando bits individuales.
FLAG_IS_FIRST = 1 << 0      # Indica que el fragmento es el primero del mensaje.
FLAG_IS_LAST = 1 << 1       # Indica que es el fragmento final del mensaje.
FLAG_RETRANS = 1 << 2       # Indica que es una retransmisión de un fragmento.
FLAG_COMPRESSED = 1 << 3    # Indica que el payload está comprimido (puede usarse en el futuro)

# Definimos los tipos de mensaje que permitirá el protocolo:
MSG_CHAT = 1          # Mensaje de texto chat.
MSG_FILE_CHUNK = 2    # Fragmento de archivo en transferencia.
MSG_ACK = 3           # Acknowledgement para confirmar recepción.
MSG_DISCOVERY = 4     # Mensaje para descubrimiento de vecinos en la red.
MSG_REPLY = 5         # Respuesta unicast a un broadcast de descubrimiento.

# Función para calcular el CRC32 del array de bytes que reciba.
# El CRC es una forma robusta de checksum que ayuda a detectar errores en los datos.
def crc32_bytes(data_bytes):
    # Obtiene un entero de 32 bits representando el CRC para los datos dados.
    return binascii.crc32(data_bytes) & 0xffffffff

# Empaqueta un header de mensaje según el formato definido.
# Convierte los campos del header a una secuencia de 10 bytes.
def pack_header(file_id, total_frags, frag_index, flags, msg_type, payload_len):
    return struct.pack(LINK_HDR_FMT, file_id, total_frags, frag_index, flags, msg_type, payload_len)

# Desempaqueta el header de un bloque de datos y retorna sus campos.
# Extrae los primeros 10 bytes como header y devuelve el resto.
def unpack_header(data):
    # Verifica que haya suficientes datos para el header.
    if len(data) < LINK_HDR_SIZE:
        raise ValueError("Datos insuficientes para header")
    
    # Extrae los campos del header según el formato definido.
    vals = struct.unpack(LINK_HDR_FMT, data[:LINK_HDR_SIZE])
    
    # Crea un diccionario con los campos del header.
    hdr = {
        'file_id': vals[0],       # ID del archivo/mensaje
        'total_frags': vals[1],   # Total de fragmentos
        'frag_index': vals[2],    # Índice del fragmento actual
        'flags': vals[3],         # Flags de control
        'msg_type': vals[4],      # Tipo de mensaje
        'payload_len': vals[5],   # Tamaño del contenido
    }
    
    # Devuelve el header y el resto de los datos.
    remainder = data[LINK_HDR_SIZE:]
    return hdr, remainder

# Funciones para manipular los flags del mensaje.
# Permiten activar, desactivar y verificar bits individuales.

# Activa un flag específico usando OR.
def set_flag(flags, flag):
    return flags | flag

# Desactiva un flag específico usando AND con complemento.
def clear_flag(flags, flag):
    return flags & (~flag)

# Verifica si un flag está activo usando AND.
def is_flag_set(flags, flag):
    return (flags & flag) != 0

# Agrega un CRC al final del payload para verificar integridad.
# El CRC se empaqueta en formato big-endian de 4 bytes (!I).
def append_crc(payload):
    c = crc32_bytes(payload)
    return payload + struct.pack('!I', c)

# Verifica y elimina el CRC de un payload recibido.
# Retorna una tupla (is_valid, payload_sin_crc).
# Si el CRC no coincide o hay error, is_valid será False.
def verify_and_strip_crc(payload_with_crc):
    # Verificamos que al menos tengamos los 4 bytes del CRC.
    if len(payload_with_crc) < 4:
        return False, None
    # Separamos el payload del CRC.
    payload = payload_with_crc[:-4]
    # Extraemos el CRC recibido (4 bytes en formato !I).
    crc_received = struct.unpack('!I', payload_with_crc[-4:])[0]
    # Verificamos si el CRC calculado coincide con el recibido.
    return crc32_bytes(payload) == crc_received, payload

# Formato y tamaño para el CRC32 (4 bytes).
LINK_CRC_FMT = '!I'
LINK_CRC_SIZE = struct.calcsize(LINK_CRC_FMT)

# Crea un mensaje completo combinando header, contenido y CRC.
def pack_message(msg_type, file_id, content, flags=0, frag_index=0, total_frags=1):
    # Convierte el contenido a bytes si es necesario.
    content_bytes = content if isinstance(content, bytes) else content.encode('utf-8')
    payload_len = len(content_bytes)
    
    # Crea el header del mensaje.
    hdr = pack_header(file_id, total_frags, frag_index, flags, msg_type, payload_len)
    
    # Agrega CRC al final para verificación.
    content_crc = crc32_bytes(content_bytes)
    crc_bytes = struct.pack(LINK_CRC_FMT, content_crc)
    
    return hdr + content_bytes + crc_bytes

# Extrae y valida un mensaje, separando header, contenido y CRC.
def unpack_message(data):
    # Obtiene el header y el resto de datos.
    hdr, remainder = unpack_header(data)
    
    # Verifica que el mensaje esté completo.
    if len(remainder) < hdr['payload_len'] + LINK_CRC_SIZE:
        raise ValueError("Datos insuficientes para payload y CRC")

    # Separa contenido y CRC.
    content = remainder[:hdr['payload_len']]
    crc_bytes = remainder[hdr['payload_len']:]
    
    # Verifica integridad del mensaje.
    expected_crc = struct.unpack(LINK_CRC_FMT, crc_bytes)[0]
    if expected_crc != crc32_bytes(content):
        raise ValueError("CRC inválido")

    return hdr, content
