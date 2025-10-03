import unittest
import sys, os

# Añadimos src/ al path para poder importar protocolo
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import protocolo


# Primeros Tests
class TestProtocolo(unittest.TestCase):
    #Pruebas normales del protocolo (ya existentes)

    def test_pack_unpack_header_roundtrip(self):
        header = protocolo.pack_header(1, 5, 2, protocolo.FLAG_IS_FIRST, protocolo.MSG_CHAT, 10)
        hdr, payload = protocolo.unpack_header(header + b'X' * 10)
        self.assertEqual(hdr['file_id'], 1, "✅ file_id correcto después de empaquetar/desempaquetar")
        self.assertEqual(hdr['total_frags'], 5, "✅ total_frags correcto")
        self.assertEqual(hdr['frag_index'], 2, "✅ frag_index correcto")
        self.assertTrue(hdr['flags'] & protocolo.FLAG_IS_FIRST, "✅ FLAG_IS_FIRST está correctamente activado")
        self.assertEqual(hdr['msg_type'], protocolo.MSG_CHAT, "✅ msg_type correcto")
        self.assertEqual(hdr['payload_len'], 10, "✅ payload_len correcto")
        self.assertEqual(payload, b'X' * 10, "✅ Payload recuperado correctamente")

    def test_crc_append_and_verify(self):
        data = b"hola mundo"
        with_crc = protocolo.append_crc(data)
        ok, stripped = protocolo.verify_and_strip_crc(with_crc)
        self.assertTrue(ok, "✅ CRC correcto: los datos no han sido modificados")
        self.assertEqual(stripped, data, "✅ Payload recuperado intacto después de verificar CRC")

    def test_crc_detects_corruption(self):
        data = b"hola"
        with_crc = protocolo.append_crc(data)
        corrupted = with_crc[:-5] + b'X' + with_crc[-4:]
        ok, _ = protocolo.verify_and_strip_crc(corrupted)
        self.assertFalse(ok, "✅ CRC detecta correctamente la corrupción de datos")

    def test_flags_operations(self):
        flags = 0
        flags = protocolo.set_flag(flags, protocolo.FLAG_IS_FIRST)
        self.assertTrue(
            protocolo.is_flag_set(flags, protocolo.FLAG_IS_FIRST),
            "✅ FLAG_IS_FIRST correctamente activado con set_flag"
        )
        flags = protocolo.clear_flag(flags, protocolo.FLAG_IS_FIRST)
        self.assertFalse(
            protocolo.is_flag_set(flags, protocolo.FLAG_IS_FIRST),
            "✅ FLAG_IS_FIRST correctamente desactivado con clear_flag"
        )

# Tests Casos "Limites"
class TestProtocoloEdgeCases(unittest.TestCase):
    #Pruebas de casos límite y manejo de errores

    def test_empty_payload_crc(self):
        #Verifica que un payload vacío se pueda CRC y verificar correctamente.
        data = b""
        with_crc = protocolo.append_crc(data)
        ok, stripped = protocolo.verify_and_strip_crc(with_crc)
        self.assertTrue(ok, "✅ CRC correcto para payload vacío")
        self.assertEqual(stripped, data, "✅ Payload vacío recuperado correctamente")

    def test_large_payload_crc(self):
        #Verifica un payload grande (1MB) se CRC y verifica correctamente.
        data = b"A" * 1024 * 1024  # 1 MB de datos
        with_crc = protocolo.append_crc(data)
        ok, stripped = protocolo.verify_and_strip_crc(with_crc)
        self.assertTrue(ok, "✅ CRC correcto para payload grande")
        self.assertEqual(stripped, data, "✅ Payload grande recuperado correctamente")

    def test_multiple_flags(self):
        #Verifica que múltiples flags puedan activarse y verificarse correctamente.
        flags = 0
        flags = protocolo.set_flag(flags, protocolo.FLAG_IS_FIRST)
        flags = protocolo.set_flag(flags, protocolo.FLAG_IS_LAST)
        self.assertTrue(protocolo.is_flag_set(flags, protocolo.FLAG_IS_FIRST), "✅ FLAG_IS_FIRST activado")
        self.assertTrue(protocolo.is_flag_set(flags, protocolo.FLAG_IS_LAST), "✅ FLAG_IS_LAST activado")
        # Limpiamos uno y verificamos
        flags = protocolo.clear_flag(flags, protocolo.FLAG_IS_FIRST)
        self.assertFalse(protocolo.is_flag_set(flags, protocolo.FLAG_IS_FIRST), "✅ FLAG_IS_FIRST desactivado")
        self.assertTrue(protocolo.is_flag_set(flags, protocolo.FLAG_IS_LAST), "✅ FLAG_IS_LAST sigue activado")

    def test_unpack_header_incomplete_data(self):
        # Verifica que unpack_header lance error si los datos son insuficientes."""
        incomplete_data = b'\x00\x01'  # solo 2 bytes, header mínimo es 10
        with self.assertRaises(ValueError, msg="✅ Se lanza ValueError al desempaquetar datos insuficientes"):
            protocolo.unpack_header(incomplete_data)

    def test_payload_len_mismatch(self):
        # Verifica que si el payload es más corto de lo que indica payload_len, solo se devuelve lo que hay.
        header = protocolo.pack_header(1, 1, 0, 0, protocolo.MSG_CHAT, 10)
        data = header + b"12345"  # 5 bytes en lugar de 10
        hdr, payload = protocolo.unpack_header(data)
        self.assertEqual(payload, b"12345", "✅ Payload recortado correctamente según los datos disponibles")
        self.assertEqual(hdr['payload_len'], 10, "✅ payload_len sigue indicando el valor original del header")


if __name__ == '__main__':
    unittest.main(verbosity=2)
