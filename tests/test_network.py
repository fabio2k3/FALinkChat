import unittest
import sys, os
from unittest import mock

# Añadimos src/ al path para poder importar network
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import network


class TestNetwork(unittest.TestCase):
    #Pruebas unitarias para network: construcción, desempaquetado y simulación de envío/recepción.

    def test_build_and_unpack_frame(self):
        # Verifica que un frame Ethernet se construya y desempaque correctamente.
        dst_mac = b'\xaa\xbb\xcc\xdd\xee\xff'
        src_mac = b'\x11\x22\x33\x44\x55\x66'
        ethertype = network.ETH_P_CUSTOM
        payload = b'HolaRed'

        frame = network.build_ethernet_frame(dst_mac, src_mac, ethertype, payload)
        d, s, e, p = network.unpack_ethernet_frame(frame)

        self.assertEqual(d, dst_mac, "✅ Dirección MAC de destino correcta")
        self.assertEqual(s, src_mac, "✅ Dirección MAC de origen correcta")
        self.assertEqual(e, ethertype, "✅ Ethertype correcto")
        self.assertEqual(p, payload, "✅ Payload correctamente recuperado")

    def test_unpack_frame_partial(self):
        # Verifica que un frame demasiado corto lance struct.error al desempaquetar.
        incomplete_frame = b'\xaa\xbb\xcc'  # Solo 3 bytes
        import struct
        with self.assertRaises(struct.error, msg="✅ Desempaquetado de frame incompleto lanza struct.error"):
            network.unpack_ethernet_frame(incomplete_frame)



    # Pruebas extendidas: simulación de envío/recepción

    def test_send_and_receive_frame(self):
        #S imula el envío y recepción de un frame usando un socket mockeado.
        dst_mac = b'\xaa\xbb\xcc\xdd\xee\xff'
        src_mac = b'\x11\x22\x33\x44\x55\x66'
        ethertype = network.ETH_P_CUSTOM
        payload = b'HolaRed'
        frame = network.build_ethernet_frame(dst_mac, src_mac, ethertype, payload)

        mock_sock = mock.Mock()
        mock_sock.recv.return_value = frame

        network.send_frame(mock_sock, frame)
        mock_sock.send.assert_called_once_with(frame)
        print("✅ send_frame llamado correctamente con el frame")

        received = network.receive_frame(mock_sock)
        self.assertEqual(received, frame, "✅ receive_frame devuelve correctamente el frame enviado")

    def test_receive_frame_with_buffer_size(self):
        # Simula recepción de un frame con tamaño de buffer personalizado.
        frame = b'\x00' * 50
        mock_sock = mock.Mock()
        mock_sock.recv.return_value = frame

        received = network.receive_frame(mock_sock, buffer_size=100)
        self.assertEqual(received, frame, "✅ receive_frame respeta buffer_size y devuelve frame completo")


if __name__ == '__main__':
    unittest.main(verbosity=2)
