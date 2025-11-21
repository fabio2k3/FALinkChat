import backend.fw_manager as fw
import pytest

def test_add_authorized(monkeypatch):
    """
    Este test verifica que la función add_authorized construye el comando correcto para agregar una IP al conjunto AUTHORIZED.
    Se usa monkeypatch para reemplazar subprocess.run por una función falsa (mock), evitando ejecutar comandos reales en el sistema.
    Así, el test solo comprueba la lógica del código, no modifica el sistema ni requiere permisos.
    """
    llamado = {}
    def fake_run(cmd, check=True):
        llamado['cmd'] = cmd
        return None
    # monkeypatch reemplaza subprocess.run por fake_run SOLO durante este test
    monkeypatch.setattr('subprocess', 'run', fake_run)
    fw.add_authorized("1.2.3.4")
    # Verificamos que el comando generado es el esperado
    assert llamado['cmd'] == ["sudo", "ipset", "add", "AUTHORIZED", "1.2.3.4"]

"""
Explicación:
- mockeo: Es una técnica para simular el comportamiento de funciones externas (como subprocess.run) sin ejecutarlas realmente. Permite probar la lógica interna sin efectos secundarios.
- monkeypatch: Es una herramienta de pytest que permite reemplazar funciones o atributos en tiempo de ejecución, solo durante el test. Así, subprocess.run se reemplaza por fake_run, que no ejecuta nada real.
- Este test comprueba que add_authorized genera el comando correcto, sin modificar el sistema ni requerir permisos sudo.
"""
