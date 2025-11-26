#!/usr/bin/env python3
from backend.portal_server import PortalHandler
from http.server import ThreadingHTTPServer

class CaptivePortalDetectionHandler(PortalHandler):

    def do_GET(self):
        path = self.path.split("?")[0]

        # Android
        if path == "/generate_204":
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        # Apple/macOS
        if path in ["/hotspot-detect.html", "/captive.apple.com"]:
            content = b"<HTML><BODY>Success</BODY></HTML>"
            self.serve_content(content, 200, "text/html")
            return

        # Windows
        if path.endswith("connecttest.txt"):
            content = b"Microsoft Connect Test"
            self.serve_content(content, 200, "text/plain")
            return

        # Resto → login original
        super().do_GET()


if __name__ == "__main__":
    server = ThreadingHTTPServer(("", 8081), CaptivePortalDetectionHandler)
    print("Servidor EXTRA iniciado en puerto 8081 (detección automática)")
    server.serve_forever()
