import backend.fw_manager as fw
import pytest

def test_remove_authorized(monkeypatch):
    called = {}
    def fake_run(cmd, check=True):
        called['cmd'] = cmd
        return None
    monkeypatch.setattr('subprocess', 'run', fake_run)
    fw.remove_authorized("1.2.3.4")
    assert called['cmd'] == ["sudo", "ipset", "del", "AUTHORIZED", "1.2.3.4"]
