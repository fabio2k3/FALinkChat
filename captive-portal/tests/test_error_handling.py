from backend.portal_server import PortalHandler
from io import BytesIO

class DummyRequest:
    def __init__(self, body):
        self.rfile = BytesIO(body.encode())
        self.headers = {"Content-Length": str(len(body))}
        self.client_address = ("1.2.3.4", 12345)

def test_authorization_error(monkeypatch):
    handler = PortalHandler(DummyRequest("username=alice&password=password123"), None, None)
    monkeypatch.setattr(handler, "serve_content", lambda content, status=200, content_type="text/html": None)
    monkeypatch.setattr("backend.auth.check_user", lambda u, p: True)
    def raise_error(ip):
        raise Exception("Fallo de ipset")
    monkeypatch.setattr("backend.fw_manager.add_authorized", raise_error)
    handler.do_POST()
