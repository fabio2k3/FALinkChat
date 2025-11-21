from backend.portal_server import PortalHandler
from io import BytesIO
import pytest

class DummyRequest:
    """
    Esta clase simula una petición HTTP POST para el test.
    En Python, los servidores web reciben peticiones como objetos con atributos como rfile (body), headers y client_address.
    """
    def __init__(self, body):
        self.rfile = BytesIO(body.encode())  # Simula el body de la petición POST
        self.headers = {"Content-Length": str(len(body))}  # Simula la cabecera HTTP con el tamaño del body
        self.client_address = ("1.2.3.4", 12345)  # Simula la IP y puerto del cliente

# Explicación detallada del test:
def test_login_success(monkeypatch):
    """
    Este test comprueba que el flujo de login funciona correctamente:
    1. Crea un handler de PortalHandler con una petición simulada (DummyRequest).
    2. Mockea (sustituye) las funciones críticas para evitar efectos reales:
       - serve_content: para no enviar respuestas reales.
       - check_user: para simular autenticación exitosa.
       - add_authorized: para simular autorización sin modificar el sistema.
    3. Ejecuta el método do_POST() del handler, que procesa la petición.
    """
    # Instancia el handler con la petición simulada
    handler = PortalHandler(DummyRequest("username=alice&password=password123"), None, None)
    # Mockea las funciones para evitar efectos reales
    monkeypatch.setattr(handler, "serve_content", lambda content, status=200, content_type="text/html": None)
    monkeypatch.setattr("backend.auth.check_user", lambda u, p: True)
    monkeypatch.setattr("backend.fw_manager.add_authorized", lambda ip: None)
    # Ejecuta el POST
    handler.do_POST()

"""
Explicación de PortalHandler:
- PortalHandler es una clase que hereda de BaseHTTPRequestHandler (de la librería estándar de Python).
- Su constructor espera tres argumentos: request, client_address, server. En este test, solo el primero (DummyRequest) es relevante, los otros dos se ponen como None porque no se usan en el test.
- PortalHandler implementa los métodos do_GET y do_POST, que procesan las peticiones HTTP GET y POST.
- En el test, se simula una petición POST con datos de login, y se comprueba que el flujo de autenticación y autorización funciona correctamente usando mocks.
- El uso de DummyRequest permite simular el entorno que normalmente provee el servidor HTTP, sin levantar un servidor real.
- El test no envía respuestas reales ni modifica el sistema, solo valida la lógica del flujo.
"""
