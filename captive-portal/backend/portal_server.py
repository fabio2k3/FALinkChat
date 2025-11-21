#!/usr/bin/env python3
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import urllib.parse, os

from auth import load_users, check_user
from fw_manager import add_authorized

# Cargar usuarios al iniciar el servidor
load_users()

def load_file(name, folder="html"):
    """Carga archivos HTML o CSS desde la carpeta especificada"""
    path = os.path.join(folder, name)
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None

class PortalHandler(BaseHTTPRequestHandler):
    def serve_content(self, content, status=200, content_type="text/html"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        # Servir archivos CSS
        if self.path.endswith(".css"):
            css_name = self.path.lstrip("/")
            content = load_file(css_name, "html")
            if content:
                self.serve_content(content, 200, "text/css")
            else:
                err = b"/* CSS not found */"
                self.serve_content(err, 404, "text/css")
        else:
            content = load_file("login.html")
            if content:
                self.serve_content(content, 200, "text/html")
            else:
                err = b"<html><body><h2>Portal no disponible</h2></body></html>"
                self.serve_content(err, 500, "text/html")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", errors="ignore")
        params = urllib.parse.parse_qs(body)
        username = params.get("username", [""])[0]
        password = params.get("password", [""])[0]
        client_ip = self.client_address[0]

        if check_user(username, password):
            try:
                add_authorized(client_ip)
            except Exception:
                err = b"<html><body><h2>Error autorizando IP</h2></body></html>"
                self.serve_content(err, 500, "text/html")
                return
            content = load_file("success.html")
            if content:
                self.serve_content(content, 200, "text/html")
            else:
                err = b"<html><body><h2>Success page not found</h2></body></html>"
                self.serve_content(err, 500, "text/html")
        else:
            content = load_file("fail.html")
            if content:
                self.serve_content(content, 401, "text/html")
            else:
                err = b"<html><body><h2>Login failed</h2></body></html>"
                self.serve_content(err, 401, "text/html")

if __name__ == "__main__":
    server = ThreadingHTTPServer(("", 8080), PortalHandler)
    print("Servidor iniciado en puerto 8080")
    server.serve_forever()
