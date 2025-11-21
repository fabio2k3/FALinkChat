import backend.fw_manager as fw

def test_is_authorized(monkeypatch):
    class Result:
        returncode = 0  # Simula éxito, IP autorizada
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: Result())
    assert fw.is_authorized("1.2.3.4") is True

def test_is_not_authorized(monkeypatch):
    class Result:
        returncode = 1  # Simula error, IP no autorizada
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: Result())
    assert fw.is_authorized("5.6.7.8") is False
