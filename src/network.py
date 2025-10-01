import socket

ETH_P_CUSTOM = 0x88B5  # EtherType personalizado para Link-Chat

def create_raw_socket(iface):
    raw_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_CUSTOM))
    raw_sock.bind((iface, 0))
    return raw_sock

def build_ethernet_frame(dst_mac, src_mac, ethertype, payload):
    # MAC address deben estar en bytes de 6 longitud cada una
    return dst_mac + src_mac + struct.pack('!H', ethertype) + payload

def unpack_ethernet_frame(frame):
    dst_mac = frame[0:6]
    src_mac = frame[6:12]
    ethertype = struct.unpack('!H', frame[12:14])[0]
    payload = frame[14:]
    return dst_mac, src_mac, ethertype, payload


def send_frame(sock, frame):
    sock.send(frame)

def receive_frame(sock, buffer_size=1600):
    return sock.recv(buffer_size)
