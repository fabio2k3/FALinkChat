import struct
import binascii

# Constantes y formato del header Link-Chat (10 bytes)
LINK_HDR_FMT = '!H H H B B H'  # file_id, total_frags, frag_index, flags, msg_type, payload_len
LINK_HDR_SIZE = struct.calcsize(LINK_HDR_FMT)

# Flags
FLAG_IS_FIRST = 1 << 0
FLAG_IS_LAST = 1 << 1
FLAG_RETRANS = 1 << 2
FLAG_COMPRESSED = 1 << 3

# Tipos de mensaje
MSG_CHAT = 1
MSG_FILE_CHUNK = 2
MSG_ACK = 3
MSG_DISCOVERY = 4
MSG_REPLY = 5

def crc32_bytes(data_bytes):
    return binascii.crc32(data_bytes) & 0xffffffff

def pack_header(file_id, total_frags, frag_index, flags, msg_type, payload_len):
    return struct.pack(LINK_HDR_FMT, file_id, total_frags, frag_index, flags, msg_type, payload_len)

def unpack_header(data):
    if len(data) < LINK_HDR_SIZE:
        raise ValueError("Datos insuficientes para header")
    vals = struct.unpack(LINK_HDR_FMT, data[:LINK_HDR_SIZE])
    hdr = {
        'file_id': vals[0],
        'total_frags': vals[1],
        'frag_index': vals[2],
        'flags': vals[3],
        'msg_type': vals[4],
        'payload_len': vals[5],
    }
    payload = data[LINK_HDR_SIZE:LINK_HDR_SIZE + hdr['payload_len']]
    return hdr, payload

# Funciones para flags
def set_flag(flags, flag):
    return flags | flag

def clear_flag(flags, flag):
    return flags & (~flag)

def is_flag_set(flags, flag):
    return (flags & flag) != 0

# Función para agregar CRC al payload
def append_crc(payload):
    c = crc32_bytes(payload)
    return payload + struct.pack('!I', c)

# Función para verificar y eliminar CRC
def verify_and_strip_crc(payload_with_crc):
    if len(payload_with_crc) < 4:
        return False, None
    payload = payload_with_crc[:-4]
    crc_received = struct.unpack('!I', payload_with_crc[-4:])[0]
    return crc32_bytes(payload) == crc_received, payload
